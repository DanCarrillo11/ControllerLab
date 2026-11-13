"""Capture real native motion offscreen with simulated inputs, never hardware."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import json
import math
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from controller_lab.backend import DemoBackend
from controller_lab.ui import Window

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
app = QApplication([])
app.setStyle("Fusion")
app.setProperty("preview_motion", True)
frames, intervals, paints = [], [], {}
with tempfile.TemporaryDirectory(prefix="controllerlab-motion-") as temp:
    window = Window(DemoBackend(), temp, True)
    window.timer.stop()
    window.scan_timer.stop()
    window.show()
    app.processEvents()
    sample = window.sample
    for family in ("dualsense", "playstation", "xbox", "switch", "wii", "gamecube", "generic"):
        values = []
        for index in range(20):
            window.view.set_input(family, sample)
            start = time.perf_counter()
            window.view.grab()
            values.append((time.perf_counter() - start) * 1000)
        paints[family] = {"mean_ms": round(statistics.mean(values[2:]), 3), "max_ms": round(max(values[2:]), 3)}
    window.view.set_input("dualsense", sample)
    for index in range(150):
        if index == 45:
            window.navigate(1)
            observed = []
            window.pages.transition.valueChanged.connect(lambda value: observed.append(time.perf_counter()))
        elif index == 75:
            window.navigate(6)
        elif index == 90:
            window.emu_advanced_toggle.click()
        elif index == 120:
            window.navigate(0)
        elif index == 135:
            window.rumble_toggle.setChecked(True)
        angle = index * .09
        sample.axes.update(leftx=.6 * math.sin(angle), lefty=.6 * math.cos(angle),
            rightx=.1 * math.sin(angle), righty=.1 * math.cos(angle),
            lefttrigger=(math.sin(angle) + 1) / 2, righttrigger=(math.cos(angle) + 1) / 2)
        sample.buttons["a"] = index % 28 < 14
        sample.time += .02
        window.sample = sample
        window.draw_sample()
        QTest.qWait(16)
        frames.append(window.grab().toImage().scaled(960, 630, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    if len(observed) > 1:
        intervals = [(b - a) * 1000 for a, b in zip(observed, observed[1:])]
    window.close()
for index, frame in enumerate(frames):
    if not frame.save(str(output / f"frame-{index:03}.png"), "PNG"):
        raise OSError("Motion capture could not be saved")
evidence = {"simulated_inputs_only": True, "animations_enabled": True, "frames": len(frames),
            "animation_update_median_ms": round(statistics.median(intervals), 2) if intervals else None,
            "controller_paint_timings": paints, "scope": "Offscreen rendering on this PC; not an end-to-end hardware latency measurement"}
(output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print(json.dumps(evidence, indent=2))
