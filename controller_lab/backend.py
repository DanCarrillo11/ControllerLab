"""SDL2 input polling. No virtual controller, remapping driver or game hooks."""
import math
import os
import time

from .model import AXES, BUTTONS, Device, Sample, identify, signed_axis, clamp


class SDLBackend:
    def __init__(self):
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
        import pygame
        from pygame._sdl2 import controller
        self.pg, self.controllers = pygame, controller
        pygame.display.init()  # Event pumping without an SDL window.
        pygame.joystick.init()
        controller.init()
        self.handles = {}
        self.rumbling = set()
        self.error = ""

    def refresh(self):
        self.pg.event.pump()
        found = {}
        for index in range(self.pg.joystick.get_count()):
            try:
                joy = self.pg.joystick.Joystick(index)
                iid = joy.get_instance_id()
                if iid in self.handles:
                    found[iid] = self.handles[iid]
                    continue
                pad = None
                if self.controllers.is_controller(index):
                    try:
                        pad = self.controllers.Controller(index)
                    except self.pg.error as exc:
                        # Preserve raw access when a standard mapping cannot be opened.
                        self.error = str(exc)
                name, guid = joy.get_name(), joy.get_guid()
                family, evidence = identify(name, guid)
                device = Device(iid, name, guid, family, evidence, pad is not None,
                                joy.get_numaxes(), joy.get_numbuttons(), joy.get_numhats())
                found[iid] = (device, joy, pad)
            except self.pg.error as exc:
                self.error = str(exc)
        for iid in self.handles.keys() - found.keys():
            self._release(self.handles[iid])
        self.handles = found
        self.pg.event.clear()
        return [entry[0] for entry in found.values()]

    def poll(self, iid):
        entry = self.handles.get(iid)
        if not entry:
            return None
        device, joy, pad = entry
        try:
            self.pg.event.pump()
            if pad is not None and not pad.attached():
                return None
            raw_axes = tuple(joy.get_axis(i) for i in range(device.axes_count))
            raw_buttons = tuple(bool(joy.get_button(i)) for i in range(device.buttons_count))
            hats = tuple(joy.get_hat(i) for i in range(device.hats_count))
            axes, buttons = {}, {}
            if pad is not None:
                mapping = pad.get_mapping()
                for i, key in enumerate(AXES):
                    if key in mapping:
                        v = pad.get_axis(i)
                        axes[key] = clamp(v / 32767, 0, 1) if i >= 4 else signed_axis(v)
                for i, key in enumerate(BUTTONS):
                    if key in mapping:
                        buttons[key] = bool(pad.get_button(i))
            return Sample(time.monotonic(), axes, buttons, raw_axes, raw_buttons, hats,
                          joy.get_power_level(), pad is not None)
        except self.pg.error as exc:
            self.error = str(exc)
            return None

    def rumble(self, iid, low, high, duration=600):
        entry = self.handles.get(iid)
        if not entry:
            return False
        try:
            played = bool((entry[2] or entry[1]).rumble(clamp(low, 0, 1), clamp(high, 0, 1),
                                                     max(1, min(2000, int(duration)))))
            if played:
                self.rumbling.add(iid)
            return played
        except self.pg.error:
            return False

    def stop(self, iid):
        entry = self.handles.get(iid)
        if entry and iid in self.rumbling:
            try:
                (entry[2] or entry[1]).stop_rumble()
            except self.pg.error:
                pass
            self.rumbling.discard(iid)

    def _release(self, entry):
        try:
            self.stop(entry[0].instance_id)
            if entry[2] is not None:
                entry[2].quit()
            entry[1].quit()
        except self.pg.error:
            pass

    def close(self):
        for entry in list(self.handles.values()):
            self._release(entry)
        self.handles.clear()
        self.controllers.quit()
        self.pg.joystick.quit()
        self.pg.display.quit()


class DemoBackend:
    def __init__(self, family="dualsense"):
        self.family, self.error = family, ""
        self.start = time.monotonic()
        self.axis_keys = AXES[:2] if family == "wii" else AXES
        self.button_keys = BUTTONS[:15]
        if family == "dualsense":
            self.button_keys += ("misc1", "touchpad")
        elif family == "playstation":
            self.button_keys += ("touchpad",)
        elif family == "switch":
            self.button_keys += ("misc1",)
        elif family == "wii":
            self.button_keys = tuple(k for k in self.button_keys if k not in ("leftstick", "rightstick"))
        elif family == "gamecube":
            self.button_keys = tuple(k for k in self.button_keys if k not in ("leftstick", "rightstick", "guide", "back"))

    def refresh(self):
        from .model import FAMILIES
        return [Device(100, FAMILIES[self.family] + " (simulated)", "demo-" + self.family,
                       self.family, "Demo fixture, not detected hardware", True, len(self.axis_keys), len(self.button_keys), 1)]

    def poll(self, iid):
        t = time.monotonic() - self.start
        axes = dict(zip(AXES, (math.cos(t) * .68, math.sin(t) * .68, .018, -.012,
                              (math.sin(t * 1.3) + 1) / 2, (math.cos(t * .8) + 1) / 2)))
        axes = {k: v for k, v in axes.items() if k in self.axis_keys}
        buttons = dict.fromkeys(self.button_keys, False)
        buttons[BUTTONS[int(t) % 4]] = True
        return Sample(time.monotonic(), axes, buttons, tuple(axes.values()), tuple(buttons.values()),
                      ((0, 0),), "full", True)

    def rumble(self, *args):
        return False

    def stop(self, *args):
        pass

    def close(self):
        pass
