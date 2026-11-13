import math
import unittest

from controller_lab.model import (Device, Sample, Session, StickStats, identify,
    deadzone, signed_axis, rest_summary, apply_mapping, button_names)


class IdentityTests(unittest.TestCase):
    def test_actual_dualsense_guid_and_generic_windows_name(self):
        self.assertEqual(identify("Wireless Controller", "030057564c050000e60c000000016800")[0], "dualsense")

    def test_families(self):
        for name, expected in (("DualSense Wireless Controller", "dualsense"),
                ("Sony DualShock 4", "playstation"), ("Xbox Wireless Controller", "xbox"),
                ("Switch Pro Controller", "switch"), ("Joy-Con (L)", "switch"),
                ("Nintendo RVL-CNT-01", "wii"), ("GameCube Controller Adapter", "gamecube"),
                ("USB Gamepad", "generic")):
            with self.subTest(name=name):
                self.assertEqual(identify(name)[0], expected)

    def test_usb_id_does_not_hide_specific_adapter(self):
        self.assertEqual(identify("GameCube USB adapter", vendor=0x057e, product=0x2009)[0], "gamecube")

    def test_malformed_or_nonstandard_guid_is_not_guessed(self):
        for guid in ("", "z" * 32, "not-a-guid", "000000004c050000e60c000000000000"):
            self.assertEqual(identify("Unknown device", guid)[0], "generic")

    def test_ps4_usb_identity(self):
        self.assertEqual(identify("Wireless Controller", vendor=0x054c, product=0x09cc)[0], "playstation")

    def test_nintendo_faces_are_position_correct(self):
        self.assertEqual(button_names("switch")["a"], "B")
        self.assertEqual(button_names("switch")["b"], "A")
        self.assertEqual(button_names("dualsense")["a"], "×")


class MeasurementTests(unittest.TestCase):
    def test_signed_endpoints_and_center(self):
        self.assertEqual([signed_axis(x) for x in (-32768, 0, 32767)], [-1, 0, 1])

    def test_radial_deadzone_does_not_change_direction(self):
        self.assertEqual(deadzone(.02, .01, .1), (0, 0))
        x, y = deadzone(.6, .8, .1)
        self.assertAlmostEqual(x, .6)
        self.assertAlmostEqual(y, .8)
        self.assertAlmostEqual(math.hypot(*deadzone(1, 1, .1)), 1)

    def test_insufficient_circle_coverage_has_no_score(self):
        stats = StickStats()
        for _ in range(100):
            stats.add(1, 0)
        self.assertIsNone(stats.summary()["radial_deviation"])

    def test_complete_circle_and_partial_gate_deviation(self):
        stats = StickStats()
        for i in range(128):
            a = (i + .2) * math.tau / 128
            stats.add(.8 * math.cos(a), .8 * math.sin(a))
        self.assertEqual(stats.summary()["coverage"], 1)
        self.assertAlmostEqual(stats.summary()["radial_deviation"], .2)

    def test_rest_uses_raw_magnitude_and_variance(self):
        r = rest_summary([(.03, .04)] * 20)
        self.assertAlmostEqual(r["mean_radius"], .05)
        self.assertEqual(r["jitter"], 0)
        self.assertIsNone(rest_summary([]))

    def test_presses_count_edges_not_held_samples(self):
        s = Session(Device(1, "Pad", "guid", "generic", "test", True), 10)
        for t, down in ((10, True), (11, True), (12, False), (13, True)):
            s.add(Sample(t, {"lefttrigger": .4}, {"a": down}, mapped=True))
        r = s.report()
        self.assertEqual(r["button_presses"], {"a": 2})
        self.assertEqual(r["duration_seconds"], 3)
        self.assertEqual(r["left_stick"]["samples"], 0)
        self.assertEqual(r["triggers"], {"lefttrigger": {"min": .4, "max": .4}})


class MappingTests(unittest.TestCase):
    def test_adapter_mapping_with_hat_and_inverted_trigger(self):
        raw = Sample(1, {}, {}, (.25, -.5, -1), (False, True), ((-1, 1),))
        mapped = apply_mapping(raw, {"axes": {"leftx": {"index": 0}, "lefty": {"index": 1, "invert": True},
            "lefttrigger": {"index": 2, "invert": True, "signed": True}},
            "buttons": {"a": "b1", "dpup": "h0:up", "dpleft": "h0:left"}})
        self.assertEqual(mapped.axes, {"leftx": .25, "lefty": .5, "lefttrigger": 1})
        self.assertTrue(mapped.buttons["a"])
        self.assertTrue(mapped.buttons["dpup"])
        self.assertEqual(raw.axes, {})
        self.assertEqual(raw.raw_axes, (.25, -.5, -1))

    def test_invalid_indices_do_not_read_other_controls(self):
        s = Sample(raw_axes=(.2,), raw_buttons=(True,), hats=((0, 0),))
        r = apply_mapping(s, {"axes": {"leftx": {"index": -1}, "rightx": {"index": 8}},
                               "buttons": {"a": "b-1", "b": "b7", "x": "h-1:up", "y": "bad"}})
        self.assertEqual(r.axes, {})
        self.assertEqual(r.buttons, {})
        self.assertFalse(r.mapped)

    def test_empty_mapping_preserves_sdl_values(self):
        s = Sample(axes={"leftx": .2}, mapped=True)
        self.assertIs(apply_mapping(s, {}), s)

    def test_partially_custom_mapping_does_not_invent_stick_axes(self):
        r = apply_mapping(Sample(raw_buttons=(True,)), {"buttons": {"a": "b0"}})
        self.assertTrue(r.mapped)
        self.assertEqual(r.axes, {})

    def test_malformed_config_falls_back(self):
        s = Sample()
        self.assertIs(apply_mapping(s, {"axes": []}), s)
