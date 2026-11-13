import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from controller_lab.controller_art import ART_ROOT, ControllerView, Overlay, catalog, fitted_rect
from controller_lab.model import FAMILIES, Sample
from test_ui import APP


class ControllerArtworkTests(unittest.TestCase):
    def test_upstream_and_adapted_vector_checksums(self):
        sources = json.loads((ART_ROOT / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual(set(sources), set(FAMILIES))
        for entry in sources.values():
            with self.subTest(file=entry["file"]):
                self.assertEqual(hashlib.sha256((ART_ROOT / entry["file"]).read_bytes()).hexdigest(), entry["sha256"])
                self.assertEqual(hashlib.sha256((ART_ROOT / entry["upstream_file"]).read_bytes()).hexdigest(), entry["upstream_sha256"])
                self.assertIn(entry["license"], ("MIT", "GPL-3.0", "CC-BY-SA-3.0"))
                for additional in entry.get("additional_sources", []):
                    self.assertEqual(hashlib.sha256((ART_ROOT / additional["upstream_file"]).read_bytes()).hexdigest(),
                                     additional["sha256"])

    def test_all_models_are_complete_vectors_without_raster_or_external_content(self):
        for family, spec in catalog().items():
            with self.subTest(family=family):
                model = Overlay(family)
                self.assertTrue(model.full.isValid())
                self.assertTrue(model.base.isValid())
                self.assertTrue(model.active.isValid())
                for id in set(spec["parts"].values()) | set(spec["sticks"].values()):
                    self.assertTrue(model.full.elementExists(id), id)
                    self.assertGreater(model.boxes[id].width(), 0, id)
                root = ET.fromstring((ART_ROOT / spec["file"]).read_bytes())
                for node in root.iter():
                    self.assertNotIn(node.tag.rsplit("}", 1)[-1], ("image", "script", "foreignObject"))
                    self.assertFalse(any(key.lower().endswith("href") for key in node.attrib))

    def test_original_controller_path_geometry_is_preserved(self):
        sources = json.loads((ART_ROOT / "sources.json").read_text(encoding="utf-8"))
        for family, entry in sources.items():
            upstream = ET.parse(ART_ROOT / entry["upstream_file"]).getroot()
            original_paths = {n.get("d") for n in upstream.iter() if n.tag.endswith("}path")}
            for additional in entry.get("additional_sources", []):
                extra = ET.parse(ART_ROOT / additional["upstream_file"]).getroot()
                original_paths.update(n.get("d") for n in extra.iter() if n.tag.endswith("}path"))
            adapted = ET.parse(ART_ROOT / entry["file"]).getroot()
            for node in adapted.iter():
                if node.tag.endswith("}path"):
                    if family == "playstation" and (node.get("id") in ("Triangle", "Square", "Circle", "Cross")
                                                     or node.get("id", "").startswith("lab-glyph-")):
                        # DS4 combines the ring and symbol; those contours are split
                        # so the symbol can be centered independently of its button.
                        continue
                    self.assertIn(node.get("d"), original_paths, family)

    def test_outline_weight_stays_constant_when_models_are_resized(self):
        # Pixel coverage doubles with perimeter when a stroke keeps its weight.
        # A stroke that scales with the picture would cover four times the area.
        for family in catalog():
            model = Overlay(family)
            key = "dpup" if family == "wii" else "lefttrigger"
            areas = []
            for size in (180, 360):
                image = QImage(size + 24, size + 24, QImage.Format.Format_ARGB32)
                image.fill(QColor("#222630"))
                painter = QPainter(image)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                # DS4 keeps its hit-test/active shape hidden in the neutral view.
                id = "LT" if family == "playstation" else model.spec["parts"][key]
                model.full.render(painter, id, QRectF(12, 12, size, size))
                painter.end()
                # Cyan's green-channel coverage, including fractional edge pixels.
                data = bytes(image.constBits())
                areas.append(sum(max(0, data[i] - 38) / 153 for i in range(1, len(data), 4)))
            with self.subTest(family=family):
                self.assertGreater(areas[0], 50)
                self.assertAlmostEqual(areas[1] / areas[0], 2, delta=.12)

    def test_xbox_front_view_keeps_buttons_and_sticks_round(self):
        model = Overlay("xbox")
        for key in ("a", "b", "x", "y"):
            box = model.part_box(key)
            self.assertAlmostEqual(box.width() / box.height(), 1, delta=.001)
        for id in model.spec["sticks"].values():
            box = model.boxes[id]
            self.assertAlmostEqual(box.width() / box.height(), 1, delta=.001)
        self.assertAlmostEqual(model.part_box("x").center().y(), model.part_box("b").center().y(), delta=.1)

    def test_gamecube_uses_the_centered_full_wordmark(self):
        model = Overlay("gamecube")
        self.assertFalse(model.full.elementExists("GCN"))
        id = "lab-gamecube-wordmark"
        self.assertTrue(model.full.elementExists(id))
        box = model.full.transformForElement(id).mapRect(model.full.boundsOnElement(id))
        self.assertAlmostEqual(box.center().x(), model.part_box("start").center().x(), delta=5)
        self.assertLess(box.bottom(), model.part_box("start").top())
        tree = ET.parse(ART_ROOT / model.spec["file"]).getroot()
        self.assertTrue(any(n.text == "NINTENDO GAMECUBE" for n in tree.iter() if n.tag.endswith("}title")))

    def test_playstation_symbols_have_their_own_centered_geometry(self):
        for family in ("dualsense", "playstation"):
            model = Overlay(family)
            self.assertEqual(set(model.spec["glyphs"]), {"a", "b", "x", "y"})
            for key, id in model.spec["glyphs"].items():
                with self.subTest(family=family, symbol=key):
                    box = model.full.transformForElement(id).mapRect(model.full.boundsOnElement(id))
                    center = box.center()
                    if key == "y":
                        center.setY(box.top() + box.height() * 2 / 3)
                    target = model.part_box(key).center()
                    self.assertAlmostEqual(center.x(), target.x(), places=5)
                    self.assertAlmostEqual(center.y(), target.y(), places=5)
                    self.assertGreater(box.width(), 0)
                    self.assertLess(box.width(), model.part_box(key).width() * .85)

    def test_ds4_button_rings_stay_aligned_when_glyphs_are_separated(self):
        model = Overlay("playstation")
        for key, ring in (("a", "Cross"), ("b", "Circle"), ("x", "Square"), ("y", "Triangle")):
            rect = model.full.transformForElement(ring).mapRect(model.full.boundsOnElement(ring))
            target = model.part_box(key)
            self.assertAlmostEqual(rect.center().x(), target.center().x(), places=5)
            self.assertAlmostEqual(rect.center().y(), target.center().y(), places=5)
            self.assertAlmostEqual(rect.width(), target.width(), places=5)
            self.assertAlmostEqual(rect.height(), target.height(), places=5)

    def test_tall_and_wide_views_keep_their_proportions(self):
        for spec in catalog().values():
            source = QRectF(*spec["viewbox"])
            for bounds in (QRectF(0, 0, 120, 500), QRectF(20, 40, 1000, 120)):
                target = fitted_rect(source, bounds)
                self.assertAlmostEqual(target.width() / target.height(), source.width() / source.height())
                self.assertLessEqual(target.width(), bounds.width() + .001)
                self.assertLessEqual(target.height(), bounds.height() + .001)

    def test_directions_match_physical_positions_in_every_model(self):
        for family in catalog():
            model = Overlay(family)
            with self.subTest(family=family):
                self.assertLess(model.part_box("dpleft").center().x(), model.part_box("dpright").center().x())
                self.assertLess(model.part_box("dpup").center().y(), model.part_box("dpdown").center().y())

    def render_pair(self, family, first, second):
        view = ControllerView()
        view.resize(640, 420)
        view.set_input(family, first)
        view.show()
        APP.processEvents()
        idle = view.grab().toImage()
        view.set_input(family, second)
        APP.processEvents()
        changed = view.grab().toImage()
        model = view.model()
        view.close()
        view.deleteLater()
        APP.processEvents()
        return idle, changed, model

    def difference_bounds(self, a, b):
        av, bv = bytes(a.constBits()), bytes(b.constBits())
        pixels = [i // 4 for i in range(0, len(av), 4) if av[i:i+4] != bv[i:i+4]]
        if not pixels:
            return QRectF()
        xs, ys = [i % a.width() for i in pixels], [i // a.width() for i in pixels]
        return QRectF(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)

    def screen_rect(self, model, rect):
        target = fitted_rect(model.viewbox, QRectF(15, 8, 610, 404))
        scale = target.width() / model.viewbox.width()
        return QRectF(target.x() + (rect.x() - model.viewbox.x()) * scale,
                      target.y() + (rect.y() - model.viewbox.y()) * scale,
                      rect.width() * scale, rect.height() * scale)

    def test_button_highlight_only_changes_its_own_region(self):
        for family in catalog():
            with self.subTest(family=family):
                idle, changed, model = self.render_pair(family, Sample(connected=True), Sample(buttons={"a": True}, connected=True))
                delta = self.difference_bounds(idle, changed)
                self.assertFalse(delta.isEmpty())
                expected = self.screen_rect(model, model.part_box("a")).adjusted(-3, -3, 3, 3)
                self.assertTrue(expected.contains(delta), (family, expected, delta))

    def test_stick_moves_its_cap_without_altering_input_measurements(self):
        sample = Sample(axes={"leftx": 1., "lefty": 1.}, connected=True)
        idle, changed, _ = self.render_pair("dualsense", Sample(connected=True), sample)
        self.assertFalse(self.difference_bounds(idle, changed).isEmpty())
        self.assertEqual(sample.axes, {"leftx": 1., "lefty": 1.})

    def test_trigger_fill_grows_with_pressure(self):
        idle, low, _ = self.render_pair("dualsense", Sample(connected=True), Sample(axes={"lefttrigger": .25}, connected=True))
        _, high, _ = self.render_pair("dualsense", Sample(connected=True), Sample(axes={"lefttrigger": .75}, connected=True))
        def changes(im):
            a, b = bytes(idle.constBits()), bytes(im.constBits())
            return sum(a[i:i+4] != b[i:i+4] for i in range(0, len(a), 4))
        self.assertGreater(changes(high), changes(low))
        self.assertGreater(changes(low), 0)

    def test_gamecube_trigger_does_not_paint_over_the_face(self):
        idle, changed, model = self.render_pair("gamecube", Sample(connected=True), Sample(axes={"lefttrigger": 1}, connected=True))
        delta = self.difference_bounds(idle, changed)
        self.assertFalse(delta.isEmpty())
        expected = self.screen_rect(model, model.part_box("lefttrigger")).adjusted(-3, -3, 3, 3)
        self.assertTrue(expected.contains(delta))
