"""Diagnostic plots; vector controller previews are rendered in controller_art."""
from collections import deque
import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont, QLinearGradient, QPolygonF
from PySide6.QtWidgets import QWidget

from .model import Sample, button_names, deadzone
from .theme import ACCENT_TEXT, INK, MUTED, BORDER, SELECTION, SIDEBAR

ACCENT = ACCENT_TEXT


from .controller_art import ControllerView


class StickPlot(QWidget):
    def __init__(self):
        super().__init__()
        self.points = deque(maxlen=900)
        self.value = (0.0, 0.0)
        self.radius = .08
        self.active = False
        self.setMinimumSize(200, 190)

    def set_value(self, x, y, active=True):
        self.active, self.value = active, (x, y)
        if active:
            self.points.append((x, y))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        r = min(self.width(), self.height()) * .41
        p.setPen(QPen(QColor(BORDER), 1))
        p.setBrush(QColor(SIDEBAR))
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r * .5, r * .5)
        p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
        p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
        p.setPen(QPen(QColor(ACCENT), 1, Qt.PenStyle.DashLine))
        p.setBrush(QColor(SELECTION))
        p.drawEllipse(QPointF(cx, cy), r * self.radius, r * self.radius)
        if self.active:
            p.setPen(QPen(QColor("#62aaff"), 2))
            for x, y in self.points:
                p.drawPoint(QPointF(cx + x * r, cy + y * r))
            x, y = self.value
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ACCENT))
            p.drawEllipse(QPointF(cx + x * r, cy + y * r), 5, 5)
            px, py = deadzone(x, y, self.radius)
            p.setPen(QPen(QColor("#6ee7b7"), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx + px * r, cy + py * r), 8, 8)
        p.end()


class Trace(QWidget):
    def __init__(self, color=ACCENT):
        super().__init__()
        self.values, self.color = deque(maxlen=240), color
        self.setMinimumHeight(100)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height() - 12
        p.setPen(QPen(QColor(BORDER), 1))
        for v in (.0, .5, 1.):
            p.drawLine(QPointF(0, 6 + h * (1 - v)), QPointF(w, 6 + h * (1 - v)))
        if self.values:
            path = QPainterPath()
            for i, v in enumerate(self.values):
                pt = QPointF(w - (len(self.values) - 1 - i) * w / 239, 6 + (1 - v) * h)
                path.moveTo(pt) if i == 0 else path.lineTo(pt)
            p.setPen(QPen(QColor(self.color), 2))
            p.drawPath(path)
        p.end()
