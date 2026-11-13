"""Small shared desktop layout primitives."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QFrame, QVBoxLayout
from .motion import AnimatedButton, BentoCard


def label(text="", style="", wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(style)
    widget.setWordWrap(wrap)
    return widget


class StateBadge(QLabel):
    """A compact status whose color follows its explicit connection/output text."""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setObjectName("StatusChip")
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText(text)

    def setText(self, text):
        lower = text.casefold()
        tone = "demo" if lower.startswith("demo") else "error" if "unavailable" in lower or "lost" in lower else "ready" if lower.startswith("connected") or lower.endswith(" active") else "neutral"
        if self.text() == text and self.property("tone") == tone:
            return
        super().setText(text)
        if self.property("tone") != tone:
            self.setProperty("tone", tone)
            self.style().unpolish(self)
            self.style().polish(self)


def button(text, slot=None, primary=False):
    widget = AnimatedButton(text)
    if primary:
        widget.setObjectName("Primary")
    if slot:
        widget.clicked.connect(slot)
    return widget


def card(title=""):
    frame = BentoCard()
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 17, 20, 17)
    layout.setSpacing(10)
    if title:
        layout.addWidget(label(title, "SectionTitle"))
    return frame, layout
