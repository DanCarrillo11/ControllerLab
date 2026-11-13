import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from controller_lab.backend import DemoBackend
from controller_lab.model import Device, Sample, FAMILIES
from controller_lab.ui import Window
from controller_lab.controller_art import controller_icon


APP = QApplication.instance() or QApplication([])
APP.setStyle("Fusion")
for name in ("segoeui.ttf", "seguisb.ttf", "seguisym.ttf", "consola.ttf"):
    font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))


class FakeBackend:
    def __init__(self, mapped=True):
        self.devices = [Device(7, "Test DualSense", "test-pad", "dualsense", "fixture", mapped, 6, 17, 0)]
        self.sample = Sample(time.monotonic(), dict(leftx=.02, lefty=-.01, rightx=0, righty=0,
             lefttrigger=0, righttrigger=1) if mapped else {}, {"a": True} if mapped else {},
             (.02, -.01, 0, 0, -1, 1), (True,) + (False,) * 16, (), "unknown", mapped)
        self.rumbles = []

    def refresh(self):
        return self.devices[:]

    def poll(self, iid):
        return self.sample if any(d.instance_id == iid for d in self.devices) else None

    def rumble(self, *args):
        self.rumbles.append(args)
        return True

    def stop(self, *args):
        pass

    def close(self):
        pass


class UITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.backend = FakeBackend()
        self.window = Window(self.backend, self.tmp.name)
        self.window.timer.stop()
        self.window.scan_timer.stop()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.tmp.cleanup()

    def test_model_and_diagram_are_detected_without_vibration(self):
        self.assertEqual(self.window.family, "dualsense")
        self.assertEqual(self.window.view.family, "dualsense")
        self.assertEqual(self.backend.rumbles, [])
        self.assertEqual(self.window.power_label.text(), "Not reported")

    def test_all_overlays_are_available_and_override_persists(self):
        for action in self.window.overlay_group.actions():
            if action.data() in FAMILIES:
                self.window.set_overlay(action)
                self.assertEqual(self.window.view.family, action.data())
        self.assertEqual(self.window.store.device("test-pad")["overlay"], "generic")
        self.assertEqual(self.window.sample.axes["leftx"], .02)

    def test_connected_device_thumbnail_changes_with_selected_controller(self):
        initial = self.window.controller_avatar.pixmap().toImage()
        self.assertEqual(initial, controller_icon("dualsense").pixmap(48, 36).toImage())
        self.backend.devices.append(Device(8, "Xbox controller", "xbox-fixture", "xbox", "fixture", True))
        self.window.refresh_devices()
        self.window.select_device(1)
        selected = self.window.controller_avatar.pixmap().toImage()
        self.assertEqual(selected, controller_icon("xbox").pixmap(48, 36).toImage())
        self.assertNotEqual(initial, selected)

    def test_manual_overlay_does_not_misidentify_the_connected_device_thumbnail(self):
        original = self.window.controller_avatar.pixmap().toImage()
        action = next(action for action in self.window.overlay_group.actions() if action.data() == "switch")
        self.window.set_overlay(action)
        self.assertEqual(self.window.view.family, "switch")
        self.assertEqual(self.window.controller_avatar.pixmap().toImage(), original)
        self.assertIn("DualSense", self.window.controller_avatar.toolTip())

    def test_hot_unplug_saves_recording_and_clears_live_state(self):
        self.window.toggle_recording()
        self.backend.sample.time += 1
        self.window.tick()
        self.backend.devices = []
        self.window.refresh_devices()
        self.assertIsNone(self.window.session)
        self.assertFalse(self.window.sample.connected)
        self.assertFalse(self.window.record_button.isEnabled())
        self.assertEqual(len(self.window.store.reports()), 1)
        self.assertEqual(self.window.workspace.currentIndex(), 0)

    def test_history_can_be_opened_with_no_controller(self):
        self.backend.devices = []
        self.window.refresh_devices()
        self.window.navigate(4)
        self.assertEqual(self.window.workspace.currentIndex(), 1)
        self.assertEqual(self.window.pages.currentIndex(), 4)
        self.assertFalse(self.window.record_button.isEnabled())
        self.window.navigate(0)
        self.assertEqual(self.window.workspace.currentIndex(), 0)

    def test_switching_controller_ends_old_recording(self):
        self.window.toggle_recording()
        self.backend.sample.time += 1
        self.window.tick()
        self.backend.devices.append(Device(8, "Other", "other-guid", "xbox", "fixture", True))
        self.window.refresh_devices()
        self.window.select_device(1)
        self.assertEqual(self.window.family, "xbox")
        self.assertIsNone(self.window.session)
        self.assertEqual(self.window.store.reports()[0][1]["device"]["guid"], "test-pad")

    def test_rest_capture_uses_original_values_despite_deadzone_preview(self):
        self.window.deadzone_slider.setValue(30)
        self.window.start_rest()
        self.backend.sample.time = self.window.rest_start + 5.1
        self.window.tick()
        self.assertIsNone(self.window.rest_start)
        self.assertAlmostEqual(self.window.rest_results["left"]["mean_x"], .02)
        self.assertGreater(self.window.rest_results["left"]["mean_radius"], 0)

    def test_reset_cancels_inflight_rest_measurement(self):
        self.window.start_rest()
        self.window.reset_measurements()
        self.assertIsNone(self.window.rest_start)
        self.assertEqual(self.window.rest_results, {})

    def test_rumble_requires_explicit_button_action(self):
        self.window.rumble(1, 0)
        self.assertEqual(len(self.backend.rumbles), 1)
        self.assertEqual(self.backend.rumbles[0], (7, .45, 0, 600))

    def test_vibration_drawer_opens_without_playing_an_effect(self):
        self.assertTrue(self.window.rumble_panel.isHidden())
        self.window.rumble_toggle.click()
        APP.processEvents()
        self.assertFalse(self.window.rumble_panel.isHidden())
        self.assertEqual(self.backend.rumbles, [])
        self.window.rumble_toggle.click()
        self.assertTrue(self.window.rumble_panel.isHidden())

    def test_vibration_drawer_fits_minimum_window(self):
        self.window.resize(1080, 730)
        self.window.show()
        self.window.rumble_toggle.click()
        APP.processEvents()
        self.assertEqual((self.window.width(), self.window.height()), (1080, 730))
        self.assertGreaterEqual(self.window.view.width(), self.window.view.minimumWidth())
        for b in self.window.rumble_buttons:
            self.assertTrue(self.window.rumble_panel.rect().contains(b.mapTo(self.window.rumble_panel, b.rect().bottomRight())))

    def test_unplug_clears_the_visible_device_summary(self):
        self.window.rumble_toggle.click()
        self.backend.devices = []
        self.window.refresh_devices()
        self.assertEqual(self.window.device_count.text(), "0")
        self.assertEqual(self.window.power_label.text(), "—")
        self.assertEqual(self.window.input_label.text(), "No live inputs")
        self.assertFalse(self.window.rumble_toggle.isChecked())
        self.assertFalse(self.window.rumble_toggle.isEnabled())
        self.assertTrue(self.window.controller_avatar.pixmap().isNull())

    def test_long_controller_name_fits_and_remains_available_in_tooltip(self):
        long_name = "USB adapter / " + "A very long controller name " * 12
        self.backend.devices = [Device(18, long_name, "long-guid", "generic", "fixture", False)]
        self.window.refresh_devices()
        self.window.resize(1080, 730)
        self.window.show()
        APP.processEvents()
        self.assertEqual(self.window.width(), 1080)
        self.assertEqual(self.window.controller_title.text(), long_name)
        self.assertEqual(self.window.controller_title.toolTip(), long_name)
        self.assertEqual(self.window.device_list.count(), 1)

    def test_unknown_device_does_not_invent_zero_readings(self):
        self.window.close()
        self.backend = FakeBackend(False)
        self.window = Window(self.backend, self.tmp.name)
        self.window.timer.stop()
        self.window.scan_timer.stop()
        self.assertEqual(self.window.stick_widgets["left"][1].text(), "Not mapped")
        self.assertEqual(self.window.trigger_widgets["left"][0].text(), "Not mapped")

    def test_live_summary_distinguishes_zero_from_a_missing_trigger(self):
        self.window.sample.axes["lefttrigger"] = 0
        self.window.sample.axes.pop("righttrigger", None)
        self.window.draw_sample()
        left, left_bar = self.window.live_triggers["left"]
        right, right_bar = self.window.live_triggers["right"]
        self.assertEqual(left.text(), "0%")
        self.assertTrue(left_bar.isEnabled())
        self.assertEqual(right.text(), "—")
        self.assertFalse(right_bar.isEnabled())

    def test_input_loss_clears_live_readouts_before_the_next_device_scan(self):
        self.window.sample.axes["lefttrigger"] = .9
        self.window.draw_sample()
        self.assertEqual(self.window.live_triggers["left"][0].text(), "90%")
        self.backend.devices = []
        self.window.tick()
        self.assertEqual(self.window.event_label.text(), "No live input")
        self.assertTrue(all(value.text() == "—" and not bar.isEnabled()
                            for value, bar in self.window.live_triggers.values()))

    def test_all_pages_fit_minimum_window_size(self):
        self.window.resize(1080, 730)
        self.window.show()
        for index in range(5):
            self.window.navigate(index)
            APP.processEvents()
            self.assertEqual(self.window.width(), 1080)
            self.assertEqual(self.window.height(), 730)
            self.assertGreater(self.window.pages.width(), 650)

    def test_mapping_dialog_cannot_apply_assignments_to_replacement_device(self):
        from PySide6.QtWidgets import QDialog
        replacement = Device(99, "Replacement", "replacement-guid", "generic", "fixture", False)
        window = self.window
        class Dialog:
            result_mapping = {"buttons": {"a": "b0"}}
            def __init__(self, *args):
                pass
            def exec(self):
                window.device = replacement
                return QDialog.DialogCode.Accepted
        with patch("controller_lab.ui.MappingDialog", Dialog):
            window.map_inputs()
        self.assertEqual(window.store.device("replacement-guid"), {})
        self.assertEqual(window.mapping, {})


class RenderTests(unittest.TestCase):
    def test_every_family_renders_a_distinct_diagram(self):
        hashes = set()
        import hashlib
        for family in FAMILIES:
            with tempfile.TemporaryDirectory() as path:
                window = Window(DemoBackend(family), path, True)
                window.timer.stop()
                window.scan_timer.stop()
                window.show()
                APP.processEvents()
                image = window.view.grab().toImage()
                digest = hashlib.sha256(bytes(image.constBits())).hexdigest()
                self.assertNotIn(digest, hashes, family)
                hashes.add(digest)
                window.close()
                window.deleteLater()
                APP.processEvents()
