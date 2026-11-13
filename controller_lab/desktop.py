"""Desktop lifecycle, temporary per-game profiles and explicit setup checks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .desktop_settings import DesktopSettings, choose_game_rule
from .windows_desktop import StopHotkey, running_game_paths


class TaskSignals(QObject):
    finished = Signal(object)


class Task(QRunnable):
    def __init__(self, work):
        super().__init__()
        self.work, self.signals = work, TaskSignals()

    def run(self):
        try:
            result = self.work()
        except Exception as exc:
            result = {"error": str(exc)}
        self.signals.finished.emit(result)


def probe_virtual_output():
    """Use a disposable process so a failed client import cannot poison a retry."""
    with tempfile.TemporaryDirectory(prefix="controllerlab-output-check-") as directory:
        report = Path(directory) / "output.json"
        command = [sys.executable]
        if not getattr(sys, "frozen", False):
            command.append(str(Path(__file__).resolve().parents[1] / "app.py"))
        command.extend(["--virtual-check", str(report)])
        result = subprocess.run(command, capture_output=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if report.is_file():
            data = json.loads(report.read_text(encoding="utf-8"))
            data["ready"] = result.returncode == 0 and data.get("ready") is True
            return data
        return dict(ready=False, error="The virtual-output check could not complete (exit " + str(result.returncode) + ").")


class DesktopIntegration:
    def init_desktop(self):
        self.desktop = DesktopSettings(self.store.root)
        self.desktop_closed, self.quit_requested = False, False
        self._desktop_tasks, self._game_scan_busy = set(), False
        self._game_generation, self._profile_reloading = 0, False
        self.auto_rule, self.auto_manual_pause = None, False
        self.virtual_readiness = None
        self.native_desktop = not self.demo and os.name == "nt" and QApplication.platformName() == "windows"
        self.stop_hotkey = StopHotkey(QApplication.instance(), self.emergency_stop, self.native_desktop)
        if self.native_desktop:
            try:
                self.stop_hotkey.configure(self.desktop.data["stop_hotkey"], self.desktop.data["hotkey_enabled"])
            except ValueError as exc:
                self.stop_hotkey.error = str(exc)
        self.tray = None
        if self.native_desktop and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.windowIcon(), self)
            self.tray_menu = QMenu(self)
            self.tray_menu.addAction("Open Controller Lab", self.restore_from_tray)
            self.tray_stop = self.tray_menu.addAction("Stop emulation", self.emergency_stop)
            self.tray_menu.addSeparator()
            self.tray_menu.addAction("Game profiles…", self.open_game_profiles)
            self.tray_menu.addAction("Desktop settings…", self.open_desktop_settings)
            self.tray_menu.addSeparator()
            self.tray_menu.addAction("Quit Controller Lab", self.request_quit)
            self.tray.setContextMenu(self.tray_menu)
            self.tray.activated.connect(self.tray_activated)
            self.tray.show()
        self.minimize_tray_action.setEnabled(self.tray is not None)
        self.game_timer = QTimer(self)
        self.game_timer.setInterval(2000)
        self.game_timer.timeout.connect(self.scan_game_profiles)
        if self.native_desktop:
            self.game_timer.start()
        self.set_game_status("Game profiles off" if not self.desktop.data["game_profiles_enabled"] else "Waiting for a matching game")
        self.sync_desktop_status()
        self.build_preferences_pages()
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        if self.desktop.warning:
            self.notice(self.desktop.warning)
        if self.native_desktop:
            QTimer.singleShot(400, self.maybe_setup)

    def background(self, work, completed):
        task = Task(work)
        self._desktop_tasks.add(task)
        def finish(result):
            self._desktop_tasks.discard(task)
            if not self.desktop_closed:
                completed(result)
        task.signals.finished.connect(finish, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(task)

    def hotkey_status(self):
        if not self.desktop.data["hotkey_enabled"]:
            return "Global stop shortcut is disabled."
        if self.stop_hotkey.identifier is not None:
            return "Active: " + self.stop_hotkey.text + " · stops output while another app is focused."
        return self.stop_hotkey.error or "Global shortcut is inactive in this preview."

    def save_desktop_options(self, **options):
        from .windows_desktop import hotkey_parts
        hotkey_parts(options["stop_hotkey"])
        old = dict(self.desktop.data)
        if self.native_desktop and not self.stop_hotkey.configure(options["stop_hotkey"], options["hotkey_enabled"]):
            raise ValueError(self.stop_hotkey.error)
        try:
            self.desktop.save(**options)
        except (OSError, ValueError):
            if self.native_desktop:
                self.stop_hotkey.configure(old["stop_hotkey"], old["hotkey_enabled"])
            raise
        self.sync_desktop_status()
        self.notice("Desktop settings saved.")

    def sync_desktop_status(self):
        if not hasattr(self, "desktop"):
            return
        QApplication.instance().setProperty("reduce_motion", self.desktop.data["reduce_motion"])
        self.global_stop.setVisible(self.emulation.running)
        self.emu_stop_hint.setText(self.hotkey_status())
        if self.tray:
            running = self.emulation.running
            self.tray_stop.setEnabled(running)
            status = ("Xbox 360 active" if self.emulation.settings["target"] == "x360" else "DualShock 4 active") if running else "Output stopped"
            self.tray.setToolTip("Controller Lab · " + status + ("\nStop: " + self.stop_hotkey.text if self.stop_hotkey.identifier is not None else ""))

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore_from_tray()

    def restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def minimize_to_tray(self):
        if self.tray and self.tray.isVisible() and QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()

    def should_hide_on_close(self):
        return bool(hasattr(self, "desktop") and self.tray and self.tray.isVisible() and QSystemTrayIcon.isSystemTrayAvailable() and
            self.desktop.data["close_to_tray"] and not self.quit_requested and not QApplication.instance().isSavingSession())

    def handle_minimized(self):
        if hasattr(self, "desktop") and self.desktop.data["minimize_to_tray"] and self.isMinimized() and not self.desktop_closed:
            self.minimize_to_tray()

    def emergency_stop(self):
        running = self.emulation.running
        self.stop_emulation()
        if not running:
            self.notice("Emulation is already stopped.")

    def request_quit(self):
        self.quit_requested = True
        self.close()
        QApplication.instance().quit()

    def shutdown_desktop(self):
        if not hasattr(self, "desktop") or self.desktop_closed:
            return
        self.desktop_closed = True
        self.game_timer.stop()
        self.stop_hotkey.close()
        self.store.profile_overrides.clear()
        if self.tray:
            self.tray.hide()

    def make_desktop_dialog(self):
        from .desktop_dialogs import DesktopDialog
        return DesktopDialog(self)

    def make_games_dialog(self):
        from .desktop_dialogs import GameProfilesDialog
        return GameProfilesDialog(self)

    def make_setup_dialog(self):
        from .desktop_dialogs import SetupDialog
        return SetupDialog(self)

    def open_desktop_settings(self):
        self.restore_from_tray()
        self.navigate(7)
        self.settings_tabs.setCurrentIndex(0)

    def open_game_profiles(self):
        self.restore_from_tray()
        self.navigate(8)

    def open_setup(self):
        self.restore_from_tray()
        self.stop_emulation()
        self.make_setup_dialog().exec()

    def maybe_setup(self):
        if not self.desktop_closed and self.isVisible() and not self.desktop.data["setup_completed"]:
            if QApplication.activeModalWidget():
                QTimer.singleShot(1000, self.maybe_setup)
            else:
                self.open_setup()

    def check_virtual_outputs(self, completed):
        self.stop_emulation()
        def checked(result):
            self.virtual_readiness = result
            self.sync_emulation_ui()
            completed(result)
        self.background(probe_virtual_output, checked)

    def set_game_status(self, text):
        self.game_profile_status.setText(text)

    def desktop_device_changing(self):
        if hasattr(self, "desktop") and not self._profile_reloading:
            self._game_generation += 1
            self.store.profile_overrides.clear()
            self.auto_rule = None

    def reload_desktop_profile(self, reason):
        if not self.device:
            return
        iid = self.device.instance_id
        self.stop_emulation()
        self.cancel_guided()
        if self.session:
            self.finish_recording(reason)
        self.backend.stop(iid)
        index = next((i for i, d in enumerate(self.devices) if d.instance_id == iid), -1)
        self._profile_reloading = True
        try:
            self.device = None
            self.select_device(index)
        finally:
            self._profile_reloading = False
        self.notice(reason + ". Start emulation when ready.")

    def clear_game_override(self):
        before = self.store.active_profile(self.device.guid) if self.device else None
        self.store.profile_overrides.clear()
        self.auto_rule = None
        if self.device and before != self.store.active_profile(self.device.guid):
            self.reload_desktop_profile("Manual controller profile restored")

    def pause_game_profiles(self):
        if hasattr(self, "desktop") and self.desktop.data["game_profiles_enabled"]:
            self.auto_manual_pause = True
            self.store.profile_overrides.clear()
            self.auto_rule = None
            self.set_game_status("Game profiles paused for manual selection")

    def save_game_rules(self, enabled, rules):
        self.desktop.save(game_profiles_enabled=enabled, game_rules=rules)
        self._game_generation += 1
        self.auto_manual_pause = False
        self.clear_game_override()
        self.set_game_status("Waiting for a matching game" if enabled else "Game profiles off")

    def scan_game_profiles(self):
        if self.desktop_closed or QApplication.activeModalWidget() or self._game_scan_busy or self.pages.currentIndex() == 8:
            return
        if not self.desktop.data["game_profiles_enabled"] or not self.device:
            return
        rules = self.desktop.data["game_rules"]
        wanted = {r["executable"] for r in rules if r["enabled"] and r["guid"] == self.device.guid}
        if not wanted:
            self.apply_game_snapshot(dict(running=[], foreground="", error=""))
            return
        generation = self._game_generation
        self._game_scan_busy = True
        def scanned(result):
            self._game_scan_busy = False
            if generation == self._game_generation and not QApplication.activeModalWidget() and self.pages.currentIndex() != 8:
                self.apply_game_snapshot(result)
        self.background(lambda: running_game_paths(wanted), scanned)

    def apply_game_snapshot(self, snapshot):
        if not self.device or not self.desktop.data["game_profiles_enabled"]:
            return
        if snapshot.get("error"):
            self.set_game_status("Game detection unavailable: " + snapshot["error"])
            return
        running = set(snapshot.get("running", []))
        rules = self.desktop.data["game_rules"]
        matching = {r["executable"] for r in rules if r["enabled"] and r["guid"] == self.device.guid} & running
        if self.auto_manual_pause and matching:
            self.set_game_status("Game profiles paused. Save Game profiles to resume.")
            return
        if not matching:
            self.auto_manual_pause = False
        rule, conflict = choose_game_rule(rules, self.device.guid, running, snapshot.get("foreground", ""), self.auto_rule or "")
        if rule and rule["profile_id"] and rule["profile_id"] not in dict(self.store.profiles(self.device.guid)):
            self.clear_game_override()
            self.set_game_status("Missing game profile. Update the rule for " + rule["name"] + ".")
            return
        if rule:
            if self.store.profile_overrides.get(self.device.guid, None) != rule["profile_id"]:
                before = self.store.active_profile(self.device.guid)
                self.store.override_profile(self.device.guid, rule["profile_id"])
                if before != rule["profile_id"]:
                    self.reload_desktop_profile("Game profile selected: " + rule["name"])
            self.auto_rule = rule["executable"]
            self.set_game_status(rule["name"] + " · " + self.store.profile_name(self.device.guid))
        else:
            self.clear_game_override()
            self.set_game_status("Multiple games open. Focus one to select its profile." if conflict else "Waiting for a matching game")
