import json
from pathlib import Path
import tempfile
import unittest
from controller_lab.model import Device, Sample, Session
from controller_lab.storage import Store, report_csv, report_text


def fixture():
    session = Session(Device(1, "Example pad", "test-guid", "generic", "fixture", True), 1)
    session.add(Sample(2, {"lefttrigger": .5}, {"a": True}))
    return session.report()


class StorageTests(unittest.TestCase):
    def test_device_preferences_are_isolated(self):
        with tempfile.TemporaryDirectory() as path:
            s = Store(path)
            s.update("pad-a", overlay="xbox", deadzone=12)
            s.update("pad-b", overlay="switch")
            loaded = Store(path)
            self.assertEqual(loaded.device("pad-a")["overlay"], "xbox")
            self.assertNotIn("deadzone", loaded.device("pad-b"))

    def test_corrupt_preferences_do_not_prevent_startup(self):
        with tempfile.TemporaryDirectory() as path:
            Path(path, "preferences.json").write_text("{broken", encoding="utf-8")
            store = Store(path)
            self.assertEqual(store.preferences, {})
            self.assertTrue(store.warning)

    def test_report_roundtrip_and_bad_file_skipped(self):
        with tempfile.TemporaryDirectory() as path:
            s = Store(path)
            r = fixture()
            identifier = s.save_report(r)
            Path(path, "sessions", "broken.json").write_text("broken", encoding="utf-8")
            self.assertEqual(s.reports(), [(identifier, r)])

    def test_text_and_csv_keep_missing_measurements_distinct_from_zero(self):
        r = fixture()
        self.assertIn("not mapped", report_text(r))
        self.assertIn("left_stick.radial_deviation,", report_csv(r))
        self.assertNotIn("righttrigger", report_csv(r))

    def test_incomplete_structured_report_is_skipped(self):
        with tempfile.TemporaryDirectory() as path:
            p = Path(path, "sessions")
            p.mkdir()
            (p / "bad.json").write_text(json.dumps({"schema": 1, "created": "today", "device": {},
                "left_stick": {}, "right_stick": {}}), encoding="utf-8")
            self.assertEqual(Store(path).reports(), [])

    def test_nonfinite_metrics_are_skipped(self):
        with tempfile.TemporaryDirectory() as path:
            r = fixture()
            r["left_stick"]["peak_radius"] = float("nan")
            Store(path).save_report(r)
            self.assertEqual(Store(path).reports(), [])
