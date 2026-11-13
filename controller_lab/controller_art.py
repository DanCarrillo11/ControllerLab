"""Layered SVG controller overlays adapted from controller testing tools."""
from functools import lru_cache
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from PySide6.QtCore import QByteArray, QRectF, Qt, QPointF, QTimer
from PySide6.QtGui import QPainter, QPainterPath, QPixmap, QIcon, QColor, QPen, QPolygonF
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from .model import Sample
from .theme import ACCENT, ACCENT_TEXT, BORDER, SIDEBAR, SURFACE
from .motion import enabled

ART_ROOT = Path(__file__).resolve().parents[1] / "assets" / "overlays"


@lru_cache(maxsize=1)
def catalog():
    return json.loads((ART_ROOT / "layouts.json").read_text(encoding="utf-8"))


def fitted_rect(source, bounds):
    ratio = min(bounds.width() / source.width(), bounds.height() / source.height())
    width, height = source.width() * ratio, source.height() * ratio
    return QRectF(bounds.center().x() - width / 2, bounds.center().y() - height / 2, width, height)


@lru_cache(maxsize=16)
def controller_icon(family):
    """Use the detected device's existing artwork, independently of app branding."""
    family = family if family in catalog() else "generic"
    model = Overlay(family)
    pixmap = QPixmap(128, 96)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(2)
    painter = QPainter(pixmap)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
    model.full.render(painter, fitted_rect(model.viewbox, QRectF(2, 2, 60, 44)))
    painter.end()
    return QIcon(pixmap)


class Overlay:
    def __init__(self, family):
        self.spec = catalog()[family]
        # Change display colors only; preserve the attributed source artwork and geometry.
        data = (ART_ROOT / self.spec["file"]).read_bytes().replace(b"#22bfd4", ACCENT_TEXT.encode("ascii")).replace(b"#242426", SURFACE.encode("ascii"))
        self.full = QSvgRenderer(QByteArray(data))
        if not self.full.isValid():
            raise OSError(f"Controller overlay could not be loaded: {family}")
        self.viewbox = self.full.viewBoxF()
        self.boxes = {}
        for id in set(self.spec["parts"].values()) | set(self.spec["sticks"].values()):
            self.boxes[id] = self.full.transformForElement(id).mapRect(self.full.boundsOnElement(id))
        neutral = ET.fromstring(data)
        for node in neutral.iter():
            if node.get("id") in self.spec["sticks"].values():
                node.set("opacity", "0")
        self.base = QSvgRenderer(QByteArray(ET.tostring(neutral)))
        active = ET.fromstring(data)
        for node in active.iter():
            if node.tag.rsplit("}", 1)[-1] in ("path", "rect", "circle", "ellipse", "polygon", "polyline", "text", "tspan"):
                node.set("fill", ACCENT)
                node.set("fill-opacity", ".34")
                node.set("stroke", "#c4e0ff")
                node.set("stroke-opacity", "1")
        self.active = QSvgRenderer(QByteArray(ET.tostring(active)))

    def part_box(self, key):
        id = self.spec["parts"][key]
        rect = QRectF(self.boxes[id])
        if key in self.spec.get("visible", {}):
            x, y, w, h = self.spec["visible"][key]
            return QRectF(rect.x() + rect.width() * x, rect.y() + rect.height() * y,
                          rect.width() * w, rect.height() * h)
        if self.spec.get("split_dpad") and key.startswith("dp"):
            x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
            return {"dpup": QRectF(x + w / 3, y, w / 3, h / 2),
                    "dpdown": QRectF(x + w / 3, y + h / 2, w / 3, h / 2),
                    "dpleft": QRectF(x, y + h / 3, w / 2, h / 3),
                    "dpright": QRectF(x + w / 2, y + h / 3, w / 2, h / 3)}[key]
        return rect


class ControllerView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.family, self.sample = "dualsense", Sample(connected=False)
        self.models = {}
        self.grid_size, self.grid_points = None, QPolygonF()
        self.levels, self.targets = {}, {}
        self.visual_clock = QTimer(self)
        self.visual_clock.setInterval(16)
        self.visual_clock.timeout.connect(self.advance_visuals)
        self.setMinimumSize(360, 230)
        self.setAccessibleName("Vector controller overlay with live buttons and moving sticks")

    def model(self):
        family = self.family if self.family in catalog() else "generic"
        if family not in self.models:
            self.models[family] = Overlay(family)
        return self.models[family]

    def set_input(self, family, sample):
        changed = family != self.family
        self.family, self.sample = family, sample or Sample(connected=False)
        self.targets = {key: max(0., min(1., float(self.sample.axes.get(key, 0)))) if key.endswith("trigger")
                        else float(self.sample.buttons.get(key, False)) for key in self.model().spec["parts"]} if self.sample.connected else {}
        if changed or not self.sample.connected or not enabled() or not self.isVisible():
            self.levels = dict(self.targets)
            self.visual_clock.stop()
        elif any(abs(value - self.levels.get(key, 0)) > .001 for key, value in self.targets.items()):
            if not self.visual_clock.isActive():
                self.visual_clock.start()
        self.update()

    def advance_visuals(self):
        if not enabled() or not self.isVisible():
            self.levels = dict(self.targets)
            self.visual_clock.stop()
        else:
            moving = False
            for key, target in self.targets.items():
                current = self.levels.get(key, 0.)
                value = current + (target - current) * .42
                if abs(target - value) < .002:
                    value = target
                else:
                    moving = True
                self.levels[key] = value
            if not moving:
                self.visual_clock.stop()
        self.update()

    def hideEvent(self, event):
        self.visual_clock.stop()
        self.levels = dict(self.targets)
        super().hideEvent(event)

    def paintEvent(self, event):
        model = self.model()
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 12, 12)
        p.setClipPath(clip)
        size = (self.width(), self.height(), self.devicePixelRatioF())
        if size != self.grid_size:
            self.grid_size = size
            self.grid_points = QPolygonF([QPointF(x, y) for x in range(20, self.width() - 16, 28)
                                         for y in range(20, self.height() - 16, 28)])
        p.fillRect(self.rect(), QColor(SIDEBAR))
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawPoints(self.grid_points)
        p.setPen(QPen(QColor(BORDER), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(clip)
        p.restore()
        target = fitted_rect(model.viewbox, QRectF(self.rect()).adjusted(15, 8, -15, -8))
        p.translate(target.topLeft())
        p.scale(target.width() / model.viewbox.width(), target.height() / model.viewbox.height())
        p.translate(-model.viewbox.x(), -model.viewbox.y())
        p.setOpacity(1 if self.sample.connected else .38)
        model.base.render(p, model.viewbox)
        if self.sample.connected:
            for key, id in model.spec["parts"].items():
                value = self.levels.get(key, 0)
                if value <= .001:
                    continue
                p.save()
                if not key.endswith("trigger"):
                    p.setOpacity(value)
                clip = model.part_box(key)
                if key.endswith("trigger"):
                    clip.setTop(clip.bottom() - clip.height() * max(0, min(1, value)))
                p.setClipRect(clip, Qt.ClipOperation.IntersectClip)
                model.active.render(p, id, model.boxes[id])
                p.restore()
        for side, id in model.spec["sticks"].items():
            box = QRectF(model.boxes[id])
            x = self.sample.axes.get(side + "x", 0) if self.sample.connected else 0
            y = self.sample.axes.get(side + "y", 0) if self.sample.connected else 0
            length = math.hypot(x, y)
            if length > 1:
                x, y = x / length, y / length
            box.translate(x * box.width() * .16, y * box.height() * .16)
            renderer = model.active if self.sample.connected and self.sample.buttons.get(side + "stick", False) else model.full
            renderer.render(p, id, box)
        p.end()
