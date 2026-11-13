import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QDialog
from controller_lab.backend import DemoBackend
from controller_lab.emulation import Emulation
from controller_lab.storage import Store
from controller_lab.ui import Window
from controller_lab.workspace import NEW_PROFILE, MANAGE_PROFILES

APP = QApplication.instance() or QApplication([])


class ProfileCreationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.window = Window(DemoBackend("dualsense"), self.directory.name, demo=True)
        self.window.timer.stop()
        self.window.scan_timer.stop()
        self.guid = self.window.device.guid

    def tearDown(self):
        self.window.quit_requested = True
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.directory.cleanup()

    def fake_output(self):
        sink = Mock()
        sink.notifications = []
        self.window.emulation = Emulation(lambda *args: sink)
        self.window.emulation.start(self.window.device.instance_id, self.window.sample, {})
        return sink

    def test_create_copies_visible_unsaved_settings_and_preserves_default(self):
        window = self.window
        window.emu_deadzone.setValue(23)
        window.emu_bindings = {"a": "x", "x": "a"}
        key = window.create_profile_from_current("  Swapped buttons  ")
        self.assertEqual(window.profile_picker.currentData(), key)
        self.assertEqual(window.store.profile_name(self.guid), "Swapped buttons")
        loaded = Store(self.directory.name)
        self.assertEqual(loaded.active_profile(self.guid), key)
        self.assertAlmostEqual(loaded.device(self.guid)["emulation"]["deadzone"], .23)
        self.assertEqual(loaded.device(self.guid)["emulation"]["buttons"], {"a": "x", "x": "a"})
        window.profile_picker.setCurrentIndex(0)
        self.assertEqual(window.emu_deadzone.value(), 8)
        window.profile_picker.setCurrentIndex(window.profile_picker.findData(key))
        self.assertEqual(window.emu_deadzone.value(), 23)

    def test_changes_saved_to_one_profile_do_not_replace_another(self):
        window = self.window
        first = window.create_profile_from_current("Racing")
        window.emu_deadzone.setValue(19)
        window.save_emulation_settings()
        second = window.create_profile_from_current("Platformers")
        window.emu_deadzone.setValue(4)
        window.save_emulation_settings()
        window.profile_picker.setCurrentIndex(window.profile_picker.findData(first))
        self.assertEqual(window.emu_deadzone.value(), 19)
        window.profile_picker.setCurrentIndex(window.profile_picker.findData(second))
        self.assertEqual(window.emu_deadzone.value(), 4)

    def test_successful_creation_stops_output_without_starting_the_new_configuration(self):
        sink = self.fake_output()
        self.window.create_profile_from_current("New controls")
        sink.close.assert_called_once()
        self.assertFalse(self.window.emulation.running)

    def test_failed_creation_is_atomic_and_keeps_current_output_running(self):
        sink = self.fake_output()
        with patch("controller_lab.storage.atomic_write", side_effect=OSError("Disk unavailable")):
            with self.assertRaises(OSError):
                self.window.create_profile_from_current("Racing")
        self.assertEqual(self.window.store.profiles(self.guid), [])
        self.assertEqual(self.window.store.active_profile(self.guid), "")
        self.assertTrue(self.window.emulation.running)
        sink.close.assert_not_called()

    def test_action_items_do_not_become_the_selected_saved_profile(self):
        for token, method in ((NEW_PROFILE, "new_controller_profile"), (MANAGE_PROFILES, "open_profiles")):
            with self.subTest(token=token), patch.object(self.window, method) as action:
                self.window.profile_picker.setCurrentIndex(self.window.profile_picker.findData(token))
                action.assert_called_once()
                self.assertEqual(self.window.profile_picker.currentData(), "")
                self.assertEqual(self.window.store.active_profile(self.guid), "")

    def test_cancel_creation_does_not_write_or_stop_output(self):
        sink = self.fake_output()
        dialog = self.window.make_new_profile_dialog()
        dialog.name.setText("Not saved")
        dialog.reject()
        self.assertEqual(self.window.store.profiles(self.guid), [])
        self.assertTrue(self.window.emulation.running)
        sink.close.assert_not_called()

    def test_duplicate_name_can_be_corrected_without_closing_the_dialog(self):
        self.window.create_profile_from_current("Racing")
        dialog = self.window.make_new_profile_dialog()
        self.assertFalse(dialog.create_button.isEnabled())
        dialog.name.setText(" racing ")
        dialog.create()
        self.assertIn("already exists", dialog.error.text())
        self.assertIsNone(dialog.profile_id)
        dialog.name.setText("Platformers")
        dialog.create()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(self.window.store.profile_name(self.guid), "Platformers")

    def test_creation_is_rejected_if_the_controller_changes_while_naming(self):
        dialog = self.window.make_new_profile_dialog()
        self.window.devices = []
        self.window.select_device(-1)
        dialog.name.setText("Racing")
        dialog.create()
        self.assertIn("controller changed", dialog.error.text())
        self.assertIsNone(dialog.profile_id)
        self.assertEqual(self.window.store.profiles(self.guid), [])

    def test_recording_keeps_its_original_profile_when_a_new_one_is_activated(self):
        window = self.window
        window.toggle_recording()
        window.tick()
        window.create_profile_from_current("After recording")
        report = window.store.reports()[0][1]
        self.assertEqual(report["profile_id"], "")
        self.assertEqual(report["profile_name"], "Default")
        self.assertEqual(window.store.profile_name(self.guid), "After recording")

    def test_names_are_unique_and_default_is_reserved_without_changing_stored_profiles(self):
        store = self.window.store
        first = store.create_profile(self.guid, "Racing")
        second = store.create_profile(self.guid, "Platformers")
        for name in ("", " ", "DEFAULT", "racing", "x" * 81):
            with self.subTest(name=name), self.assertRaises(ValueError):
                store.create_profile(self.guid, name)
        with self.assertRaises(ValueError):
            store.rename_profile(self.guid, second, "RACING")
        self.assertEqual(dict(store.profiles(self.guid)), {first: "Racing", second: "Platformers"})
