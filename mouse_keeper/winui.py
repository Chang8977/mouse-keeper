"""Win32 glue for window appearance: DPI, DWM rounded corners / dark title bar,
system theme and icons.

Kept in its own module because none of it has anything to do with the keep-alive
logic; mixing it into winapi.py would just make that file a mess.
"""

from __future__ import annotations

import ctypes
import winreg
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")

GA_ROOT = 2

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_DEFAULT = 0
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040

user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
user32.GetAncestor.restype = wintypes.HWND
user32.GetDpiForWindow.argtypes = (wintypes.HWND,)
user32.GetDpiForWindow.restype = wintypes.UINT
user32.LoadImageW.argtypes = (wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT)
user32.LoadImageW.restype = wintypes.HANDLE
user32.DestroyIcon.argtypes = (wintypes.HICON,)


def enable_dpi_awareness() -> bool:
    """Must be called before any window exists, or a high-DPI display will get a
    bitmap-stretched, blurry UI.

    DPI_AWARENESS_CONTEXT is a pointer-sized handle and has to be declared as
    c_void_p. Passing Python's -4 directly makes ctypes marshal a 32-bit int,
    leaving garbage in the upper half on 64-bit, and the call fails silently --
    the UI is still blurry and nothing reports an error.
    """
    try:
        user32.SetProcessDpiAwarenessContext.argtypes = (ctypes.c_void_p,)
        user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):  # PER_MONITOR_AWARE_V2
            return True
    except (AttributeError, OSError):
        pass
    try:  # Win 8.1 through early Win 10
        return bool(ctypes.WinDLL("shcore").SetProcessDpiAwareness(2) == 0)
    except OSError:
        pass
    try:
        return bool(user32.SetProcessDPIAware())
    except OSError:
        return False


def hwnd_of(widget) -> int:
    """The real top-level HWND of a tkinter window (winfo_id returns an inner child)."""
    return user32.GetAncestor(wintypes.HWND(widget.winfo_id()), GA_ROOT)


def dpi_of(widget) -> int:
    return user32.GetDpiForWindow(wintypes.HWND(hwnd_of(widget))) or 96


# --------------------------------------------------------------------------
# Monitors: which screen a point is on, its work area and its DPI
# --------------------------------------------------------------------------

MONITOR_DEFAULTTONEAREST = 2
MDT_EFFECTIVE_DPI = 0


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


# HMONITOR is a handle: declare it pointer-sized, for the same reason as the
# DPI context above.
user32.MonitorFromPoint.argtypes = (wintypes.POINT, wintypes.DWORD)
user32.MonitorFromPoint.restype = wintypes.HANDLE
user32.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.POINTER(MONITORINFO))
user32.GetMonitorInfoW.restype = wintypes.BOOL


def monitor_at(x: int, y: int) -> tuple[tuple[int, int, int, int], int] | None:
    """Work area ``(left, top, right, bottom)`` and DPI of the monitor holding
    the point (or the nearest one), in physical pixels.

    The work area excludes the taskbar, and on a multi-monitor setup it can sit
    at negative coordinates (a screen left of or above the primary one) --
    which is exactly what ``winfo_screenwidth`` / ``winfo_screenheight`` cannot
    describe, since they only ever report the primary screen's size.
    Returns None if the lookup fails, so callers can fall back.
    """
    try:
        hmon = user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)),
                                       MONITOR_DEFAULTTONEAREST)
        if not hmon:
            return None
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            return None
        rc = info.rcWork
        dpi = 96
        try:
            dx, dy = wintypes.UINT(), wintypes.UINT()
            if ctypes.WinDLL("shcore").GetDpiForMonitor(
                    wintypes.HANDLE(hmon), MDT_EFFECTIVE_DPI,
                    ctypes.byref(dx), ctypes.byref(dy)) == 0:
                dpi = dx.value or 96
        except OSError:
            pass
        return (rc.left, rc.top, rc.right, rc.bottom), dpi
    except (OSError, ctypes.ArgumentError):
        return None


def _set_attr(hwnd: int, attr: int, value: int) -> bool:
    v = ctypes.c_int(value)
    return dwmapi.DwmSetWindowAttribute(
        wintypes.HWND(hwnd), attr, ctypes.byref(v), ctypes.sizeof(v)) == 0


def round_corners(hwnd: int, small: bool = False) -> bool:
    """Win11 rounded corners. The attribute does not exist on Win10, where the
    call fails harmlessly."""
    return _set_attr(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                     DWMWCP_ROUNDSMALL if small else DWMWCP_ROUND)


def use_dark_titlebar(hwnd: int, dark: bool) -> bool:
    return _set_attr(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0)


def _personalize_flag(value_name: str) -> bool:
    """Read one of the *UsesLightTheme DWORDs under Personalize. 0 = dark."""
    try:
        with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, value_name)[0] == 0
    except OSError:
        return False


def system_uses_dark_theme() -> bool:
    """Whether *app* windows (title bars, menus) are in dark mode.

    Drives the Fluent panel's own colours.
    """
    return _personalize_flag("AppsUseLightTheme")


def taskbar_uses_dark_theme() -> bool:
    """Whether the *taskbar* (and Start, and notification area) is in dark mode.

    Windows lets this differ from the app theme above -- Settings >
    Personalization > Colors > Custom lets "Default Windows mode" and "Default
    app mode" be set independently. Drives which tray-icon artwork set is used:
    each set is designed for contrast against one specific taskbar colour, not
    both, so picking the wrong one is what makes a tray icon go illegible
    rather than just look slightly off.
    """
    return _personalize_flag("SystemUsesLightTheme")


def load_icon(path: str | Path) -> int:
    """Load an HICON from a .ico file. Returns 0 on failure."""
    return user32.LoadImageW(None, str(path), IMAGE_ICON, 0, 0,
                             LR_LOADFROMFILE | LR_DEFAULTSIZE) or 0


def destroy_icon(hicon: int) -> None:
    if hicon:
        user32.DestroyIcon(wintypes.HICON(hicon))
