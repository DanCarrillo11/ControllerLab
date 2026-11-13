"""Explicit native desktop check without showing UI or creating virtual output."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QSystemTrayIcon

from . import VERSION
from .desktop_settings import executable_key
from .storage import atomic_write
from .windows_desktop import StopHotkey, running_game_paths


def check_desktop(application, destination):
    result = dict(version=VERSION, platform=os.name, virtual_output_created=False,
                  physical_inputs_forwarded=False, vibration_requested=False,
                  tray_available=QSystemTrayIcon.isSystemTrayAvailable(), hotkey_message_received=False)
    if os.name != "nt" or application.platformName() != "windows":
        result.update(ready=False, error="This explicit check requires Windows desktop Qt.")
        atomic_write(destination, json.dumps(result, indent=2))
        return 2
    path = executable_key(str(Path(sys.executable).resolve()))
    processes = running_game_paths({path})
    result["process_path_readback"] = path in processes["running"]
    shortcut = StopHotkey(application, lambda: received(), enabled=True)
    def received():
        result["hotkey_message_received"] = True
        application.quit()
    try:
        result["hotkey_registered"] = shortcut.configure("Ctrl+Alt+Shift+F9")
        if result["hotkey_registered"]:
            user, kernel = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("kernel32", use_last_error=True)
            user.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
            user.PostThreadMessageW.restype = wintypes.BOOL
            kernel.GetCurrentThreadId.restype = wintypes.DWORD
            thread, identifier = kernel.GetCurrentThreadId(), shortcut.identifier
            # Exercise Qt's native message routing, without synthesizing keyboard input.
            QTimer.singleShot(0, lambda: user.PostThreadMessageW(thread, 0x0312, identifier, 0))
            QTimer.singleShot(2500, application.quit)
            application.exec()
        else:
            result["error"] = shortcut.error
    finally:
        shortcut.close()
    result["hotkey_unregistered"] = shortcut.identifier is None
    result["ready"] = all(result.get(k) is True for k in ("process_path_readback", "hotkey_registered", "hotkey_message_received", "hotkey_unregistered"))
    atomic_write(destination, json.dumps(result, indent=2))
    return 0 if result["ready"] else 2
