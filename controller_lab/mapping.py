"""Explicit app-local assignments for generic controllers and adapters."""
import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QWidget, QGridLayout, QComboBox, QCheckBox, QDialogButtonBox, QPushButton)
from .model import AXES, BUTTONS, button_names


class InputCapture:
    """Observe a changed axis or rising button/hat edge, without sending input."""
    def __init__(self, sample, kind):
        self.axes, self.buttons, self.hats, self.kind = sample.raw_axes, sample.raw_buttons, sample.hats, kind

    def observe(self, sample):
        if self.kind == "axis":
            changes = [(abs(value - old), i, old, value) for i, (old, value) in enumerate(zip(self.axes, sample.raw_axes))]
            if not changes:
                return None
            delta, index, old, value = max(changes)
            if delta < .4:
                return None
            return {"index": index, "signed": abs(old) > .5, "invert": old > .5 or abs(old) <= .5 and value < old}
        for i, value in enumerate(sample.raw_buttons):
            if value and (i >= len(self.buttons) or not self.buttons[i]):
                return f"b{i}"
        previous = self.hats
        self.buttons, self.hats = sample.raw_buttons, sample.hats
        for i, (x, y) in enumerate(sample.hats):
            oldx, oldy = previous[i] if i < len(previous) else (0, 0)
            for name, down, old in (("up", y > 0, oldy > 0), ("down", y < 0, oldy < 0),
                                    ("left", x < 0, oldx < 0), ("right", x > 0, oldx > 0)):
                if down and not old:
                    return f"h{i}:{name}"
        return None


class MappingDialog(QDialog):
    def __init__(self, device, family, current, parent=None, poller=None):
        super().__init__(parent)
        self.poller, self.capture = poller, None
        self.capture_timer = QTimer(self)
        self.capture_timer.timeout.connect(self.poll_capture)
        self.setWindowTitle("Input assignments · Controller Lab")
        self.resize(760, 680)
        self.result_mapping = None
        root = QVBoxLayout(self)
        title = QLabel("Map this controller")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        hint = QLabel("Assignments affect Controller Lab and its optional virtual output. Use Listen, move a control, then review its source and inversion before saving.")
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        root.addWidget(hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        grid = QGridLayout(content)
        self.axes, self.buttons = {}, {}
        for col, label in enumerate(("Axis", "Raw source", "Invert", "−1 to +1 trigger", "Capture")):
            grid.addWidget(QLabel(label), 0, col)
        for row, key in enumerate(AXES, 1):
            grid.addWidget(QLabel(key.replace("trigger", " trigger").replace("x", " X").replace("y", " Y").title()), row, 0)
            combo = QComboBox()
            combo.addItem("Unassigned", -1)
            for i in range(device.axes_count):
                combo.addItem(f"Axis {i}", i)
            invert, signed = QCheckBox(), QCheckBox()
            signed.setChecked(True)
            signed.setVisible(key.endswith("trigger"))
            source = current.get("axes", {}).get(key, {})
            source = source if isinstance(source, dict) else {}
            index = combo.findData(source.get("index", -1))
            combo.setCurrentIndex(max(0, index))
            invert.setChecked(bool(source.get("invert")))
            signed.setChecked(source.get("signed", True))
            grid.addWidget(combo, row, 1)
            grid.addWidget(invert, row, 2)
            grid.addWidget(signed, row, 3)
            listen = QPushButton("Listen")
            listen.setEnabled(poller is not None)
            listen.clicked.connect(lambda checked=False, k=key: self.start_capture("axis", k))
            grid.addWidget(listen, row, 4)
            self.axes[key] = (combo, invert, signed)
        labels = button_names(family)
        row = 8
        for key in BUTTONS:
            grid.addWidget(QLabel(f"{labels[key]}  ·  {key}"), row, 0)
            combo = QComboBox()
            combo.addItem("Unassigned", "")
            for i in range(device.buttons_count):
                combo.addItem(f"Button {i}", f"b{i}")
            for i in range(device.hats_count):
                for direction in ("up", "down", "left", "right"):
                    combo.addItem(f"Hat {i} · {direction}", f"h{i}:{direction}")
            combo.setCurrentIndex(max(0, combo.findData(current.get("buttons", {}).get(key, ""))))
            grid.addWidget(combo, row, 1, 1, 3)
            listen = QPushButton("Listen")
            listen.setEnabled(poller is not None)
            listen.clicked.connect(lambda checked=False, k=key: self.start_capture("button", k))
            grid.addWidget(listen, row, 4)
            self.buttons[key] = combo
            row += 1
        scroll.setWidget(content)
        root.addWidget(scroll)
        self.capture_status = QLabel("Listen captures one input at a time. Nothing is saved until you choose Save.")
        self.capture_status.setWordWrap(True)
        self.capture_status.setObjectName("Muted")
        root.addWidget(self.capture_status)
        footer = QHBoxLayout()
        reset = QPushButton("Use automatic mapping")
        reset.clicked.connect(self.reset_mapping)
        footer.addWidget(reset)
        footer.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        root.addLayout(footer)

    def start_capture(self, kind, key):
        sample = self.poller() if self.poller else None
        if sample is None or not sample.connected:
            self.capture_status.setText("No live input. Reconnect the controller before listening.")
            return
        self.capture = kind, key, InputCapture(sample, kind)
        self.capture_until = time.monotonic() + 10
        self.capture_status.setText("Listening for " + key + "… Move that axis or press that button. Keep other controls still.")
        self.capture_timer.start(30)

    def poll_capture(self):
        if self.capture is None:
            return
        sample = self.poller() if self.poller else None
        if sample is None or not sample.connected or time.monotonic() >= self.capture_until:
            self.capture_timer.stop()
            self.capture = None
            self.capture_status.setText("Listening ended. Check the connection or choose Listen again.")
            return
        kind, key, probe = self.capture
        result = probe.observe(sample)
        if result is None:
            return
        if kind == "axis":
            combo, invert, signed = self.axes[key]
            combo.setCurrentIndex(max(0, combo.findData(result["index"])))
            if key.endswith("trigger"):
                invert.setChecked(result["invert"])
                signed.setChecked(result["signed"])
        else:
            combo = self.buttons[key]
            combo.setCurrentIndex(max(0, combo.findData(result)))
        self.capture_timer.stop()
        self.capture = None
        self.capture_status.setText("Captured " + key + ". Review the assignment and choose Save when ready.")

    def done(self, result):
        self.capture_timer.stop()
        self.capture = None
        super().done(result)

    def reset_mapping(self):
        self.result_mapping = {}
        self.accept()

    def save(self):
        axes = {key: {"index": c.currentData(), "invert": i.isChecked(), "signed": s.isChecked()}
                for key, (c, i, s) in self.axes.items() if c.currentData() >= 0}
        buttons = {key: c.currentData() for key, c in self.buttons.items() if c.currentData()}
        self.result_mapping = {"axes": axes, "buttons": buttons} if axes or buttons else {}
        self.accept()
