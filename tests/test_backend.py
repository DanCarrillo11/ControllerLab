from types import SimpleNamespace
import unittest
from controller_lab.backend import SDLBackend


class Joy:
    def __init__(self, iid):
        self.iid, self.closed, self.stops = iid, False, 0

    def get_instance_id(self): return self.iid
    def get_name(self): return "USB Gamepad"
    def get_guid(self): return "unknown"
    def get_numaxes(self): return 2
    def get_numbuttons(self): return 2
    def get_numhats(self): return 1
    def get_axis(self, i): return (.2, -.3)[i]
    def get_button(self, i): return i == 1
    def get_hat(self, i): return (0, 1)
    def get_power_level(self): return "unknown"
    def rumble(self, *args):
        self.effect = args
        return True
    def stop_rumble(self): self.stops += 1
    def quit(self): self.closed = True


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.joys = [Joy(14), Joy(19)]
        self.backend = SDLBackend.__new__(SDLBackend)
        self.backend.handles, self.backend.rumbling, self.backend.error = {}, set(), ""
        self.backend.pg = SimpleNamespace(error=RuntimeError,
            event=SimpleNamespace(pump=lambda: None, clear=lambda: None),
            joystick=SimpleNamespace(get_count=lambda: len(self.joys), Joystick=lambda i: self.joys[i]))
        self.backend.controllers = SimpleNamespace(is_controller=lambda i: False)

    def test_removal_and_device_index_shift_keep_correct_instance(self):
        self.backend.refresh()
        removed = self.joys.pop(0)
        remaining = self.backend.refresh()
        self.assertEqual([d.instance_id for d in remaining], [19])
        self.assertTrue(removed.closed)
        self.assertFalse(self.joys[0].closed)

    def test_raw_device_is_readable_without_guessing_axis_roles(self):
        self.backend.refresh()
        s = self.backend.poll(19)
        self.assertEqual(s.raw_axes, (.2, -.3))
        self.assertEqual(s.axes, {})
        self.assertFalse(s.mapped)

    def test_open_close_does_not_stop_rumble_started_by_another_app(self):
        self.backend.refresh()
        self.backend._release(self.backend.handles[14])
        self.assertEqual(self.joys[0].stops, 0)

    def test_only_own_rumble_is_stopped_and_duration_is_bounded(self):
        self.backend.refresh()
        self.assertTrue(self.backend.rumble(14, .5, .5, 10000))
        self.assertEqual(self.joys[0].effect, (.5, .5, 2000))
        self.backend.stop(14)
        self.assertEqual(self.joys[0].stops, 1)
        self.backend.stop(14)
        self.assertEqual(self.joys[0].stops, 1)

    def test_failed_controller_open_preserves_raw_device_access(self):
        self.backend.controllers.is_controller = lambda i: True
        def fail(index):
            raise RuntimeError("Controller mapping could not open")
        self.backend.controllers.Controller = fail
        self.assertEqual(len(self.backend.refresh()), 2)
        self.assertFalse(self.backend.poll(14).mapped)
