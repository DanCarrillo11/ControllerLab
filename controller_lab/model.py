"""Hardware-independent identity, input normalization and measurements."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import math
import statistics
from collections import deque

FAMILIES = {
    "dualsense": "PlayStation 5 · DualSense",
    "playstation": "PlayStation · DualShock",
    "xbox": "Xbox",
    "switch": "Nintendo Switch",
    "wii": "Nintendo Wii",
    "gamecube": "Nintendo GameCube",
    "generic": "Generic gamepad",
}
BUTTONS = ("a", "b", "x", "y", "back", "guide", "start", "leftstick",
           "rightstick", "leftshoulder", "rightshoulder", "dpup", "dpdown",
           "dpleft", "dpright", "misc1", "paddle1", "paddle2", "paddle3",
           "paddle4", "touchpad")
AXES = ("leftx", "lefty", "rightx", "righty", "lefttrigger", "righttrigger")
DEFAULT_NAMES = dict(zip(BUTTONS, ("A", "B", "X", "Y", "View", "Home", "Menu",
    "LS", "RS", "LB", "RB", "Up", "Down", "Left", "Right", "Capture",
    "P1", "P2", "P3", "P4", "Touchpad")))


def button_names(family):
    labels = DEFAULT_NAMES.copy()
    if family in ("dualsense", "playstation"):
        labels.update(a="×", b="○", x="□", y="△", back="Create" if family == "dualsense" else "Share",
                      start="Options", guide="PS", leftstick="L3", rightstick="R3",
                      leftshoulder="L1", rightshoulder="R1", misc1="Mute")
    elif family == "switch":
        labels.update(a="B", b="A", x="Y", y="X", back="−", start="+",
                      leftshoulder="L", rightshoulder="R")
    elif family == "gamecube":
        labels.update(a="A", b="B", x="X", y="Y", start="Start", leftshoulder="L", rightshoulder="Z")
    elif family == "wii":
        labels.update(a="A", b="B", x="1", y="2", back="−", start="+", guide="Home")
    elif family == "generic":
        labels.update(back="Select", start="Start", guide="Home")
    return labels


def identify(name, guid="", vendor=None, product=None):
    """Conservative classification; the backend's mapping is a separate concern.

    Standard SDL2 USB/Bluetooth GUIDs store VID/PID as little-endian words.
    Name matching takes precedence for third-party adapters with explicit names.
    """
    if vendor is None and len(guid) == 32:
        try:
            raw = bytes.fromhex(guid)
            if int.from_bytes(raw[:2], "little") in (3, 5):
                vendor = int.from_bytes(raw[4:6], "little")
                product = int.from_bytes(raw[8:10], "little")
        except ValueError:
            pass
    n = name.casefold()
    if any(v in n for v in ("gamecube", "game cube", "wup-028", "mayflash gc")) or (vendor, product) == (0x057e, 0x0337):
        return "gamecube", "Device name / USB identity"
    if any(v in n for v in ("wiimote", "wii remote", "rvl-cnt", "wii u pro")) or (vendor == 0x057e and product in (0x0306, 0x0330)):
        return "wii", "Device name / USB identity"
    if "dualsense" in n or (vendor == 0x054c and product in (0x0ce6, 0x0df2)):
        return "dualsense", "Sony DualSense identity"
    if any(v in n for v in ("dualshock", "playstation", "ps4 controller", "ps3 controller")) or vendor == 0x054c:
        return "playstation", "PlayStation identity"
    if any(v in n for v in ("switch", "joy-con", "joycon", "nintendo pro")) or (vendor == 0x057e and product in (0x2006, 0x2007, 0x2009, 0x2017, 0x200e)):
        return "switch", "Switch identity"
    if any(v in n for v in ("xbox", "xinput", "x-box", "x360", "xone")) or vendor == 0x045e:
        return "xbox", "Xbox / XInput identity"
    return "generic", "Unidentified device; choose an overlay if needed"


def clamp(value, low=-1.0, high=1.0):
    return max(low, min(high, float(value)))


def signed_axis(value):
    return clamp(value / (32768.0 if value < 0 else 32767.0))


def deadzone(x, y, radius):
    """Radial preview only; raw measurements remain unchanged."""
    length = math.hypot(x, y)
    radius = clamp(radius, 0.0, 0.95)
    if length <= radius:
        return 0.0, 0.0
    adjusted = min(1.0, (length - radius) / (1.0 - radius))
    return x / length * adjusted, y / length * adjusted


@dataclass(frozen=True)
class Device:
    instance_id: int
    name: str
    guid: str
    family: str
    identity: str
    mapped: bool
    axes_count: int = 0
    buttons_count: int = 0
    hats_count: int = 0


@dataclass
class Sample:
    time: float = 0.0
    axes: dict = field(default_factory=dict)
    buttons: dict = field(default_factory=dict)
    raw_axes: tuple = ()
    raw_buttons: tuple = ()
    hats: tuple = ()
    power: str = "unknown"
    mapped: bool = False
    connected: bool = True


def apply_mapping(sample, mapping):
    """An optional app-local map for adapters; never writes a device/SDL map."""
    if not mapping:
        return sample
    axes, buttons = {}, {}
    axis_map = mapping.get("axes", {})
    button_map = mapping.get("buttons", {})
    if not isinstance(axis_map, dict) or not isinstance(button_map, dict):
        return sample
    for key, source in axis_map.items():
        if key not in AXES or not isinstance(source, dict):
            continue
        index = source.get("index", -1)
        if not isinstance(index, int) or not 0 <= index < len(sample.raw_axes):
            continue
        v = sample.raw_axes[index]
        v = -v if source.get("invert") else v
        axes[key] = clamp((v + 1) / 2, 0, 1) if key.endswith("trigger") and source.get("signed", True) else clamp(v, 0 if key.endswith("trigger") else -1, 1)
    for key, source in button_map.items():
        if key not in BUTTONS or not isinstance(source, str):
            continue
        try:
            if source.startswith("b"):
                index = int(source[1:])
                if 0 <= index < len(sample.raw_buttons):
                    buttons[key] = bool(sample.raw_buttons[index])
            elif source.startswith("h"):
                index, direction = source[1:].split(":")
                index = int(index)
                if 0 <= index < len(sample.hats):
                    x, y = sample.hats[index]
                    buttons[key] = {"up": y > 0, "down": y < 0, "left": x < 0, "right": x > 0}.get(direction, False)
        except ValueError:
            continue
    return Sample(sample.time, axes, buttons, sample.raw_axes, sample.raw_buttons, sample.hats,
                  sample.power, bool(axes or buttons), sample.connected)


class StickStats:
    def __init__(self):
        self.samples = 0
        self.peak = 0.0
        self.bins = [0.0] * 32
        self.visited = set()

    def add(self, x, y):
        self.samples += 1
        radius = math.hypot(x, y)
        self.peak = max(self.peak, radius)
        if radius >= 0.5:
            slot = int((math.atan2(y, x) + math.pi) / (2 * math.pi) * 32) % 32
            self.bins[slot] = max(self.bins[slot], radius)
            self.visited.add(slot)

    def summary(self):
        return {"samples": self.samples, "peak_radius": self.peak,
                "coverage": len(self.visited) / 32,
                "radial_deviation": (statistics.mean(abs(self.bins[i] - 1) for i in self.visited)
                                     if len(self.visited) >= 24 else None)}


def rest_summary(points):
    if not points:
        return None
    xs, ys = zip(*points)
    radii = [math.hypot(x, y) for x, y in points]
    return {"samples": len(points), "mean_x": statistics.mean(xs), "mean_y": statistics.mean(ys),
            "mean_radius": statistics.mean(radii), "max_radius": max(radii),
            "jitter": math.hypot(statistics.pstdev(xs), statistics.pstdev(ys))}


class Session:
    def __init__(self, device, start):
        self.device, self.start, self.last = device, start, start
        self.left, self.right = StickStats(), StickStats()
        self.triggers = {k: {"min": 1.0, "max": 0.0} for k in AXES[-2:]}
        self.presses, self.previous, self.samples = {}, {}, 0
        self.raw_presses, self.raw_previous = {}, ()
        self.trails = {side: deque(maxlen=900) for side in ("left", "right")}

    def add(self, sample):
        self.last = sample.time
        self.samples += 1
        for prefix, stats in (("left", self.left), ("right", self.right)):
            if prefix + "x" in sample.axes and prefix + "y" in sample.axes:
                stats.add(sample.axes[prefix + "x"], sample.axes[prefix + "y"])
                self.trails[prefix].append((sample.axes[prefix + "x"], sample.axes[prefix + "y"]))
        for key, values in self.triggers.items():
            if key in sample.axes:
                v = sample.axes[key]
                values["min"], values["max"] = min(values["min"], v), max(values["max"], v)
        for key, down in sample.buttons.items():
            if down and not self.previous.get(key):
                self.presses[key] = self.presses.get(key, 0) + 1
        self.previous = sample.buttons.copy()
        for index, down in enumerate(sample.raw_buttons):
            if down and (index >= len(self.raw_previous) or not self.raw_previous[index]):
                key = str(index)
                self.raw_presses[key] = self.raw_presses.get(key, 0) + 1
        self.raw_previous = sample.raw_buttons

    def report(self):
        return {"schema": 1, "created": datetime.now(timezone.utc).isoformat(),
                "device": asdict(self.device), "duration_seconds": max(0, self.last - self.start),
                "sample_count": self.samples, "left_stick": self.left.summary(),
                "right_stick": self.right.summary(), "button_presses": self.presses.copy(),
                "triggers": {k: v.copy() for k, v in self.triggers.items() if v["min"] <= v["max"]},
                "stick_trails": {k: list(v) for k, v in self.trails.items()}, "raw_button_presses": self.raw_presses.copy()}
