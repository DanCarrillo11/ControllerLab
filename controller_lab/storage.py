"""Small, atomic local stores. No network accounts or telemetry."""
import csv
import io
import json
import os
from pathlib import Path
import tempfile
import uuid
import math
import re
from copy import deepcopy


def valid_report(r):
    """Skip incomplete/corrupt local reports rather than breaking the history UI."""
    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    if not isinstance(r, dict) or r.get("schema") != 1 or not isinstance(r.get("created"), str):
        return False
    device = r.get("device")
    if not isinstance(device, dict) or not all(isinstance(device.get(k), str) for k in ("name", "guid")) or not isinstance(device.get("mapped"), bool):
        return False
    if not number(r.get("duration_seconds")) or not isinstance(r.get("sample_count"), int):
        return False
    if r["duration_seconds"] < 0 or r["sample_count"] < 0 or isinstance(r["sample_count"], bool):
        return False
    for side in ("left_stick", "right_stick"):
        s = r.get(side)
        if not isinstance(s, dict) or not all(number(s.get(k)) for k in ("samples", "peak_radius", "coverage")):
            return False
        if s.get("radial_deviation") is not None and not number(s["radial_deviation"]):
            return False
        if s["samples"] < 0 or s["peak_radius"] < 0 or not 0 <= s["coverage"] <= 1:
            return False
    for field in ("button_presses", "triggers", "rest_measurements"):
        if not isinstance(r.get(field, {}), dict):
            return False
    if "button_presses" not in r or "triggers" not in r:
        return False
    from .model import BUTTONS
    if not all(k in BUTTONS and isinstance(v, int) and v >= 0 for k, v in r["button_presses"].items()):
        return False
    if not all(isinstance(v, dict) and number(v.get("min")) and number(v.get("max")) for v in r["triggers"].values()):
        return False
    if not all(0 <= value["min"] <= value["max"] <= 1 for value in r["triggers"].values()):
        return False
    raw = r.get("raw_button_presses", {})
    if not isinstance(raw, dict) or not all(isinstance(key, str) and key.isdecimal() and isinstance(value, int) and value >= 0 for key, value in raw.items()):
        return False
    if not all(k in ("left", "right") and isinstance(v, dict) and all(number(v.get(key)) for key in
        ("mean_radius", "max_radius", "jitter")) for k, v in r.get("rest_measurements", {}).items()):
        return False
    if len(device["name"]) > 512 or len(device["guid"]) > 256 or len(r["created"]) > 64:
        return False
    if "name" in r and (not isinstance(r["name"], str) or len(r["name"]) > 120):
        return False
    for points in r.get("stick_trails", {}).values() if isinstance(r.get("stick_trails", {}), dict) else [None]:
        if not isinstance(points, list) or len(points) > 2000 or not all(
            isinstance(p, (list, tuple)) and len(p) == 2 and all(number(v) and abs(v) <= 2 for v in p) for p in points):
            return False
    return True


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.warning = ""
        self.preferences = {}
        self.profile_overrides = {}
        try:
            data = json.loads((self.root / "preferences.json").read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.preferences = data
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            self.warning = "Preferences could not be read. Default settings are in use."

    def device(self, guid):
        value = self.preferences.get(guid, {})
        if not isinstance(value, dict):
            return {}
        result = {k: deepcopy(v) for k, v in value.items() if k not in ("profiles", "active_profile")}
        profile = value.get("profiles", {}).get(self.active_profile(guid), {}) if isinstance(value.get("profiles", {}), dict) else {}
        if isinstance(profile, dict) and isinstance(profile.get("settings"), dict):
            result.update(deepcopy(profile["settings"]))
        return result

    def update(self, guid, **values):
        value = deepcopy(self.preferences.get(guid, {}))
        if not isinstance(value, dict):
            value = {}
        profile = value.get("profiles", {}).get(self.active_profile(guid)) if isinstance(value.get("profiles", {}), dict) else None
        if isinstance(profile, dict):
            profile.setdefault("settings", {}).update(values)
        else:
            value.update(values)
        updated = dict(self.preferences, **{guid: value})
        atomic_write(self.root / "preferences.json", json.dumps(updated, indent=2))
        self.preferences = updated

    def profiles(self, guid):
        value = self.preferences.get(guid, {})
        profiles = value.get("profiles", {}) if isinstance(value, dict) else {}
        if not isinstance(profiles, dict):
            return []
        return [(key, p["name"]) for key, p in profiles.items() if isinstance(p, dict)
                and isinstance(p.get("name"), str) and isinstance(p.get("settings"), dict)]

    def active_profile(self, guid):
        if guid in self.profile_overrides:
            key = self.profile_overrides[guid]
            return key if key in dict(self.profiles(guid)) else ""
        value = self.preferences.get(guid, {})
        key = value.get("active_profile", "") if isinstance(value, dict) else ""
        return key if key in dict(self.profiles(guid)) else ""

    def profile_name(self, guid):
        return dict(self.profiles(guid)).get(self.active_profile(guid), "Default")

    def _profile_write(self, guid, mutate):
        value = deepcopy(self.preferences.get(guid, {}))
        if not isinstance(value, dict):
            value = {}
        if not isinstance(value.get("profiles"), dict):
            value["profiles"] = {}
        mutate(value)
        updated = dict(self.preferences, **{guid: value})
        atomic_write(self.root / "preferences.json", json.dumps(updated, indent=2))
        self.preferences = updated

    def profile_label(self, guid, name, excluding=None):
        name = name.strip() if isinstance(name, str) else ""
        if not name:
            raise ValueError("Enter a profile name.")
        if len(name) > 80:
            raise ValueError("Use at most 80 characters for a profile name.")
        if name.casefold() == "default" or any(key != excluding and label.casefold() == name.casefold()
                                               for key, label in self.profiles(guid)):
            raise ValueError("A profile with this name already exists. Choose another name.")
        return name

    def create_profile(self, guid, name, *, settings=None, activate=False):
        name = self.profile_label(guid, name)
        identifier = uuid.uuid4().hex
        if settings is not None and not isinstance(settings, dict):
            raise ValueError("Profile settings must be a configuration object.")
        snapshot = deepcopy(self.device(guid) if settings is None else settings)
        def create(value):
            value["profiles"][identifier] = {"name": name, "settings": snapshot}
            if activate:
                value["active_profile"] = identifier
        self._profile_write(guid, create)
        if activate:
            self.profile_overrides.pop(guid, None)
        return identifier

    def select_profile(self, guid, identifier):
        if identifier and identifier not in dict(self.profiles(guid)):
            raise ValueError("This profile is no longer available.")
        self._profile_write(guid, lambda value: value.update(active_profile=identifier))
        self.profile_overrides.pop(guid, None)

    def override_profile(self, guid, identifier):
        if identifier and identifier not in dict(self.profiles(guid)):
            raise ValueError("The game's profile was deleted. Update its game rule.")
        self.profile_overrides[guid] = identifier

    def clear_profile_override(self, guid):
        self.profile_overrides.pop(guid, None)

    def rename_profile(self, guid, identifier, name):
        if identifier not in dict(self.profiles(guid)):
            raise ValueError("Select a named profile and enter a name.")
        name = self.profile_label(guid, name, excluding=identifier)
        self._profile_write(guid, lambda value: value["profiles"][identifier].update(name=name))

    def delete_profile(self, guid, identifier):
        if identifier not in dict(self.profiles(guid)):
            raise ValueError("Select a named profile.")
        def remove(value):
            value["profiles"].pop(identifier)
            if value.get("active_profile") == identifier:
                value["active_profile"] = ""
        self._profile_write(guid, remove)

    def save_report(self, report):
        identifier = uuid.uuid4().hex
        atomic_write(self.root / "sessions" / (identifier + ".json"), json.dumps(report, indent=2))
        return identifier

    def reports(self):
        reports = []
        for path in (self.root / "sessions").glob("*.json"):
            try:
                r = json.loads(path.read_text(encoding="utf-8"))
                if valid_report(r):
                    reports.append((path.stem, r))
            except (OSError, ValueError):
                continue
        return sorted(reports, key=lambda item: item[1]["created"], reverse=True)

    def report_path(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise ValueError("Invalid session identifier.")
        return self.root / "sessions" / (identifier + ".json")

    def rename_report(self, identifier, name):
        path = self.report_path(identifier)
        report = json.loads(path.read_text(encoding="utf-8"))
        if not valid_report(report):
            raise ValueError("This report cannot be read.")
        report["name"] = name.strip()[:120]
        atomic_write(path, json.dumps(report, indent=2))

    def delete_report(self, identifier):
        path = self.report_path(identifier)
        trash = self.root / "trash"
        trash.mkdir(parents=True, exist_ok=True)
        os.replace(path, trash / (identifier + ".json"))
        os.utime(trash / (identifier + ".json"), None)

    def restore_report(self):
        paths = list((self.root / "trash").glob("*.json"))
        if not paths:
            return False
        path = max(paths, key=lambda p: p.stat().st_mtime)
        target = self.report_path(path.stem)
        if target.exists():
            raise ValueError("A session with this identifier already exists.")
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(path, target)
        return True

    def import_report(self, path):
        path = Path(path)
        if path.stat().st_size > 2_000_000:
            raise ValueError("Choose a report smaller than 2 MB.")
        report = json.loads(path.read_text(encoding="utf-8"))
        if not valid_report(report):
            raise ValueError("This is not a valid Controller Lab report.")
        return self.save_report(report)


def report_text(report):
    d = report["device"]
    lines = [d["name"], report["created"], "",
             f"Duration: {report['duration_seconds']:.1f} seconds",
             f"Input samples: {report['sample_count']}",
             f"Mapping: {report.get('mapping_source', 'SDL' if d['mapped'] else 'Raw inputs')}"]
    for side in ("left", "right"):
        s = report[side + "_stick"]
        if not s["samples"]:
            lines += [f"\n{side.title()} stick: not mapped"]
            continue
        error = s["radial_deviation"]
        lines += [f"\n{side.title()} stick", f"  Peak radius: {s['peak_radius'] * 100:.1f}%",
                  f"  Circle coverage: {s['coverage'] * 100:.0f}%",
                  f"  Radial deviation: {error * 100:.1f}%" if error is not None else "  Radial deviation: insufficient circle coverage"]
    for key, values in report["triggers"].items():
        lines.append(f"\n{key}: {values['min'] * 100:.1f}% — {values['max'] * 100:.1f}%")
    lines += ["\nButton presses"]
    lines += [f"  {key}: {count}" for key, count in report["button_presses"].items()]
    if report.get("raw_button_presses"):
        lines += ["\nRaw button presses"] + [f"  Button {key}: {count}" for key, count in report["raw_button_presses"].items()]
    for key, values in report.get("rest_measurements", {}).items():
        lines += [f"\n{key.title()} stick at rest (user-started test)",
                  f"  Mean distance from center: {values['mean_radius'] * 100:.2f}%",
                  f"  Maximum distance: {values['max_radius'] * 100:.2f}%",
                  f"  Jitter: {values['jitter'] * 100:.2f}%"]
    lines += ["", "These are observed input measurements, not a hardware health certification.",
              "Radial deviation depends on the shape of the stick gate and how it is moved."]
    return "\n".join(lines)


def report_csv(report):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["measurement", "value"])
    writer.writerow(["duration_seconds", report["duration_seconds"]])
    writer.writerow(["sample_count", report["sample_count"]])
    for side in ("left_stick", "right_stick"):
        for key, value in report[side].items():
            writer.writerow([side + "." + key, "" if value is None else value])
    for key, value in report["button_presses"].items():
        writer.writerow(["button_presses." + key, value])
    for key, value in report.get("raw_button_presses", {}).items():
        writer.writerow(["raw_button_presses." + key, value])
    for key, values in report["triggers"].items():
        for field, value in values.items():
            writer.writerow([key + "." + field, value])
    for side, values in report.get("rest_measurements", {}).items():
        for field, value in values.items():
            writer.writerow(["rest." + side + "." + field, value])
    return buffer.getvalue()
