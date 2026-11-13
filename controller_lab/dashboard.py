"""Live stick positions and a truthful virtual-output signal path."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .theme import ACCENT, ACCENT_TEXT, BORDER, MUTED, SECONDARY, SECONDARY_BLUE, SIDEBAR, UI_FONT
from .motion import enabled
from .controller_art import controller_icon


class LiveSticks(QWidget):
    def __init__(self):
        super().__init__()
        self.values = {"left": None, "right": None}
        self.setMinimumHeight(80)
        self.setAccessibleName("Live left and right stick positions; missing axes remain unavailable")

    def set_sample(self, sample):
        for side in self.values:
            x, y = sample.axes.get(side + "x"), sample.axes.get(side + "y")
            self.values[side] = (x, y) if sample.connected and all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y)) else None
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for index, (side, value) in enumerate(self.values.items()):
            cx, cy, radius = self.width() * (.25 + index * .5), 29, 23
            p.setPen(QPen(QColor(BORDER), 1))
            p.setBrush(QColor(SIDEBAR))
            p.drawEllipse(QPointF(cx, cy), radius, radius)
            p.drawLine(QPointF(cx - radius, cy), QPointF(cx + radius, cy))
            p.drawLine(QPointF(cx, cy - radius), QPointF(cx, cy + radius))
            if value is not None:
                x, y = value
                length = max(1, math.hypot(x, y))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(ACCENT_TEXT if index == 0 else SECONDARY_BLUE))
                p.drawEllipse(QPointF(cx + x / length * radius, cy + y / length * radius), 4, 4)
            p.setPen(QColor(SECONDARY))
            p.setFont(QFont(UI_FONT, 8))
            p.drawText(QRectF(cx - 45, 57, 90, 18), Qt.AlignmentFlag.AlignCenter, side.title() if value is not None else "Unavailable")


class OutputRoute(QWidget):
    def __init__(self):
        super().__init__()
        self.source, self.source_name, self.target, self.running, self.demo = "generic", "No controller", "x360", False, False
        self.phase = 0
        self.setMinimumHeight(84)
        self.setAccessibleName("Physical controller to virtual controller signal path")
        self.clock = QTimer(self)
        self.clock.setInterval(16)
        self.clock.timeout.connect(self.advance)

    def set_state(self, device, target, running, demo=False):
        self.source = device.family if device else "generic"
        self.source_name = device.name if device else "Connect a controller"
        self.target, self.running, self.demo = target, running, demo
        if running and enabled() and self.isVisible():
            self.clock.start()
        else:
            self.clock.stop()
            self.phase = 0
        self.update()

    def advance(self):
        if not self.running or not enabled():
            self.clock.stop()
            self.phase = 0
        else:
            self.phase = (self.phase + .025) % 1
        self.update()

    def hideEvent(self, event):
        self.clock.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        if self.running and enabled():
            self.clock.start()
        super().showEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        w = self.width()
        p.setPen(QPen(QColor(BORDER), 1))
        p.setBrush(QColor(SIDEBAR))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 12, 12)
        for x, family, title, subtitle in ((18, self.source, self.source_name, "PHYSICAL INPUT"),
                (w * .60, "xbox" if self.target == "x360" else "playstation", "Xbox 360" if self.target == "x360" else "DualShock 4", "VIRTUAL OUTPUT")):
            controller_icon(family).paint(p, QRectF(x, 22, 48, 38).toRect())
            p.setFont(QFont(UI_FONT, 8))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(x + 59, 17, w * .33 - 65, 18), subtitle)
            p.setFont(QFont(UI_FONT, 9, QFont.Weight.DemiBold))
            p.setPen(QColor(ACCENT_TEXT))
            text = p.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, round(w * .33 - 65))
            p.drawText(QRectF(x + 59, 40, w * .33 - 65, 22), text)
        left, right, cy = w * .39, w * .57, 32
        p.setPen(QPen(QColor(ACCENT if self.running else "#55555d"), 1.5, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(left, cy), QPointF(right, cy))
        p.drawLine(QPointF(right - 5, cy - 4), QPointF(right, cy))
        p.drawLine(QPointF(right - 5, cy + 4), QPointF(right, cy))
        if self.running:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#6ee7b7"))
            p.drawEllipse(QPointF(left + (right - left) * self.phase, cy), 3, 3)
        p.setFont(QFont(UI_FONT, 8))
        p.setPen(QColor("#6ee7b7" if self.running else MUTED))
        p.drawText(QRectF(left - 10, 47, right - left + 20, 20), Qt.AlignmentFlag.AlignCenter,
                   "Forwarding" if self.running else "Preview only" if self.demo else "Stopped")
