"""Shared dark workspace controls, palette and detected-device presentation."""
import math
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QStyledItemDelegate, QStyle

from .theme import (STYLE, CANVAS, SURFACE, ELEVATED, INK, SECONDARY, MUTED,
                    ACCENT, SELECTION, UI_FONT, load_fonts)


def apply_palette(app):
    load_fonts(app)
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, CANVAS), (QPalette.ColorRole.WindowText, INK),
                        (QPalette.ColorRole.Base, SURFACE), (QPalette.ColorRole.AlternateBase, ELEVATED),
                        (QPalette.ColorRole.Text, INK), (QPalette.ColorRole.Button, SURFACE),
                        (QPalette.ColorRole.ButtonText, INK), (QPalette.ColorRole.Highlight, ACCENT),
                        (QPalette.ColorRole.HighlightedText, "#ffffff"), (QPalette.ColorRole.PlaceholderText, MUTED)):
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#767682"))
    app.setPalette(palette)


class ElidedLabel(QLabel):
    """Keep long device names and held-button lists inside the available width."""
    def __init__(self, text="", style=""):
        super().__init__(text)
        self.setObjectName(style)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.contentsRect().width())
        painter.drawText(self.contentsRect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)


def ui_icon(kind, color=SECONDARY):
    pixmap = QPixmap(40, 40)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(2, 2)
    painter.setPen(QPen(QColor(color), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "settings":
        painter.drawEllipse(QRectF(5, 5, 10, 10))
        painter.drawEllipse(QRectF(8, 8, 4, 4))
        for index in range(8):
            angle = index * math.pi / 4
            painter.drawLine(round(10 + math.cos(angle) * 6), round(10 + math.sin(angle) * 6),
                             round(10 + math.cos(angle) * 8), round(10 + math.sin(angle) * 8))
    elif kind == "record":
        painter.drawEllipse(QRectF(5, 5, 10, 10))
        painter.setBrush(QColor(color))
        painter.drawEllipse(QRectF(8, 8, 4, 4))
    elif kind == "history":
        painter.drawArc(QRectF(3, 3, 14, 14), -45 * 16, 300 * 16)
        painter.drawLine(3, 3, 3, 8)
        painter.drawLine(3, 8, 7, 8)
        painter.drawLine(10, 6, 10, 10)
        painter.drawLine(10, 10, 13, 12)
    elif kind == "vibration":
        painter.drawRoundedRect(QRectF(7, 5, 6, 10), 2, 2)
        for x, sign in ((4, -1), (16, 1)):
            painter.drawLine(x, 6, x + sign * 2, 10)
            painter.drawLine(x + sign * 2, 10, x, 14)
    elif kind == "test":
        painter.drawEllipse(QRectF(4, 4, 12, 12))
        painter.drawEllipse(QRectF(8, 8, 4, 4))
        for x1, y1, x2, y2 in ((10, 1, 10, 5), (10, 15, 10, 19), (1, 10, 5, 10), (15, 10, 19, 10)):
            painter.drawLine(x1, y1, x2, y2)
    elif kind == "guided":
        painter.drawRoundedRect(QRectF(5, 4, 11, 14), 2, 2)
        painter.drawRoundedRect(QRectF(8, 2, 5, 4), 1, 1)
        painter.drawLine(8, 11, 10, 13)
        painter.drawLine(10, 13, 14, 9)
    elif kind == "emulation":
        painter.drawRoundedRect(QRectF(2, 5, 6, 10), 2, 2)
        painter.drawRoundedRect(QRectF(12, 5, 6, 10), 2, 2)
        painter.drawLine(6, 10, 14, 10)
        painter.drawLine(11, 7, 14, 10)
        painter.drawLine(14, 10, 11, 13)
    elif kind == "profiles":
        for y, x in ((5, 7), (10, 13), (15, 8)):
            painter.drawLine(3, y, 17, y)
            painter.setBrush(QColor(SURFACE))
            painter.drawEllipse(QRectF(x - 2, y - 2, 4, 4))
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


class DeviceDelegate(QStyledItemDelegate):
    def __init__(self, icon_provider, parent=None):
        super().__init__(parent)
        self.icon_provider = icon_provider

    def sizeHint(self, option, index):
        return QSize(200, 68)

    def paint(self, painter, option, index):
        device = index.data(Qt.ItemDataRole.UserRole)
        if device is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        rect = option.rect.adjusted(0, 3, -2, -3)
        painter.setPen(Qt.PenStyle.NoPen)
        if selected or option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(QColor(SELECTION if selected else ELEVATED))
            painter.drawRoundedRect(rect, 10, 10)
        if selected:
            painter.setBrush(QColor(ACCENT))
            painter.drawRoundedRect(QRectF(rect.x(), rect.y() + 13, 2, rect.height() - 26), 1, 1)
        tile = QRectF(rect.x() + 7, rect.y() + 13, 40, 34)
        painter.setBrush(QColor("#25486a" if selected else ELEVATED))
        painter.drawRoundedRect(tile, 8, 8)
        self.icon_provider(device.family).paint(painter, tile.adjusted(2, 2, -2, -2).toRect())
        painter.setPen(QColor(INK if selected else SECONDARY))
        painter.setFont(QFont(UI_FONT, 9))
        name = painter.fontMetrics().elidedText(device.name, Qt.TextElideMode.ElideRight, rect.width() - 62)
        painter.drawText(QRectF(rect.x() + 54, rect.y() + 10, rect.width() - 62, 21), Qt.AlignmentFlag.AlignVCenter, name)
        painter.setFont(QFont(UI_FONT, 8))
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(rect.x() + 54, rect.y() + 32, rect.width() - 62, 19), Qt.AlignmentFlag.AlignVCenter,
                         "Mapped controller" if device.mapped else "Raw inputs available")
        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setPen(QPen(QColor(ACCENT), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 9, 9)
        painter.restore()
