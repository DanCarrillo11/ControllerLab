"""Guided observations and evidence; no automatic hardware pass/fail grades."""
from .model import Session, rest_summary, button_names

STEPS = (("Buttons", "Press every available button and direction at least once."),
         ("Sticks", "Rotate each available stick around its outer edge, then release it."),
         ("Triggers", "Slowly press and release each available trigger fully."),
         ("Center", "Release both sticks. Choose Measure center and keep the controller still for five seconds."),
         ("Vibration", "Optionally run a vibration test, then tell the app whether you felt it."),
         ("Summary", "Review your observations and save the report. Pending controls stay marked as not observed."))


class GuidedRun:
    def __init__(self, device, sample):
        self.device, self.session = device, Session(device, sample.time)
        self.step, self.seen, self.expected = 0, set(), set(sample.buttons)
        self.raw = not sample.mapped
        if self.raw:
            self.expected = {"raw" + str(i) for i in range(len(sample.raw_buttons))}
            self.expected.update(f"hat{i}:{d}" for i in range(len(sample.hats)) for d in ("up", "down", "left", "right"))
        self.rest_start, self.rest, self.points = None, {}, {"left": [], "right": []}
        self.vibration = "Not tested"
        self.command_accepted = None
        self.cancelled = False

    def add(self, sample):
        if self.cancelled or not sample.connected:
            return
        self.session.add(sample)
        self.seen.update(key for key, down in sample.buttons.items() if down)
        if self.raw:
            self.seen.update("raw" + str(i) for i, down in enumerate(sample.raw_buttons) if down)
            for i, (x, y) in enumerate(sample.hats):
                self.seen.update(f"hat{i}:{key}" for key, down in (("up", y > 0), ("down", y < 0), ("left", x < 0), ("right", x > 0)) if down)
        if self.rest_start is not None:
            for side in ("left", "right"):
                if side + "x" in sample.axes and side + "y" in sample.axes:
                    self.points[side].append((sample.axes[side + "x"], sample.axes[side + "y"]))
            if sample.time - self.rest_start >= 5:
                self.rest = {side: rest_summary(points) for side, points in self.points.items() if len(points) >= 10}
                self.rest_start = None

    def measure_center(self, sample):
        if not any(s + "x" in sample.axes and s + "y" in sample.axes for s in ("left", "right")):
            raise ValueError("Map both axes of at least one stick before measuring its center.")
        self.rest_start, self.rest, self.points = sample.time, {}, {"left": [], "right": []}

    def next(self):
        if self.rest_start is not None:
            raise ValueError("Wait for the center measurement to finish, or cancel it first.")
        self.step = min(len(STEPS) - 1, self.step + 1)

    def report(self, family):
        report = self.session.report()
        names = button_names(family)
        report["rest_measurements"] = self.rest.copy()
        report["guided"] = {"buttons": [{"key": k, "name": names.get(k, k), "observed": k in self.seen}
                                             for k in sorted(self.expected)],
                            "vibration": self.vibration, "command_accepted": self.command_accepted,
                            "finished": self.step == len(STEPS) - 1 and not self.cancelled}
        return report

    def summary(self, family):
        report = self.report(family)
        buttons = report["guided"]["buttons"]
        lines = [f"Buttons / directions observed: {sum(b['observed'] for b in buttons)} of {len(buttons)}"]
        if buttons:
            names = button_names(family)
            pending = [names.get(key, key) for key in sorted(self.expected - self.seen)]
            lines.append("Pending: " + ", ".join(pending) if pending else "Every exposed button/direction was observed.")
        for side in ("left", "right"):
            stats = report[side + "_stick"]
            lines.append(f"{side.title()} stick: {stats['coverage'] * 100:.0f}% circle coverage" if stats["samples"] else f"{side.title()} stick: Not mapped")
        for key in ("lefttrigger", "righttrigger"):
            values = report["triggers"].get(key)
            lines.append(f"{key.replace('trigger', ' trigger').title()}: {values['min'] * 100:.0f}% to {values['max'] * 100:.0f}%" if values else key.replace("trigger", " trigger").title() + ": Not mapped")
        lines.append("Center: " + ("Measuring…" if self.rest_start is not None else "Measured" if self.rest else "Not measured"))
        lines.append("Vibration: " + self.vibration)
        return "\n".join(lines)


def capability_rows(device, sample, mapping=False, vibration=None):
    if device is None or not sample.connected:
        return [("Connection", "No live device", "Connect a controller or inspect saved reports.")]
    rows = [("Identity", "Detected family", device.identity),
            ("Input mapping", "Custom profile" if mapping else "SDL mapping" if sample.mapped else "Raw only",
             "A mapping describes input positions; it does not prove that every hardware feature works."),
            ("Raw inputs", "Readable", f"{len(sample.raw_axes)} axes, {len(sample.raw_buttons)} buttons, {len(sample.hats)} hats")]
    for side in ("left", "right"):
        rows.append((side.title() + " stick", "Mapped" if all(side + k in sample.axes for k in ("x", "y")) else "Not mapped", "Move the stick to verify its response."))
        rows.append((side.title() + " trigger", "Mapped" if side + "trigger" in sample.axes else "Not mapped", "Press and release to verify its range."))
    rows += [("Power", sample.power if sample.power != "unknown" else "Not reported", "Shown only when exposed by the input backend."),
             ("Vibration", vibration or "Not tested", "An accepted output command is separate from a felt motor response."),
             ("Connection transport", "Not reported", "This backend does not reliably distinguish USB from Bluetooth."),
             ("Advanced features", "Not implemented", "Gyro, touch coordinates, adaptive triggers and native Wii/adapter protocols are outside this release.")]
    return rows
