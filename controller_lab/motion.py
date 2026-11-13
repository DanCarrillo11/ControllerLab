"""Native, bounded interface motion; never changes controller measurements."""
from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation, QPropertyAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QGraphicsOpacityEffect, QLabel,
                              QProgressBar, QPushButton, QStackedWidget, QWidget)


from .theme import ACCENT, ACCENT_TEXT, BORDER, ELEVATED, INK, SECONDARY, SECONDARY_BLUE, SELECTION, SURFACE


def enabled():
    app = QApplication.instance()
    return bool(app and not app.property("reduce_motion") and
                (app.platformName() != "offscreen" or app.property("preview_motion")))


class AnimatedButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.hover = 0.0
        self.transition = QVariantAnimation(self)
        self.transition.setDuration(170)
        self.transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.transition.valueChanged.connect(self._frame)
        self.selection = 0.0
        self.selection_transition = QVariantAnimation(self)
        self.selection_transition.setDuration(180)
        self.selection_transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.selection_transition.valueChanged.connect(self._selection_frame)
        self.toggled.connect(self._selection_target)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _frame(self, value):
        self.hover = float(value)
        self.update()

    def _selection_frame(self, value):
        self.selection = float(value)
        self.update()

    def _selection_target(self, checked):
        self.selection_transition.stop()
        if not enabled() or not self.isVisible():
            self._selection_frame(float(checked))
            return
        self.selection_transition.setStartValue(self.selection)
        self.selection_transition.setEndValue(float(checked))
        self.selection_transition.start()

    def _target(self, value):
        self.transition.stop()
        if not enabled():
            self._frame(value)
            return
        self.transition.setStartValue(self.hover)
        self.transition.setEndValue(value)
        self.transition.start()

    def enterEvent(self, event):
        self._target(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._target(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        if self.objectName() in ("WorkspaceNav", "Nav"):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            segmented = self.objectName() == "Nav"
            rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
            if segmented:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(SURFACE))
                p.drawRoundedRect(rect, 9, 9)
            color = QColor(SELECTION)
            color.setAlpha(round(255 * self.selection))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(rect, 9, 9)
            hover_color = QColor(SECONDARY)
            hover_color.setAlpha(round(self.hover * 24))
            p.setBrush(hover_color)
            p.drawRoundedRect(rect, 9, 9)
            edge = QColor("#36516b")
            edge.setAlpha(round(145 * self.selection + 80 * self.hover * (1 - self.selection)))
            p.setPen(QPen(QColor(ACCENT_TEXT) if self.hasFocus() else edge, 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect, 9, 9)
            p.setPen(QColor(ACCENT_TEXT if self.isChecked() else SECONDARY))
            p.setFont(self.font())
            if segmented:
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())
            else:
                p.drawText(rect.adjusted(14, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
            return
        super().paintEvent(event)
        if self.hover > .001 and self.isEnabled():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            edge = QColor(ACCENT_TEXT if self.objectName() == "Primary" else SECONDARY)
            edge.setAlpha(round(125 * self.hover))
            painter.setPen(QPen(edge, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 9, 9)

    def hideEvent(self, event):
        self.transition.stop()
        self.selection_transition.stop()
        self.hover, self.selection = 0.0, float(self.isChecked())
        super().hideEvent(event)


class BentoCard(QFrame):
    """A passive information surface; only its actual controls respond to input."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class Switch(QCheckBox):
    """Accessible native checkbox behavior presented as an animated pill switch."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.position = 0.0
        self.transition = QVariantAnimation(self)
        self.transition.setDuration(170)
        self.transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.transition.valueChanged.connect(self._frame)
        self.toggled.connect(self._target)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _frame(self, value):
        self.position = float(value)
        self.update()

    def _target(self, checked):
        self.transition.stop()
        if not enabled() or not self.isVisible():
            self._frame(float(checked))
            return
        self.transition.setStartValue(self.position)
        self.transition.setEndValue(float(checked))
        self.transition.start()

    def sizeHint(self):
        return QSize(46 + self.fontMetrics().horizontalAdvance(self.text()), max(28, self.fontMetrics().height() + 6))

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, point):
        return self.rect().contains(point)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(1 if self.isEnabled() else .5)
        y = (self.height() - 20) / 2
        p.setPen(QPen(QColor(ACCENT_TEXT if self.hasFocus() else BORDER), 1))
        off, on = QColor(ELEVATED), QColor(ACCENT)
        p.setBrush(QColor(*(round(start + (end - start) * self.position)
                            for start, end in zip(off.getRgb()[:3], on.getRgb()[:3]))))
        p.drawRoundedRect(QRectF(1, y, 34, 20), 10, 10)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ffffff" if self.isChecked() else SECONDARY))
        p.drawEllipse(QRectF(4 + 14 * self.position, y + 3, 14, 14))
        p.setPen(QColor(INK))
        p.setFont(self.font())
        p.drawText(QRectF(46, 0, self.width() - 46, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text())

    def hideEvent(self, event):
        self.transition.stop()
        self.position = float(self.isChecked())
        super().hideEvent(event)


class AnimatedStack(QStackedWidget):
    """Dissolve the outgoing page; the real destination is immediately current."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cover, self.transition = None, None

    def finish_transition(self):
        if self.transition:
            self.transition.stop()
            self.transition.deleteLater()
            self.transition = None
        if self.cover:
            self.cover.hide()
            self.cover.deleteLater()
            self.cover = None

    def setCurrentIndex(self, index):
        if index == self.currentIndex() or not 0 <= index < self.count():
            return super().setCurrentIndex(index)
        self.finish_transition()
        previous = self.currentWidget()
        snapshot = previous.grab() if enabled() and self.isVisible() and previous else None
        super().setCurrentIndex(index)
        if snapshot is None or snapshot.isNull():
            return
        self.cover = QLabel(self)
        self.cover.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.cover.setPixmap(snapshot)
        self.cover.setGeometry(self.contentsRect())
        effect = QGraphicsOpacityEffect(self.cover)
        self.cover.setGraphicsEffect(effect)
        self.cover.show()
        self.cover.raise_()
        self.transition = QPropertyAnimation(effect, b"opacity", self)
        self.transition.setDuration(190)
        self.transition.setStartValue(1.0)
        self.transition.setEndValue(0.0)
        self.transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.transition.finished.connect(self.finish_transition)
        self.transition.start()

    def resizeEvent(self, event):
        self.finish_transition()
        super().resizeEvent(event)

    def hideEvent(self, event):
        self.finish_transition()
        super().hideEvent(event)


class AnimatedProgress(QProgressBar):
    """Smooth the visual track while value() always returns the actual target."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.display_value = 0.0
        self.transition = QVariantAnimation(self)
        self.transition.setDuration(95)
        self.transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.transition.valueChanged.connect(self._frame)
        self.setTextVisible(False)

    def _frame(self, value):
        self.display_value = float(value)
        self.update()

    def setValue(self, value):
        super().setValue(value)
        target = float(self.value())
        if self.transition.endValue() == target and self.transition.state() == QVariantAnimation.State.Running:
            return
        self.transition.stop()
        if not enabled() or not self.isVisible() or not self.isEnabled() or target <= self.minimum():
            self._frame(target)
            return
        self.transition.setStartValue(self.display_value)
        self.transition.setEndValue(target)
        self.transition.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(BORDER))
        painter.drawRoundedRect(rect, 3, 3)
        ratio = max(0, min(1, (self.display_value - self.minimum()) / max(1, self.maximum() - self.minimum())))
        if ratio > 0:
            clip = QPainterPath()
            clip.addRoundedRect(rect, 3, 3)
            painter.setClipPath(clip)
            rect.setWidth(rect.width() * ratio)
            painter.fillRect(rect, QColor(SECONDARY_BLUE if self.property("side") == "right" else ACCENT) if self.isEnabled() else QColor("#55555d"))

    def hideEvent(self, event):
        self.transition.stop()
        self.display_value = float(self.value())
        super().hideEvent(event)


class RevealPanel(QWidget):
    """Clip an expanding panel without squeezing its fields during the reveal."""
    def __init__(self, content):
        super().__init__()
        self.content = content
        content.setParent(self)

    def sizeHint(self):
        hint = self.content.sizeHint()
        layout = self.content.layout()
        height = layout.totalHeightForWidth(self.width()) if layout and layout.hasHeightForWidth() else hint.height()
        return QSize(hint.width(), max(height, self.content.minimumSizeHint().height()))

    def minimumSizeHint(self):
        return QSize(0, 0)

    def resizeEvent(self, event):
        self.content.setGeometry(0, 0, self.width(), self.sizeHint().height())
        super().resizeEvent(event)

    def showEvent(self, event):
        self.content.show()
        super().showEvent(event)


def reveal(widget, expanded):
    """Animate disclosures with cancellation and a stable restored height limit."""
    old = getattr(widget, "_reveal_animation", None)
    if old:
        old.stop()
        old.deleteLater()
        widget._reveal_animation = None
    limit = getattr(widget, "_reveal_limit", widget.maximumHeight())
    widget._reveal_limit = limit
    if not enabled() or not widget.parentWidget().isVisible():
        widget.setMaximumHeight(limit)
        widget.setVisible(expanded)
        return
    start = widget.height() if widget.isVisible() else 0
    widget.setVisible(True)
    target = min(limit, max(widget.minimumSizeHint().height(), widget.sizeHint().height())) if expanded else 0
    widget.setMaximumHeight(start)
    animation = QPropertyAnimation(widget, b"maximumHeight", widget)
    widget._reveal_animation = animation
    animation.setDuration(200)
    animation.setStartValue(start)
    animation.setEndValue(target)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    def finish():
        widget.setVisible(expanded)
        widget.setMaximumHeight(limit)
        widget._reveal_animation = None
        animation.deleteLater()
    animation.finished.connect(finish)
    animation.start()
