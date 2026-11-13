"""Controller Lab entry point; demo/render modes never access real hardware."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from controller_lab import VERSION
from controller_lab.model import FAMILIES


def main():
    parser = argparse.ArgumentParser(description="Controller Lab · local gamepad diagnostics")
    parser.add_argument("--version", action="version", version=f"Controller Lab {VERSION}")
    parser.add_argument("--demo", action="store_true", help="Use simulated inputs without opening devices")
    parser.add_argument("--family", choices=FAMILIES, default="dualsense", help="Controller family for demo mode")
    parser.add_argument("--render-demo", metavar="PNG", help="Render a labeled synthetic preview without opening a window")
    parser.add_argument("--data-dir", type=Path, help="Override the local settings/report directory")
    parser.add_argument("--render-report", metavar="PNG", help="Export an explicitly simulated visual report offscreen")
    parser.add_argument("--render-dialog", choices=("setup", "desktop", "games", "profile"), help="Render a simulated dialog; use with --render-demo PNG")
    parser.add_argument("--desktop-check", metavar="JSON", help="Check native shortcut routing and process-path readback without input/output")
    parser.add_argument("--page", choices=("live", "sticks", "triggers", "raw", "sessions", "guided", "emulation", "settings", "games"), default="live")
    parser.add_argument("--virtual-check", metavar="JSON", help="Explicit neutral-output driver check; no physical inputs or vibration")
    parser.add_argument("--self-check", metavar="JSON", help="Check input backend and device discovery without vibration")
    args = parser.parse_args()
    if args.render_dialog and not args.render_demo:
        parser.error("--render-dialog requires --render-demo PNG")
    if args.self_check:
        from dataclasses import asdict
        from controller_lab.backend import SDLBackend
        from controller_lab.storage import atomic_write
        backend = SDLBackend()
        try:
            devices = backend.refresh()
            result = {"version": VERSION, "backend": "SDL2", "devices": [asdict(d) for d in devices],
                      "readable": [backend.poll(d.instance_id) is not None for d in devices],
                      "vibration_requested": False}
            atomic_write(args.self_check, json.dumps(result, indent=2))
        finally:
            backend.close()
        return 0
    if args.virtual_check:
        from controller_lab.emulation import VirtualSink, driver_status
        from controller_lab.storage import atomic_write
        result = {"version": VERSION, "drivers": driver_status(), "outputs": {}, "physical_inputs_forwarded": False, "vibration_requested": False}
        for target in ("x360", "ds4"):
            try:
                sink = VirtualSink(target)
                sink.close()
                result["outputs"][target] = {"status": "created_neutral_and_detached"}
            except Exception as exc:
                result["outputs"][target] = {"status": "unavailable", "error": str(exc)}
        result["ready"] = all(value["status"] == "created_neutral_and_detached" for value in result["outputs"].values())
        atomic_write(args.virtual_check, json.dumps(result, indent=2))
        return 0 if result["ready"] else 2
    if args.render_demo or args.render_report:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase, QFont
    from controller_lab.backend import DemoBackend, SDLBackend
    from controller_lab.ui import Window
    application = QApplication(sys.argv[:1])
    application.setApplicationName("ControllerLab")
    application.setOrganizationName("DanCarrillo")
    application.setStyle("Fusion")
    if args.desktop_check:
        from controller_lab.desktop_probe import check_desktop
        return check_desktop(application, args.desktop_check)
    # Offscreen Qt does not enumerate Windows fonts on every Windows host.
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ("segoeui.ttf", "seguisb.ttf", "seguisym.ttf", "consola.ttf"):
        if (fonts / name).is_file():
            QFontDatabase.addApplicationFont(str(fonts / name))
    application.setFont(QFont("Segoe UI", 10))
    demo = args.demo or bool(args.render_demo) or bool(args.render_report)
    temporary = tempfile.TemporaryDirectory(prefix="controllerlab-demo-") if demo and not args.data_dir else None
    data_dir = args.data_dir or (Path(temporary.name) if temporary else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ControllerLab")
    try:
        backend = DemoBackend(args.family) if demo else SDLBackend()
        window = Window(backend, data_dir, demo)
        if args.render_demo or args.render_report:
            window.resize(1280, 840)
            sample = backend.poll(100)
            fixed = dict(leftx=.23, lefty=-.18, rightx=.012, righty=-.009, lefttrigger=.32, righttrigger=.74)
            sample.axes = {k: fixed[k] for k in sample.axes}
            sample.buttons = {k: k == "a" for k in sample.buttons}
            sample.raw_axes = tuple(sample.axes.values())
            sample.raw_buttons = tuple(sample.buttons.values())
            window.sample = sample
            window.timer.stop()
            window.scan_timer.stop()
            window.view.model()  # Fail the check explicitly if an overlay is missing/invalid.
            window.show()
            application.processEvents()
            window.draw_sample()
            if args.render_report or args.page == "sessions":
                from controller_lab.model import Session
                from controller_lab.reports import export_png
                from copy import deepcopy
                import math
                session = Session(window.device, sample.time)
                for index in range(128):
                    point = deepcopy(sample)
                    point.time += index * .05
                    for side in ("left", "right"):
                        if side + "x" in point.axes:
                            point.axes[side + "x"] = .96 * math.cos(index * math.tau / 128)
                            point.axes[side + "y"] = .96 * math.sin(index * math.tau / 128)
                    session.add(point)
                report = window.decorate_report(session.report())
                if args.render_report:
                    path = Path(args.render_report)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    export_png(report, path)
                    window.close()
                    return 0
                window.store.save_report(report)
                window.refresh_history()
            if args.page == "guided":
                window.start_guided()
                window.guided.add(sample)
                window.update_guided()
            window.navigate(("live", "sticks", "triggers", "raw", "sessions", "guided", "emulation", "settings", "games").index(args.page))
            active_page = window.pages.currentIndex()
            window.primary_buttons[0 if active_page <= 3 else active_page].setFocus()
            application.processEvents()
            path = Path(args.render_demo)
            path.parent.mkdir(parents=True, exist_ok=True)
            rendered = window
            if args.render_dialog:
                rendered = {"setup": window.make_setup_dialog, "desktop": window.make_desktop_dialog,
                            "games": window.make_games_dialog, "profile": window.make_new_profile_dialog}[args.render_dialog]()
                if args.render_dialog == "profile":
                    rendered.name.setText("Racing")
                if args.render_dialog == "games":
                    rendered.rules = [dict(id="demo", name="Example game · simulated rule", executable=r"C:\Games\Example\game.exe",
                        guid=window.device.guid, profile_id="", enabled=True)]
                    rendered.refresh(0)
                rendered.show()
                application.processEvents()
            if not rendered.grab().save(str(path), "PNG"):
                raise OSError("Could not save preview")
            if rendered is not window:
                rendered.close()
            window.close()
            return 0
        window.show()
        return application.exec()
    finally:
        if temporary:
            temporary.cleanup()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        log_dir = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "ControllerLab"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "startup-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        if not getattr(sys, "frozen", False):
            raise
        if any(flag in sys.argv for flag in ("--self-check", "--render-demo", "--render-report", "--virtual-check", "--desktop-check")):
            raise SystemExit(1)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            application = QApplication.instance() or QApplication([])
            QMessageBox.critical(None, "Controller Lab could not start", "The app could not start. Details were saved to:\n" + str(log_dir / "startup-error.log"))
        finally:
            raise SystemExit(1)
