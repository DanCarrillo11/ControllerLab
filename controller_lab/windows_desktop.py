"""Small Windows APIs: read process paths and register one stop shortcut. No hooks."""
import ctypes
from ctypes import wintypes
import os

from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
from PySide6.QtGui import QKeySequence


def hotkey_parts(text):
    sequence = QKeySequence.fromString(text, QKeySequence.SequenceFormat.PortableText)
    if sequence.count() != 1:
        raise ValueError("Use one shortcut, such as Ctrl+Alt+F11.")
    from PySide6.QtCore import Qt
    combination = sequence[0]
    modifiers, key = combination.keyboardModifiers(), combination.key().value
    if modifiers & Qt.KeyboardModifier.MetaModifier or not modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
        raise ValueError("Include Ctrl or Alt. Windows-key shortcuts are reserved.")
    if Qt.Key.Key_F1.value <= key <= Qt.Key.Key_F24.value:
        virtual = 0x70 + key - Qt.Key.Key_F1.value
        if key == Qt.Key.Key_F12.value:
            raise ValueError("F12 is reserved by Windows. Choose another key.")
    elif ord("A") <= key <= ord("Z") or ord("0") <= key <= ord("9"):
        virtual = key
    else:
        raise ValueError("Use a letter, number or F1–F24 (except F12), with Ctrl or Alt.")
    native = 0x4000
    for flag, value in ((Qt.KeyboardModifier.AltModifier, 1), (Qt.KeyboardModifier.ControlModifier, 2), (Qt.KeyboardModifier.ShiftModifier, 4)):
        if modifiers & flag:
            native |= value
    return sequence.toString(QKeySequence.SequenceFormat.PortableText), native, virtual


class StopHotkey(QAbstractNativeEventFilter):
    def __init__(self, application, callback, enabled=True):
        super().__init__()
        self.application, self.callback, self.enabled = application, callback, enabled
        self.identifier, self.text, self.error = None, "", ""
        self.next_id = 0x4340
        self.api = ctypes.WinDLL("user32", use_last_error=True) if enabled and os.name == "nt" else None
        if self.api:
            self.api.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
            self.api.RegisterHotKey.restype = wintypes.BOOL
            self.api.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
            self.api.UnregisterHotKey.restype = wintypes.BOOL
            application.installNativeEventFilter(self)

    def configure(self, text, enabled=True):
        canonical, modifiers, key = hotkey_parts(text)
        if not enabled:
            self.unregister()
            self.error = ""
            return True
        if self.identifier is not None and canonical == self.text:
            self.error = ""
            return True
        if not self.api:
            self.error = "Global shortcuts are available in the Windows desktop app."
            return False
        candidate = self.next_id
        self.next_id = 0x4340 if candidate >= 0x4FFF else candidate + 1
        if not self.api.RegisterHotKey(None, candidate, modifiers, key):
            self.error = "Shortcut unavailable or already used by another app (Windows error " + str(ctypes.get_last_error()) + ")."
            return False  # Preserve the old registered shortcut on conflict.
        self.unregister()
        self.identifier, self.text, self.error = candidate, canonical, ""
        return True

    def unregister(self):
        if self.identifier is not None and self.api:
            self.api.UnregisterHotKey(None, self.identifier)
        self.identifier, self.text = None, ""

    def nativeEventFilter(self, event_type, message):
        if self.identifier is not None and bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == self.identifier:
                QTimer.singleShot(0, self.callback)
                return True, 0
        return False, 0

    def close(self):
        self.unregister()
        if self.api:
            self.application.removeNativeEventFilter(self)


def running_game_paths(wanted):
    """Read only configured executable paths; do not launch or inspect game memory."""
    if os.name != "nt":
        return dict(running=[], foreground="", error="Automatic game profiles require Windows.")
    from .desktop_settings import executable_key
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user = ctypes.WinDLL("user32", use_last_error=True)
    class ProcessEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260)]
    kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
    kernel.Process32FirstW.restype = kernel.Process32NextW.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = (wintypes.HANDLE,), wintypes.BOOL
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    foreground_pid = wintypes.DWORD()
    user.GetWindowThreadProcessId(user.GetForegroundWindow(), ctypes.byref(foreground_pid))
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return dict(running=[], foreground="", error="Windows could not list running games.")
    found, foreground = set(), ""
    wanted = set(wanted)
    names = {os.path.basename(path).casefold() for path in wanted}
    entry = ProcessEntry()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        more = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        if not more and ctypes.get_last_error() != 18:
            return dict(running=[], foreground="", error="Windows could not read the process snapshot.")
        while more:
            if entry.szExeFile.casefold() in names:
                handle = kernel.OpenProcess(0x1000, False, entry.th32ProcessID)
                if handle:
                    try:
                        buffer, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
                        if kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                            path = executable_key(buffer.value)
                            if path in wanted:
                                found.add(path)
                                if entry.th32ProcessID == foreground_pid.value:
                                    foreground = path
                    finally:
                        kernel.CloseHandle(handle)
            more = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:
            return dict(running=[], foreground="", error="Windows could not finish reading running games.")
    finally:
        kernel.CloseHandle(snapshot)
    return dict(running=sorted(found), foreground=foreground, error="")
