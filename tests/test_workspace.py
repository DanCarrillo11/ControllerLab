import os
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QDialog

from controller_lab.backend import DemoBackend
from controller_lab.desktop_settings import clean_rules
from controller_lab.emulation import Emulation
from controller_lab.ui import Window

APP = QApplication.instance() or QApplication([])


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.window = Window(DemoBackend("dualsense"), self.directory.name, demo=True)
        self.window.timer.stop()
        self.window.scan_timer.stop()

    def tearDown(self):
        self.window.quit_requested = True
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.directory.cleanup()

    def activate_fake_output(self):
        sink = Mock()
        sink.notifications = []
        self.window.emulation = Emulation(lambda *args: sink)
        self.window.emulation.start(self.window.device.instance_id, self.window.sample, {})
        self.window.sync_emulation_ui()
        return sink

    def test_page_navigation_preserves_output_and_keeps_stop_accessible(self):
        window = self.window
        sink = self.activate_fake_output()
        window.show()
        for page in (0, 5, 4, 7, 8, 6):
            window.navigate(page)
            APP.processEvents()
            self.assertTrue(window.emulation.running)
            self.assertTrue(window.global_stop.isVisible())
        window.global_stop.click()
        sink.close.assert_called_once()
        self.assertFalse(window.emulation.running)

    def test_test_navigation_remembers_the_last_diagnostic_page(self):
        self.window.navigate(2)
        self.window.navigate(6)
        self.window.primary_buttons[0].click()
        self.assertEqual(self.window.pages.currentIndex(), 2)

    def test_quick_profile_selection_persists_choice_and_stops_output(self):
        window = self.window
        guid = window.device.guid
        profile = window.store.create_profile(guid, "Alternative")
        window.sync_profile_picker()
        sink = self.activate_fake_output()
        window.profile_picker.setCurrentIndex(window.profile_picker.findData(profile))
        self.assertEqual(window.store.active_profile(guid), profile)
        sink.close.assert_called_once()
        self.assertFalse(window.emulation.running)

    def test_failed_profile_save_leaves_live_profile_and_output_intact(self):
        window = self.window
        guid = window.device.guid
        profile = window.store.create_profile(guid, "Alternative")
        window.sync_profile_picker()
        self.activate_fake_output()
        with patch.object(window.store, "select_profile", side_effect=OSError("Disk unavailable")):
            window.profile_picker.setCurrentIndex(window.profile_picker.findData(profile))
        self.assertEqual(window.store.active_profile(guid), "")
        self.assertEqual(window.profile_picker.currentData(), "")
        self.assertTrue(window.emulation.running)

    def test_settings_and_games_stay_in_the_main_window(self):
        self.window.open_desktop_settings()
        self.assertEqual(self.window.pages.currentIndex(), 7)
        self.assertFalse(self.window.desktop_form.isWindow())
        self.window.open_game_profiles()
        self.assertEqual(self.window.pages.currentIndex(), 8)
        self.assertFalse(self.window.games_form.isWindow())
        self.assertIsNone(APP.activeModalWidget())

    def test_save_includes_the_last_edited_game_without_a_separate_add_click(self):
        self.window.navigate(8)
        form = self.window.games_form
        form.name.setText("My game")
        form.path.setText(r"C:\Games\MyGame\game.exe")
        form.save()
        self.assertEqual(len(self.window.desktop.data["game_rules"]), 1)
        self.assertEqual(self.window.desktop.data["game_rules"][0]["name"], "My game")
        self.assertFalse(form.isHidden())

    def test_discard_restores_saved_game_rules_and_clears_the_editor(self):
        self.window.navigate(8)
        form = self.window.games_form
        form.name.setText("Draft")
        form.path.setText(r"C:\Games\Draft\game.exe")
        form.put_rule()
        form.reset_draft()
        self.assertFalse(form.rules)
        self.assertEqual(form.name.text(), "")
        self.assertFalse(self.window.desktop.data["game_rules"])

    def test_game_detection_does_not_change_profiles_while_editing_game_rules(self):
        window = self.window
        rules = clean_rules([dict(name="Game", guid=window.device.guid,
            executable=r"C:\Games\Game\game.exe", profile_id="")])
        window.save_game_rules(True, rules)
        window.navigate(8)
        with patch.object(window, "background") as worker:
            window.scan_game_profiles()
        worker.assert_not_called()

    def test_general_settings_save_does_not_close_the_embedded_form(self):
        self.window.navigate(7)
        form = self.window.desktop_form
        form.minimize.setChecked(True)
        form.save()
        self.assertTrue(self.window.desktop.data["minimize_to_tray"])
        self.assertFalse(form.isHidden())

    def test_cancelling_an_inline_editor_restores_values_without_hiding_the_page(self):
        self.window.navigate(7)
        settings = self.window.desktop_form
        settings.minimize.setChecked(True)
        settings.reject()
        self.assertFalse(settings.minimize.isChecked())
        self.assertFalse(settings.isHidden())
        self.window.navigate(8)
        games = self.window.games_form
        games.name.setText("Unsaved")
        games.reject()
        self.assertEqual(games.name.text(), "")
        self.assertFalse(games.isHidden())

    def test_scan_started_before_entering_game_profiles_cannot_apply_in_the_editor(self):
        window = self.window
        rules = clean_rules([dict(name="Game", guid=window.device.guid,
            executable=r"C:\Games\Game\game.exe", profile_id="")])
        window.save_game_rules(True, rules)
        callbacks = []
        with patch.object(window, "background", side_effect=lambda work, done: callbacks.append(done)):
            window.scan_game_profiles()
        window.navigate(8)
        callbacks[0](dict(running=[rules[0]["executable"]]))
        self.assertFalse(window.store.profile_overrides)

    def test_all_pages_and_expanded_emulation_fit_a_small_window(self):
        window = self.window
        window.resize(1080, 730)
        window.show()
        for page in range(9):
            window.navigate(page)
            APP.processEvents()
            self.assertEqual((window.width(), window.height()), (1080, 730))
            self.assertGreater(window.pages.width(), 650)
        window.navigate(6)
        window.emu_advanced_toggle.click()
        window.emu_help_toggle.click()
        APP.processEvents()
        self.assertTrue(window.pages.rect().contains(window.emu_start.mapTo(window.pages, window.emu_start.rect().bottomRight())))
        self.assertFalse(window.emu_advanced.isHidden())
        self.assertFalse(window.emu_help_scroll.isHidden())

    def test_new_workspace_pages_remain_available_after_controller_disconnects(self):
        self.window.devices = []
        self.window.select_device(-1)
        for page in (4, 6, 7, 8):
            self.window.navigate(page)
            self.assertEqual(self.window.workspace.currentIndex(), 1)
        self.assertFalse(self.window.profile_picker.isEnabled())
        self.assertFalse(self.window.games_form.add_button.isEnabled())
