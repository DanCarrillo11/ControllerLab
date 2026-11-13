"""Interaction and lifecycle checks with real Qt animations, using simulated input."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import tempfile
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

from controller_lab.backend import DemoBackend
from controller_lab.desktop_settings import DesktopSettings
from controller_lab.motion import AnimatedProgress, Switch, reveal
from controller_lab.ui import Window

APP = QApplication.instance() or QApplication([])


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        APP.setProperty("preview_motion", True)
        self.window = Window(DemoBackend(), self.tmp.name, True)
        self.window.timer.stop()
        self.window.scan_timer.stop()
        self.window.show()
        APP.processEvents()

    def tearDown(self):
        self.window.close()
        APP.setProperty("preview_motion", False)
        APP.setProperty("reduce_motion", False)
        APP.processEvents()
        self.tmp.cleanup()

    def test_fast_navigation_leaves_the_last_page_interactive(self):
        for index in (1, 2, 6, 7, 0, 6):
            self.window.navigate(index)
            QTest.qWait(18)
        QTest.qWait(260)
        self.assertEqual(self.window.pages.currentIndex(), 6)
        self.assertIsNone(self.window.pages.cover)
        self.assertTrue(self.window.emu_target.isVisible())
        self.assertTrue(self.window.emu_target.isEnabled())
        self.assertFalse(self.window.emulation.running)

    def test_reduce_motion_persists_and_switches_pages_immediately(self):
        form = self.window.desktop_form
        form.reduce_motion.setChecked(True)
        form.save()
        self.assertTrue(DesktopSettings(self.tmp.name).data["reduce_motion"])
        self.window.navigate(2)
        self.assertIsNone(self.window.pages.cover)
        self.assertFalse(self.window.emulation.running)

    def test_rapid_disclosure_changes_do_not_hide_the_reopened_panel(self):
        parent = QWidget()
        layout = QVBoxLayout(parent)
        panel = Switch("A real keyboard-accessible switch")
        layout.addWidget(panel)
        parent.show()
        panel.hide()
        reveal(panel, True)
        QTest.qWait(30)
        reveal(panel, False)
        QTest.qWait(25)
        reveal(panel, True)
        QTest.qWait(270)
        self.assertTrue(panel.isVisible())
        self.assertGreater(panel.height(), 0)
        panel.setFocus()
        QTest.keyClick(panel, Qt.Key.Key_Space)
        self.assertTrue(panel.isChecked())
        parent.close()

    def test_progress_reports_actual_value_before_the_visual_animation_finishes(self):
        bar = AnimatedProgress()
        bar.setRange(0, 1000)
        bar.show()
        bar.setValue(0)
        bar.setValue(800)
        self.assertEqual(bar.value(), 800)
        QTest.qWait(150)
        self.assertAlmostEqual(bar.display_value, 800)
        bar.setEnabled(False)
        bar.setValue(0)
        self.assertEqual(bar.display_value, 0)
        bar.close()

    def test_overlay_visual_motion_does_not_modify_input_and_clears_on_disconnect(self):
        sample = self.window.sample
        sample.buttons["a"] = True
        sample.axes["lefttrigger"] = .8
        expected = dict(sample.axes), dict(sample.buttons)
        self.window.view.set_input("dualsense", sample)
        QTest.qWait(180)
        self.assertEqual((sample.axes, sample.buttons), expected)
        self.window.view.set_input("dualsense", None)
        self.assertFalse(self.window.view.visual_clock.isActive())
        self.assertEqual(self.window.view.levels, {})

    def test_signal_path_timer_stops_when_its_page_is_hidden(self):
        self.window.navigate(6)
        APP.processEvents()
        self.assertEqual(self.window.emu_route.source, self.window.device.family)
        self.assertEqual(self.window.emu_route.source_name, self.window.device.name)
        self.window.emu_route.set_state(self.window.device, "x360", True, True)
        self.assertTrue(self.window.emu_route.clock.isActive())
        self.window.navigate(0)
        self.assertFalse(self.window.emu_route.clock.isActive())
        self.assertFalse(self.window.emulation.running)

    def test_real_emulation_reveals_fit_the_small_window_after_animation(self):
        self.window.resize(1080, 730)
        self.window.navigate(6)
        self.window.emu_advanced_toggle.click()
        QTest.qWait(50)
        self.assertGreaterEqual(self.window.emu_deadzone.height(), self.window.emu_deadzone.sizeHint().height())
        self.window.emu_help_toggle.click()
        QTest.qWait(280)
        self.assertFalse(self.window.emu_advanced.isHidden())
        self.assertFalse(self.window.emu_help_scroll.isHidden())
        self.assertEqual(self.window.emu_help_scroll.maximumHeight(), 210)
        self.assertTrue(self.window.pages.rect().contains(self.window.emu_start.mapTo(self.window.pages, self.window.emu_start.rect().bottomRight())))
        self.window.emu_advanced_toggle.click()
        QTest.qWait(40)
        self.window.emu_advanced_toggle.click()
        QTest.qWait(270)
        self.assertFalse(self.window.emu_advanced.isHidden())
        self.assertFalse(self.window.emulation.running)
