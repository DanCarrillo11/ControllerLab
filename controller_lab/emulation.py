"""Explicit virtual output. Importing this module never creates a controller."""
from collections import deque
import math
import os
import time

from .model import Sample, deadzone, clamp

OUTPUT_BUTTONS = ("a", "b", "x", "y", "back", "start", "guide", "leftshoulder", "rightshoulder",
                  "leftstick", "rightstick", "dpup", "dpdown", "dpleft", "dpright", "touchpad")


def driver_status():
    result = {"vigem": False, "hidhide": False}
    if os.name == "nt":
        import winreg
        for key, name in (("vigem", "ViGEmBus"), ("hidhide", "HidHide")):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SYSTEM\\CurrentControlSet\\Services\\" + name):
                    result[key] = True
            except OSError:
                pass
    return result


def clean_settings(settings):
    settings = settings if isinstance(settings, dict) else {}
    def number(key, default, low, high):
        try:
            value = float(settings.get(key, default))
            return max(low, min(high, value)) if math.isfinite(value) else default
        except (TypeError, ValueError):
            return default
    bindings = settings.get("buttons", {})
    return {"target": "ds4" if settings.get("target") == "ds4" else "x360",
            "deadzone": number("deadzone", .08, 0, .4), "sensitivity": number("sensitivity", 1, .1, 2),
            "curve": settings.get("curve") if settings.get("curve") in ("linear", "squared", "cubic") else "linear",
            "trigger_deadzone": number("trigger_deadzone", .02, 0, .4),
            "swap_sticks": settings.get("swap_sticks") is True,
            "invert_left_y": settings.get("invert_left_y") is True,
            "invert_right_y": settings.get("invert_right_y") is True,
            "feedback": settings.get("feedback") is True,
            "buttons": {key: value for key, value in bindings.items() if isinstance(key, str)
                        and value in (*OUTPUT_BUTTONS, "")} if isinstance(bindings, dict) else {}}


def output_sample(sample, settings):
    """Build a new state; diagnostic raw values and measurements stay untouched."""
    config = clean_settings(settings)
    if not sample.connected:
        return Sample(connected=False)
    axes, buttons = {}, {}
    exponent = {"linear": 1, "squared": 2, "cubic": 3}[config["curve"]]
    def axis(key):
        try:
            value = float(sample.axes.get(key, 0))
            return clamp(value) if math.isfinite(value) else 0.
        except (TypeError, ValueError):
            return 0.
    for side in ("left", "right"):
        source = ("right" if side == "left" else "left") if config["swap_sticks"] else side
        x, y = axis(source + "x"), axis(source + "y")
        x, y = deadzone(x, y, config["deadzone"])
        radius = math.hypot(x, y)
        gain = min(1, radius ** exponent * config["sensitivity"]) / radius if radius else 0
        axes[side + "x"] = clamp(x * gain)
        axes[side + "y"] = clamp(y * gain * (-1 if config["invert_" + side + "_y"] else 1))
        threshold = config["trigger_deadzone"]
        axes[side + "trigger"] = clamp((axis(side + "trigger") - threshold) / (1 - threshold), 0, 1)
    for key, down in sample.buttons.items():
        target = config["buttons"].get(key, key)
        if down and target in OUTPUT_BUTTONS:
            buttons[target] = True
    for first, second in (("dpup", "dpdown"), ("dpleft", "dpright")):
        if buttons.get(first) and buttons.get(second):
            buttons[first] = buttons[second] = False
    return Sample(sample.time, axes, buttons, mapped=True)


class VirtualSink:
    """vgamepad/ViGEm target; the library is loaded only on explicit Start."""
    def __init__(self, target, feedback=False):
        import vgamepad as vg
        self.vg, self.target = vg, target
        self.pad = vg.VDS4Gamepad() if target == "ds4" else vg.VX360Gamepad()
        self.notifications = deque(maxlen=1)
        try:
            if feedback:
                def notification(client, target, large_motor, small_motor, led_number, user_data):
                    self.notifications.append((large_motor / 255, small_motor / 255))
                self.pad.register_notification(notification)
            self.write(Sample(connected=False))
        except Exception:
            self.close()
            raise

    def write(self, sample):
        pad, vg = self.pad, self.vg
        pad.reset()
        axes, buttons = sample.axes, sample.buttons
        # SDL and DS4 use positive Y down; Xbox XInput uses positive Y up.
        sign = 1 if self.target == "ds4" else -1
        pad.left_joystick_float(x_value_float=axes.get("leftx", 0), y_value_float=sign * axes.get("lefty", 0))
        pad.right_joystick_float(x_value_float=axes.get("rightx", 0), y_value_float=sign * axes.get("righty", 0))
        pad.left_trigger_float(value_float=axes.get("lefttrigger", 0))
        pad.right_trigger_float(value_float=axes.get("righttrigger", 0))
        if self.target == "x360":
            names = {"a": "A", "b": "B", "x": "X", "y": "Y", "back": "BACK", "start": "START", "guide": "GUIDE",
                     "leftshoulder": "LEFT_SHOULDER", "rightshoulder": "RIGHT_SHOULDER", "leftstick": "LEFT_THUMB",
                     "rightstick": "RIGHT_THUMB", "dpup": "DPAD_UP", "dpdown": "DPAD_DOWN", "dpleft": "DPAD_LEFT", "dpright": "DPAD_RIGHT"}
            for key, suffix in names.items():
                if buttons.get(key):
                    pad.press_button(button=getattr(vg.XUSB_BUTTON, "XUSB_GAMEPAD_" + suffix))
        else:
            names = {"a": "CROSS", "b": "CIRCLE", "x": "SQUARE", "y": "TRIANGLE", "back": "SHARE", "start": "OPTIONS",
                     "leftshoulder": "SHOULDER_LEFT", "rightshoulder": "SHOULDER_RIGHT", "leftstick": "THUMB_LEFT", "rightstick": "THUMB_RIGHT"}
            for key, suffix in names.items():
                if buttons.get(key):
                    pad.press_button(button=getattr(vg.DS4_BUTTONS, "DS4_BUTTON_" + suffix))
            for side, suffix in (("left", "LEFT"), ("right", "RIGHT")):
                if axes.get(side + "trigger", 0) > .01:
                    pad.press_button(button=getattr(vg.DS4_BUTTONS, "DS4_BUTTON_TRIGGER_" + suffix))
            for key, suffix in (("guide", "PS"), ("touchpad", "TOUCHPAD")):
                if buttons.get(key):
                    pad.press_special_button(special_button=getattr(vg.DS4_SPECIAL_BUTTONS, "DS4_SPECIAL_BUTTON_" + suffix))
            x = int(bool(buttons.get("dpright"))) - int(bool(buttons.get("dpleft")))
            y = int(bool(buttons.get("dpdown"))) - int(bool(buttons.get("dpup")))
            directions = {(0, -1): "NORTH", (1, -1): "NORTHEAST", (1, 0): "EAST", (1, 1): "SOUTHEAST",
                          (0, 1): "SOUTH", (-1, 1): "SOUTHWEST", (-1, 0): "WEST", (-1, -1): "NORTHWEST", (0, 0): "NONE"}
            pad.directional_pad(direction=getattr(vg.DS4_DPAD_DIRECTIONS, "DS4_BUTTON_DPAD_" + directions[(x, y)]))
        pad.update()

    def close(self):
        pad, self.pad = self.pad, None
        if pad is None:
            return
        try:
            if pad.cmp_func is not None:
                pad.unregister_notification()
                pad.cmp_func = None
            pad.reset()
            pad.update()
        finally:
            # No callback retains this target after unregistering. The library's
            # destructor detaches and frees it as this last reference is released.
            del pad


class Emulation:
    def __init__(self, factory=VirtualSink):
        self.factory, self.sink, self.source = factory, None, None
        self.settings, self.error = {}, ""
        self.feedback = (0., 0.)
        self.last_feedback = 0

    @property
    def running(self):
        return self.sink is not None

    def start(self, source, sample, settings):
        if self.running:
            raise ValueError("Stop the current output before starting another.")
        if not sample.connected or not sample.mapped:
            raise ValueError("Connect a controller and map its inputs first.")
        config = clean_settings(settings)
        sink = self.factory(config["target"], config["feedback"])
        self.source, self.sink, self.settings = source, sink, config
        self.error, self.feedback = "", (0., 0.)

    def update(self, source, sample):
        if not self.running:
            return
        if source != self.source or not sample.connected:
            self.stop()
            return
        try:
            self.sink.write(output_sample(sample, self.settings))
            if self.sink.notifications:
                self.feedback = self.sink.notifications.pop()
        except Exception as exc:
            self.error = str(exc)
            self.stop()

    def feedback_due(self, now=None):
        now = time.monotonic() if now is None else now
        if self.running and self.settings.get("feedback") and now - self.last_feedback >= .1:
            self.last_feedback = now
            return self.feedback
        return None

    def stop(self):
        sink, self.sink = self.sink, None
        self.source, self.feedback = None, (0., 0.)
        if sink is not None:
            try:
                sink.close()
            except Exception as exc:
                self.error = str(exc)
