import copy
import importlib.util
from importlib.metadata import distribution
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtGui import QImage
from controller_lab.diagnostics import GuidedRun, capability_rows
from controller_lab.emulation import Emulation, VirtualSink, output_sample, clean_settings
from controller_lab.mapping import InputCapture, MappingDialog
from controller_lab.model import Device, Sample, Session
from controller_lab.storage import Store, valid_report
from controller_lab.reports import report_html, export_png
from controller_lab.ui import Window
from test_ui import APP, FakeBackend


def report_fixture():
    session = Session(Device(1, "Pad <script>", "guid", "dualsense", "fixture", True), 1)
    for i in range(20):
        session.add(Sample(1 + i / 10, {"leftx": .02, "lefty": .01, "lefttrigger": .5}, {"a": True}, mapped=True))
    return session.report()


class FeatureStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_named_profiles_keep_independent_settings_and_default(self):
        self.store.update("g", deadzone=8, mapping={"buttons": {"a": "b0"}})
        a = self.store.create_profile("g", "First")
        b = self.store.create_profile("g", "Second")
        self.store.select_profile("g", a)
        self.store.update("g", deadzone=20, mapping={"buttons": {"b": "b1"}})
        self.store.select_profile("g", b)
        self.assertEqual(self.store.device("g")["deadzone"], 8)
        self.assertEqual(self.store.device("g")["mapping"], {"buttons": {"a": "b0"}})
        loaded = Store(self.temp.name)
        loaded.select_profile("g", a)
        self.assertEqual(loaded.device("g")["deadzone"], 20)
        loaded.delete_profile("g", a)
        self.assertEqual(loaded.profile_name("g"), "Default")
        self.assertEqual(loaded.device("g")["deadzone"], 8)

    def test_report_rename_delete_restore_preserves_measurements(self):
        report = report_fixture()
        key = self.store.save_report(report)
        self.store.rename_report(key, "My test")
        named = self.store.reports()[0][1]
        self.assertEqual(named["left_stick"], report["left_stick"])
        self.store.delete_report(key)
        self.assertEqual(self.store.reports(), [])
        self.assertTrue(self.store.restore_report())
        self.assertEqual(self.store.reports()[0][1]["name"], "My test")

    def test_report_paths_cannot_escape_session_directory(self):
        for value in ("../preferences", "C:/other/file", "", "g" * 32):
            with self.assertRaises(ValueError):
                self.store.delete_report(value)

    def test_import_validates_report_and_size(self):
        path = Path(self.temp.name) / "import.json"
        path.write_text(json.dumps(report_fixture()), encoding="utf-8")
        self.store.import_report(path)
        self.assertEqual(len(self.store.reports()), 1)
        path.write_text('{}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.store.import_report(path)
        path.write_bytes(b" " * 2_000_001)
        with self.assertRaises(ValueError):
            self.store.import_report(path)

    def test_visual_report_escapes_text_and_exports_real_image(self):
        report = report_fixture()
        html = report_html(report)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("Pad <script>", html)
        self.assertIn("data:image/png;base64,", html)
        path = Path(self.temp.name) / "report.png"
        export_png(report, path)
        image = QImage(str(path))
        self.assertFalse(image.isNull())
        self.assertGreater(image.height(), 600)

    def test_malformed_recorded_trails_are_not_imported(self):
        report = report_fixture()
        report["stick_trails"] = {"left": [[float("nan"), 0]]}
        self.assertFalse(valid_report(report))

    def test_raw_button_edges_are_recorded_without_standard_mapping(self):
        session = Session(Device(1, "Raw pad", "g", "generic", "fixture", False), 1)
        for down in (True, True, False, True):
            session.add(Sample(2, raw_buttons=(down,), mapped=False))
        self.assertEqual(session.report()["raw_button_presses"], {"0": 2})


class CaptureTests(unittest.TestCase):
    def test_a_held_button_must_be_released_before_capture(self):
        probe = InputCapture(Sample(raw_buttons=(True,)), "button")
        self.assertIsNone(probe.observe(Sample(raw_buttons=(True,))))
        self.assertIsNone(probe.observe(Sample(raw_buttons=(False,))))
        self.assertEqual(probe.observe(Sample(raw_buttons=(True,))), "b0")

    def test_hat_direction_and_inverted_signed_trigger(self):
        self.assertEqual(InputCapture(Sample(hats=((0, 0),)), "button").observe(Sample(hats=((-1, 0),))), "h0:left")
        result = InputCapture(Sample(raw_axes=(0, 1)), "axis").observe(Sample(raw_axes=(.02, -.8)))
        self.assertEqual(result, {"index": 1, "signed": True, "invert": True})

    def test_capture_changes_a_draft_without_saving_it(self):
        sample = Sample(raw_axes=(0,), raw_buttons=(False,))
        dialog = MappingDialog(Device(1, "Pad", "g", "generic", "fixture", False, 1, 1, 0), "generic", {}, None, lambda: sample)
        dialog.start_capture("button", "a")
        sample.raw_buttons = (True,)
        dialog.poll_capture()
        self.assertEqual(dialog.buttons["a"].currentData(), "b0")
        self.assertIsNone(dialog.result_mapping)
        dialog.close()


class GuidedTests(unittest.TestCase):
    def test_only_exposed_inputs_are_expected_and_pending_is_not_failed(self):
        device = Device(1, "Pad", "g", "generic", "fixture", True)
        run = GuidedRun(device, Sample(buttons={"a": False, "b": False}, mapped=True))
        run.add(Sample(1, buttons={"a": True}, mapped=True))
        result = run.report("generic")["guided"]
        self.assertEqual({b["key"] for b in result["buttons"]}, {"a", "b"})
        self.assertEqual(sum(b["observed"] for b in result["buttons"]), 1)
        self.assertFalse(result["finished"])

    def test_center_requires_five_seconds_and_does_not_apply_deadzone(self):
        sample = Sample(1, {"leftx": .03, "lefty": .04}, {}, mapped=True)
        run = GuidedRun(Device(1, "Pad", "g", "generic", "fixture", True), sample)
        run.measure_center(sample)
        for i in range(25):
            sample.time = 1 + i * .25
            run.add(sample)
        self.assertIsNone(run.rest_start)
        self.assertAlmostEqual(run.rest["left"]["mean_radius"], .05)

    def test_unknown_battery_and_rumble_are_not_claimed_supported(self):
        rows = capability_rows(Device(1, "Pad", "g", "generic", "fixture", True), Sample(power="unknown"))
        self.assertIn(("Power", "Not reported", "Shown only when exposed by the input backend."), rows)
        self.assertTrue(any(name == "Vibration" and status == "Not tested" for name, status, _ in rows))


class FakeSink:
    def __init__(self, *args):
        self.closed, self.notifications, self.states = False, [], []
    def write(self, state):
        self.states.append(state)
    def close(self):
        self.closed = True


class EmulationTests(unittest.TestCase):
    def test_transform_remaps_and_preserves_original_input(self):
        sample = Sample(1, {"leftx": .5, "lefty": 0, "lefttrigger": .01}, {"a": True, "dpup": True, "dpdown": True}, mapped=True)
        original = copy.deepcopy(sample)
        output = output_sample(sample, {"deadzone": 0, "curve": "squared", "buttons": {"a": "b"}})
        self.assertAlmostEqual(output.axes["leftx"], .25)
        self.assertEqual(output.axes["lefttrigger"], 0)
        self.assertTrue(output.buttons["b"])
        self.assertFalse(output.buttons["dpup"])
        self.assertEqual(sample, original)

    def test_source_change_disconnect_and_close_detach_output(self):
        engine = Emulation(FakeSink)
        engine.start(7, Sample(mapped=True), {})
        sink = engine.sink
        engine.update(8, Sample(mapped=True))
        self.assertFalse(engine.running)
        self.assertTrue(sink.closed)
        engine.start(7, Sample(mapped=True), {})
        sink = engine.sink
        engine.update(7, Sample(connected=False))
        self.assertTrue(sink.closed)

    def test_unmapped_source_is_rejected_without_constructing_target(self):
        calls = []
        engine = Emulation(lambda *args: calls.append(args))
        with self.assertRaises(ValueError):
            engine.start(1, Sample(mapped=False), {})
        self.assertEqual(calls, [])

    def test_output_failure_stops_and_records_error(self):
        class Broken(FakeSink):
            def write(self, state):
                raise RuntimeError("Output lost")
        engine = Emulation(Broken)
        engine.start(1, Sample(mapped=True), {})
        sink = engine.sink
        engine.update(1, Sample(mapped=True))
        self.assertFalse(engine.running)
        self.assertTrue(sink.closed)
        self.assertIn("Output lost", engine.error)

    def test_invalid_settings_are_bounded(self):
        settings = clean_settings({"sensitivity": float("inf"), "deadzone": "bad", "trigger_deadzone": 8})
        self.assertEqual(settings["sensitivity"], 1)
        self.assertEqual(settings["deadzone"], .08)
        self.assertEqual(settings["trigger_deadzone"], .4)
        self.assertFalse(clean_settings({"feedback": "false"})["feedback"])

    def test_invalid_axes_are_neutral_and_never_become_full_deflection(self):
        output = output_sample(Sample(axes={"leftx": float("nan"), "lefty": float("inf"), "rightx": "invalid"}, mapped=True), {})
        self.assertEqual(output.axes["leftx"], 0)
        self.assertEqual(output.axes["lefty"], 0)
        self.assertEqual(output.axes["rightx"], 0)

    def test_feedback_is_opt_in_and_bounded_to_latest_notification(self):
        engine = Emulation(FakeSink)
        engine.start(7, Sample(mapped=True), {})
        engine.sink.notifications.append((.5, .25))
        engine.update(7, Sample(mapped=True))
        self.assertIsNone(engine.feedback_due(10))
        engine.stop()
        engine.start(7, Sample(mapped=True), {"feedback": True})
        engine.sink.notifications.append((.5, .25))
        engine.update(7, Sample(mapped=True))
        self.assertEqual(engine.feedback_due(20), (.5, .25))

    def test_native_api_mapping_uses_correct_y_and_ds4_dpad_without_hardware(self):
        path = distribution("vgamepad").locate_file("vgamepad/api.py")
        spec = importlib.util.spec_from_file_location("standalone_gamepad_api", path)
        api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api)
        class Pad:
            def __init__(self):
                self.cmp_func = None
                self.reset()
            def reset(self):
                self.buttons, self.special, self.values = [], [], {}
            def update(self): pass
            def left_joystick_float(self, **kw): self.values["left"] = kw
            def right_joystick_float(self, **kw): self.values["right"] = kw
            def left_trigger_float(self, **kw): self.values["lt"] = kw
            def right_trigger_float(self, **kw): self.values["rt"] = kw
            def press_button(self, button): self.buttons.append(button)
            def press_special_button(self, special_button): self.special.append(special_button)
            def directional_pad(self, direction): self.values["dpad"] = direction
        fake = SimpleNamespace(VX360Gamepad=Pad, VDS4Gamepad=Pad, XUSB_BUTTON=api.XUSB_BUTTON,
                               DS4_BUTTONS=api.DS4_BUTTONS, DS4_SPECIAL_BUTTONS=api.DS4_SPECIAL_BUTTONS, DS4_DPAD_DIRECTIONS=api.DS4_DPAD_DIRECTIONS)
        with patch.dict(sys.modules, {"vgamepad": fake}):
            state = Sample(1, {"lefty": .5, "lefttrigger": .6}, {"a": True, "dpup": True, "dpright": True}, mapped=True)
            xbox = VirtualSink("x360")
            xbox.write(state)
            self.assertEqual(xbox.pad.values["left"]["y_value_float"], -.5)
            self.assertIn(api.XUSB_BUTTON.XUSB_GAMEPAD_A, xbox.pad.buttons)
            xbox.close()
            ds4 = VirtualSink("ds4")
            ds4.write(state)
            self.assertEqual(ds4.pad.values["left"]["y_value_float"], .5)
            self.assertEqual(ds4.pad.values["dpad"], api.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHEAST)
            self.assertIn(api.DS4_BUTTONS.DS4_BUTTON_TRIGGER_LEFT, ds4.pad.buttons)
            ds4.close()


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.backend = FakeBackend()
        self.window = Window(self.backend, self.temp.name)
        self.window.timer.stop()
        self.window.scan_timer.stop()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.temp.cleanup()

    def test_all_seven_pages_fit_and_no_output_starts_automatically(self):
        self.window.resize(1080, 730)
        self.window.show()
        for index in range(7):
            self.window.navigate(index)
            APP.processEvents()
            self.assertEqual((self.window.width(), self.window.height()), (1080, 730))
        self.assertFalse(self.window.emulation.running)
        self.assertEqual(self.backend.rumbles, [])

    def test_guided_report_roundtrip_and_user_confirmation(self):
        window = self.window
        window.start_guided()
        self.backend.sample.time += .1
        window.tick()
        for _ in range(4): window.guided_next()
        self.assertEqual(self.backend.rumbles, [])
        window.guided_vibration()
        self.assertTrue(window.guided.command_accepted)
        self.assertNotEqual(window.guided.vibration, "Felt by the user")
        window.confirm_vibration(True)
        window.guided_next()
        window.save_guided()
        report = window.store.reports()[0][1]
        self.assertTrue(report["guided"]["finished"])
        self.assertEqual(report["guided"]["vibration"], "Felt by the user")
        self.assertEqual(report["profile_name"], "Default")

    def test_each_guided_step_keeps_actions_inside_the_minimum_window(self):
        window = self.window
        window.resize(1080, 730)
        window.show()
        window.navigate(5)
        window.start_guided()
        for step in range(6):
            window.guided.step = step
            window.update_guided()
            APP.processEvents()
            self.assertEqual((window.width(), window.height()), (1080, 730))
            for widget in (window.guide_next, window.guide_cancel, window.guide_save, window.guide_center, window.guide_vibration):
                if not widget.isHidden():
                    self.assertTrue(window.pages.rect().contains(widget.mapTo(window.pages, widget.rect().bottomRight())))

    def test_emulation_stops_on_unplug_and_cannot_feed_its_output_back(self):
        window = self.window
        window.emulation.factory = FakeSink
        with patch("controller_lab.features.driver_status", return_value={"vigem": True, "hidhide": False}):
            window.start_emulation()
        sink = window.emulation.sink
        self.assertIsNotNone(sink)
        virtual = Device(99, "Virtual Xbox", "030000005e0400008e02000000000000", "xbox", "fixture", True)
        self.assertEqual(window.filter_virtual_outputs([*window.devices, virtual]), window.devices)
        self.backend.devices = []
        window.refresh_devices()
        self.assertFalse(window.emulation.running)
        self.assertTrue(sink.closed)

    def test_session_search_does_not_change_saved_reports(self):
        self.window.store.save_report(report_fixture())
        self.window.refresh_history()
        self.window.history_search.setText("absent name")
        self.assertEqual(self.window.history_list.count(), 0)
        self.assertEqual(len(self.window.store.reports()), 1)
