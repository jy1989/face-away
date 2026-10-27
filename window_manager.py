"""Best-effort snapshot / minimize / restore of normal Win32 top-level windows."""
import ctypes
import os
from dataclasses import dataclass

import win32con
import win32gui
import win32process


class _WindowTools:
    DWMWA_CLOAKED = 14

    @staticmethod
    def is_cloaked(hwnd: int) -> bool:
        try:
            value = ctypes.c_int()
            result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, _WindowTools.DWMWA_CLOAKED,
                ctypes.byref(value), ctypes.sizeof(value))
            return result == 0 and value.value != 0
        except Exception:
            return False


@dataclass
class WindowEntry:
    hwnd: int
    pid: int
    placement: tuple


class WindowManager:
    def __init__(self):
        self.entries: list[WindowEntry] = []
        self.foreground: int | None = None

    def minimize_all(self) -> int:
        """Save only windows currently shown, skip already minimized windows."""
        if self.entries:
            return len(self.entries)
        collected: list[WindowEntry] = []
        self_pid = os.getpid()

        def collect(hwnd, _):
            try:
                if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                    return
                if win32gui.IsIconic(hwnd) or _WindowTools.is_cloaked(hwnd):
                    return
                if not win32gui.GetWindowText(hwnd).strip():
                    return
                name = win32gui.GetClassName(hwnd)
                if name in {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW", "DV2ControlHost"}:
                    return
                exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if exstyle & (win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE):
                    return
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid == self_pid:
                    return
                placement = win32gui.GetWindowPlacement(hwnd)
                collected.append(WindowEntry(hwnd, pid, placement))
            except Exception:
                pass

        win32gui.EnumWindows(collect, None)
        try:
            self.foreground = win32gui.GetForegroundWindow()
        except Exception:
            self.foreground = None

        minimized = []
        for item in collected:
            try:
                if win32gui.IsWindow(item.hwnd):
                    win32gui.ShowWindow(item.hwnd, win32con.SW_MINIMIZE)
                    if win32gui.IsIconic(item.hwnd):
                        minimized.append(item)
            except Exception:
                pass
        self.entries = minimized
        return len(minimized)

    def restore(self) -> int:
        entries, self.entries = self.entries, []
        count = 0
        for item in reversed(entries):
            try:
                if not win32gui.IsWindow(item.hwnd):
                    continue
                _, current_pid = win32process.GetWindowThreadProcessId(item.hwnd)
                if current_pid != item.pid:
                    continue
                win32gui.SetWindowPlacement(item.hwnd, item.placement)
                count += 1
            except Exception:
                pass
        if self.foreground is not None:
            try:
                if win32gui.IsWindow(self.foreground):
                    win32gui.SetForegroundWindow(self.foreground)
            except Exception:
                pass
        self.foreground = None
        return count
