import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QByteArray, QEventLoop, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from controller_lab.backend import DemoBackend
from controller_lab.desktop_settings import DesktopSettings, clean_rules, choose_game_rule, executable_key
from controller_lab.emulation import Emulation
from controller_lab.storage import Store
from controller_lab.ui import Window
from controller_lab.windows_desktop import StopHotkey, hotkey_parts

APP = QApplication.instance() or QApplication([])


def rule(path=r"C:\Games\One\game.exe", profile="", guid="pad"):
    return clean_rules([dict(name="Game", executable=path, guid=guid, profile_id=profile)])[0]


class SettingsTests(unittest.TestCase):
    def test_desktop_settings_round_trip_without_touching_device_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            store.update("pad", deadzone=12)
            before = (Path(directory) / "preferences.json").read_bytes()
            settings = DesktopSettings(directory)
            settings.save(close_to_tray=True, stop_hotkey="Ctrl+Alt+F10", game_rules=[rule()])
            loaded = DesktopSettings(directory)
            self.assertTrue(loaded.data["close_to_tray"])
            self.assertEqual(loaded.data["stop_hotkey"], "Ctrl+Alt+F10")
            self.assertEqual((Path(directory) / "preferences.json").read_bytes(), before)

    def test_invalid_rule_save_does_not_replace_saved_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = DesktopSettings(directory)
            settings.save(setup_completed=True)
            before = settings.path.read_bytes()
            with self.assertRaises(ValueError):
                settings.save(game_rules=[rule(), rule()])
            self.assertEqual(settings.path.read_bytes(), before)
            self.assertTrue(settings.data["setup_completed"])

    def test_corrupt_file_uses_safe_defaults_with_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "desktop.json").write_text('{"game_rules":null}', encoding="utf-8")
            settings = DesktopSettings(directory)
            self.assertFalse(settings.data["game_profiles_enabled"])
            self.assertFalse(settings.data["close_to_tray"])
            self.assertTrue(settings.warning)

    def test_paths_are_full_case_insensitive_executable_paths(self):
        self.assertEqual(executable_key(r"C:\Games\ONE\..\Two\GAME.EXE"), r"c:\games\two\game.exe")
        for path in ("game.exe", "C:game.exe", r"C:\Games\game.bat", None):
            with self.subTest(path=path), self.assertRaises(ValueError):
                executable_key(path)

    def test_matching_does_not_confuse_identical_executable_names(self):
        first, second = rule(), rule(r"D:\Other\game.exe")
        selected, conflict = choose_game_rule([first, second], "pad", {second["executable"]})
        self.assertEqual(selected, second)
        self.assertFalse(conflict)

    def test_two_games_use_focus_then_keep_that_choice_on_alt_tab(self):
        first, second = rule(), rule(r"D:\Other\game.exe")
        running = {first["executable"], second["executable"]}
        self.assertEqual(choose_game_rule([first, second], "pad", running), (None, True))
        self.assertEqual(choose_game_rule([first, second], "pad", running, second["executable"])[0], second)
        self.assertEqual(choose_game_rule([first, second], "pad", running, "", second["executable"])[0], second)
        self.assertIsNone(choose_game_rule([first], "other-pad", running)[0])

    def test_temporary_profiles_do_not_change_disk_or_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            store.update("pad", deadzone=8)
            key = store.create_profile("pad", "Game")
            store.select_profile("pad", key)
            store.update("pad", deadzone=20)
            store.select_profile("pad", "")
            before = (Path(directory) / "preferences.json").read_bytes()
            store.override_profile("pad", key)
            self.assertEqual(store.device("pad")["deadzone"], 20)
            self.assertEqual(Store(directory).device("pad")["deadzone"], 8)
            self.assertEqual((Path(directory) / "preferences.json").read_bytes(), before)
            store.clear_profile_override("pad")
            self.assertEqual(store.device("pad")["deadzone"], 8)


class HotkeyTests(unittest.TestCase):
    def test_supported_shortcut_and_reserved_keys(self):
        text, modifiers, virtual = hotkey_parts("Ctrl+Alt+F11")
        self.assertEqual(text, "Ctrl+Alt+F11")
        self.assertEqual(modifiers, 0x4003)
        self.assertEqual(virtual, 0x7A)
        for text in ("F11", "Shift+A", "Meta+F10", "Ctrl+F12", "Ctrl+K, Ctrl+C", ""):
            with self.subTest(text=text), self.assertRaises(ValueError):
                hotkey_parts(text)

    def test_registration_conflict_preserves_previous_shortcut(self):
        hotkey = StopHotkey(APP, Mock(), enabled=False)
        hotkey.api = Mock()
        hotkey.api.RegisterHotKey.side_effect = [True, False]
        self.assertTrue(hotkey.configure("Ctrl+Alt+F11"))
        original = hotkey.identifier
        self.assertFalse(hotkey.configure("Ctrl+Alt+F10"))
        self.assertEqual(hotkey.identifier, original)
        self.assertEqual(hotkey.text, "Ctrl+Alt+F11")
        hotkey.api.UnregisterHotKey.assert_not_called()
        hotkey.close()
        hotkey.api.UnregisterHotKey.assert_called_once_with(None, original)

    def test_native_filter_only_stops_for_its_own_hotkey_message(self):
        callback = Mock()
        hotkey = StopHotkey(APP, callback, enabled=False)
        hotkey.identifier = 42
        message = wintypes.MSG()
        message.message, message.wParam = 0x0312, 41
        self.assertEqual(hotkey.nativeEventFilter(QByteArray(b"windows_dispatcher_MSG"), ctypes.addressof(message)), (False, 0))
        message.wParam = 42
        self.assertEqual(hotkey.nativeEventFilter(QByteArray(b"windows_dispatcher_MSG"), ctypes.addressof(message)), (True, 0))
        APP.processEvents()
        callback.assert_called_once()
        hotkey.unregister()


class Sink:
    def __init__(self, *args):
        self.closed, self.notifications = False, []
    def close(self):
        self.closed = True
    def write(self, sample):
        pass


class DesktopUITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.window = Window(DemoBackend("dualsense"), self.directory.name, demo=True)
        self.window.timer.stop()
        self.window.scan_timer.stop()
        self.guid = self.window.device.guid
        self.profile = self.window.store.create_profile(self.guid, "Game controls")
        self.rule = rule(profile=self.profile, guid=self.guid)

    def tearDown(self):
        self.window.quit_requested = True
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.directory.cleanup()

    def test_no_desktop_side_effects_or_output_in_demo(self):
        self.assertIsNone(self.window.tray)
        self.assertIsNone(self.window.stop_hotkey.identifier)
        self.assertFalse(self.window.game_timer.isActive())
        self.assertFalse(self.window.emulation.running)

    def test_game_switch_stops_output_and_game_exit_restores_manual_profile(self):
        window = self.window
        window.save_game_rules(True, [self.rule])
        window.emulation = Emulation(Sink)
        window.emulation.start(window.device.instance_id, window.sample, {})
        sink = window.emulation.sink
        window.apply_game_snapshot(dict(running=[self.rule["executable"]]))
        self.assertTrue(sink.closed)
        self.assertFalse(window.emulation.running)
        self.assertEqual(window.store.active_profile(self.guid), self.profile)
        self.assertEqual(window.store.profile_overrides[self.guid], self.profile)
        window.apply_game_snapshot(dict(running=[]))
        self.assertEqual(window.store.active_profile(self.guid), "")
        self.assertNotIn(self.guid, window.store.profile_overrides)

    def test_manual_selection_pauses_automatic_profile_until_game_closes(self):
        window = self.window
        window.save_game_rules(True, [self.rule])
        snapshot = dict(running=[self.rule["executable"]])
        window.apply_game_snapshot(snapshot)
        window.pause_game_profiles()
        window.store.select_profile(self.guid, "")
        window.apply_game_snapshot(snapshot)
        self.assertEqual(window.store.active_profile(self.guid), "")
        self.assertTrue(window.auto_manual_pause)
        window.apply_game_snapshot(dict(running=[]))
        window.apply_game_snapshot(snapshot)
        self.assertEqual(window.store.active_profile(self.guid), self.profile)

    def test_deleted_profile_never_silently_selects_default(self):
        window = self.window
        window.save_game_rules(True, [self.rule])
        window.store.delete_profile(self.guid, self.profile)
        window.apply_game_snapshot(dict(running=[self.rule["executable"]]))
        self.assertFalse(window.store.profile_overrides)
        self.assertIn("Missing game profile", window.game_profile_status.text())

    def test_process_scan_failure_keeps_current_profile(self):
        window = self.window
        window.save_game_rules(True, [self.rule])
        window.apply_game_snapshot(dict(running=[self.rule["executable"]]))
        window.apply_game_snapshot(dict(error="Access unavailable"))
        self.assertEqual(window.store.active_profile(self.guid), self.profile)

    def test_disabling_rules_restores_manual_profile(self):
        self.window.save_game_rules(True, [self.rule])
        self.window.apply_game_snapshot(dict(running=[self.rule["executable"]]))
        self.window.save_game_rules(False, [self.rule])
        self.assertEqual(self.window.store.active_profile(self.guid), "")

    def test_emergency_stop_neutralizes_output_without_restarting_it(self):
        window = self.window
        window.emulation = Emulation(Sink)
        window.emulation.start(window.device.instance_id, window.sample, {})
        sink = window.emulation.sink
        window.emergency_stop()
        self.assertTrue(sink.closed)
        self.assertFalse(window.emulation.running)
        window.tick()
        self.assertFalse(window.emulation.running)

    def test_repeated_game_scan_does_not_stop_output_or_restart_after_shortcut(self):
        window = self.window
        window.save_game_rules(True, [self.rule])
        snapshot = dict(running=[self.rule["executable"]])
        window.apply_game_snapshot(snapshot)
        window.emulation = Emulation(Sink)
        window.emulation.start(window.device.instance_id, window.sample, {})
        sink = window.emulation.sink
        window.apply_game_snapshot(snapshot)
        self.assertTrue(window.emulation.running)
        self.assertFalse(sink.closed)
        window.emergency_stop()
        window.apply_game_snapshot(snapshot)
        self.assertFalse(window.emulation.running)

    def test_stale_background_scan_cannot_apply_replaced_rules(self):
        window = self.window
        window.save_game_rules(True, [self.rule])
        callbacks = []
        with patch.object(window, "background", side_effect=lambda work, done: callbacks.append(done)):
            window.scan_game_profiles()
        window.save_game_rules(False, [])
        callbacks[0](dict(running=[self.rule["executable"]]))
        self.assertFalse(window.store.profile_overrides)
        self.assertFalse(window._game_scan_busy)

    def test_game_rule_for_the_already_selected_preset_does_not_interrupt_output(self):
        window = self.window
        same = rule(profile="", guid=self.guid)
        window.save_game_rules(True, [same])
        window.emulation = Emulation(Sink)
        window.emulation.start(window.device.instance_id, window.sample, {})
        sink = window.emulation.sink
        window.apply_game_snapshot(dict(running=[same["executable"]]))
        self.assertTrue(window.emulation.running)
        window.apply_game_snapshot(dict(running=[]))
        self.assertTrue(window.emulation.running)
        self.assertFalse(sink.closed)

    def test_background_work_delivers_results_to_the_gui(self):
        loop, delivered = QEventLoop(), []
        def complete(result):
            delivered.append(result)
            loop.quit()
        self.window.background(lambda: dict(ready=True), complete)
        QTimer.singleShot(1000, loop.quit)
        loop.exec()
        self.assertEqual(delivered, [dict(ready=True)])
        self.assertFalse(self.window._desktop_tasks)

    def test_close_to_tray_keeps_output_until_real_quit(self):
        window = self.window
        window.desktop.save(close_to_tray=True)
        window.tray, window.tray_stop = Mock(), Mock()
        window.emulation = Emulation(Sink)
        window.emulation.start(window.device.instance_id, window.sample, {})
        sink = window.emulation.sink
        event = QCloseEvent()
        with patch("controller_lab.desktop.QSystemTrayIcon.isSystemTrayAvailable", return_value=True):
            window.closeEvent(event)
        self.assertFalse(event.isAccepted())
        self.assertTrue(window.emulation.running)
        window.quit_requested = True
        window.closeEvent(QCloseEvent())
        self.assertTrue(sink.closed)
        self.assertTrue(window.desktop_closed)

    def test_no_tray_available_always_exits_instead_of_hiding(self):
        window = self.window
        window.desktop.save(close_to_tray=True)
        window.tray, window.tray_stop = Mock(), Mock()
        with patch("controller_lab.desktop.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            self.assertFalse(window.should_hide_on_close())

    def test_game_rules_dialog_cancel_does_not_save_draft(self):
        dialog = self.window.make_games_dialog()
        dialog.name.setText("My game")
        dialog.path.setText(r"C:\Games\Test\game.exe")
        dialog.put_rule()
        self.assertEqual(len(dialog.rules), 1)
        dialog.reject()
        self.assertEqual(self.window.desktop.data["game_rules"], [])

    def test_setup_check_in_demo_never_creates_virtual_output(self):
        dialog = self.window.make_setup_dialog()
        with patch.object(self.window, "check_virtual_outputs") as check:
            dialog.check_output()
        check.assert_not_called()
        self.assertIn("simulated", dialog.output_status.text())
        self.assertFalse(self.window.desktop.data["setup_completed"])
        dialog.finish()
        self.assertTrue(self.window.desktop.data["setup_completed"])

    def test_all_new_dialogs_build_and_fit_minimum_desktop(self):
        for factory in (self.window.make_setup_dialog, self.window.make_games_dialog, self.window.make_desktop_dialog):
            dialog = factory()
            dialog.show()
            APP.processEvents()
            self.assertLessEqual(dialog.width(), 1080)
            self.assertLessEqual(dialog.height(), 730)
            dialog.close()
