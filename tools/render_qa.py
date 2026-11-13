"""Render actual Qt pages with explicitly simulated data; no device access."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import math
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from controller_lab.backend import DemoBackend
from controller_lab.ui import Window
from controller_lab.model import Session, rest_summary
from controller_lab.mapping import MappingDialog

app = QApplication([])
app.setStyle("Fusion")
for name in ("segoeui.ttf", "seguisb.ttf", "seguisym.ttf", "consola.ttf"):
    path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
    if path.exists():
        QFontDatabase.addApplicationFont(str(path))
app.setFont(QFont("Segoe UI", 10))
output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "outputs" / "ui-qa"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    window = Window(DemoBackend(), tmp, True)
    window.timer.stop()
    window.scan_timer.stop()
    window.show()
    session = Session(window.device, window.sample.time)
    sample = window.sample
    for i in range(128):
        angle = (i + .2) * math.tau / 128
        x, y = .96 * math.cos(angle), .96 * math.sin(angle)
        sample.time += .08
        sample.axes.update(leftx=x, lefty=y, rightx=x * .95, righty=y * .95,
                           lefttrigger=(math.sin(angle) + 1) / 2, righttrigger=(math.cos(angle) + 1) / 2)
        sample.buttons["a"] = i % 20 < 8
        sample.raw_axes = tuple(sample.axes.values())
        sample.raw_buttons = tuple(sample.buttons.values())
        for side, observed in (("left", window.left_trigger_range), ("right", window.right_trigger_range)):
            value = sample.axes[side + "trigger"]
            observed[0], observed[1] = min(observed[0], value), max(observed[1], value)
        window.left_stats.add(x, y)
        window.right_stats.add(x * .95, y * .95)
        for side in ("left", "right"):
            window.stick_widgets[side][0].points.append((sample.axes[side + "x"], sample.axes[side + "y"]))
        session.add(sample)
        window.sample = sample
        window.draw_sample()
    report = session.report()
    report["demo"] = True
    window.store.save_report(report)
    window.refresh_history()
    for size, w, h in (("standard", 1280, 840), ("minimum", 1080, 730)):
        window.resize(w, h)
        for i, name in enumerate(("live", "sticks", "triggers", "raw", "sessions", "guided", "emulation", "settings", "games")):
            if i == 5:
                window.start_guided()
                window.guided.add(window.sample)
                window.update_guided()
            elif i == 6:
                window.cancel_guided()
            window.navigate(i)
            window.primary_buttons[0 if i <= 3 else i].setFocus()
            app.processEvents()
            window.draw_sample()
            if not window.grab().save(str(output / f"{size}-{name}.png"), "PNG"):
                raise OSError("Screenshot could not be saved")
        window.navigate(0)
        window.rumble_toggle.setChecked(True)
        app.processEvents()
        window.grab().save(str(output / f"{size}-vibration.png"), "PNG")
        window.rumble_toggle.setChecked(False)
        window.navigate(6)
        window.emu_advanced_toggle.setChecked(True)
        window.emu_help_toggle.setChecked(True)
        app.processEvents()
        window.grab().save(str(output / f"{size}-emulation-expanded.png"), "PNG")
        window.emu_advanced_toggle.setChecked(False)
        window.emu_help_toggle.setChecked(False)
        window.navigate(7)
        for index, name in ((1, "controller"), (2, "help")):
            window.settings_tabs.setCurrentIndex(index)
            app.processEvents()
            window.grab().save(str(output / f"{size}-settings-{name}.png"), "PNG")
        window.settings_tabs.setCurrentIndex(0)
    from controller_lab.reports import export_png
    export_png(report, output / "visual-report.png")
    dialog = MappingDialog(window.device, window.family, {}, window, lambda: window.sample)
    dialog.show()
    app.processEvents()
    dialog.grab().save(str(output / "input-assignments.png"), "PNG")
    dialog.close()
    from controller_lab.profiles import ProfilesDialog
    window.store.create_profile(window.device.guid, "Desktop")
    window.store.create_profile(window.device.guid, "Racing")
    profiles = ProfilesDialog(window.store, window.device.guid, window)
    profiles.show()
    app.processEvents()
    profiles.grab().save(str(output / "profiles.png"), "PNG")
    profiles.close()
    window.close()
    class DisconnectedBackend(DemoBackend):
        def refresh(self):
            return []
    empty = Window(DisconnectedBackend(), tmp, True)
    empty.timer.stop()
    empty.scan_timer.stop()
    empty.show()
    app.processEvents()
    empty.grab().save(str(output / "empty.png"), "PNG")
    empty.navigate(4)
    app.processEvents()
    empty.grab().save(str(output / "disconnected-sessions.png"), "PNG")
    empty.close()
print("Rendered nine pages and vibration at two sizes, mapping capture, profiles, visual report and disconnected states")
