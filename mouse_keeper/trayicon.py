"""Our own tray icon implementation (Shell_NotifyIcon).

Why not pystray: its context menu is a native Win32 HMENU (CreatePopupMenu +
TrackPopupMenuEx) drawn by the system, with no owner-draw hook whatsoever, so
rounded corners and hover highlights are impossible. It also does not expose a
right-click callback we could use to pop up a window of our own. Hence this
layer is hand-rolled, and right-click goes to our Fluent panel.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Callable

from . import winui

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_DESTROY = 0x0002

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
NIIF_NONE = 0x00

LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)

# Without argtypes ctypes treats LPARAM as a 32-bit int, and the large values
# the system passes raise OverflowError -- silently, from inside the callback.
user32.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM)
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.restype = wintypes.HWND
user32.PeekMessageW.argtypes = (ctypes.c_void_p, wintypes.HWND,
                                wintypes.UINT, wintypes.UINT, wintypes.UINT)


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
    ]


class TrayIcon:
    """One tray icon plus one hidden message window.

    Messages are drained by ``pump()``: the caller just ticks it from tkinter's
    ``after`` loop. No extra thread, and therefore no cross-thread UI updates to
    worry about.
    """

    def __init__(self, tooltip: str, on_left: Callable[[], None],
                 on_right: Callable[[], None], class_name: str = "MouseKeeperTray"):
        self._on_left = on_left
        self._on_right = on_right
        self._hicon = 0
        self._added = False
        self._msg = wintypes.MSG()

        # The WNDPROC reference must be kept alive; once it is garbage collected
        # the system callback would jump into a dangling pointer.
        self._proc = WNDPROC(self._wndproc)
        hinst = kernel32.GetModuleHandleW(None)

        wc = WNDCLASS()
        wc.lpfnWndProc = self._proc
        wc.hInstance = hinst
        wc.lpszClassName = class_name
        self._atom = user32.RegisterClassW(ctypes.byref(wc))
        self._wc = wc  # likewise has to stay referenced

        self.hwnd = user32.CreateWindowExW(0, class_name, class_name, 0,
                                           0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            raise OSError(f"could not create the tray message window: "
                          f"{ctypes.get_last_error()}")

        self._nid = NOTIFYICONDATA()
        self._nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        self._nid.hWnd = self.hwnd
        self._nid.uID = 1
        self._nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        self._nid.uCallbackMessage = WM_TRAYICON
        self._nid.szTip = tooltip[:127]

    # ------------------------------------------------------------------
    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAYICON:
            try:
                if lparam == WM_LBUTTONUP:
                    self._on_left()
                elif lparam == WM_RBUTTONUP:
                    self._on_right()
            except Exception:
                pass  # an exception in a callback must not kill the window proc
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # ------------------------------------------------------------------
    def show(self, icon_path: str | Path) -> bool:
        self.set_icon(icon_path)
        ok = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid)))
        self._added = ok
        return ok

    def set_icon(self, icon_path: str | Path) -> None:
        new_icon = winui.load_icon(icon_path)
        if not new_icon:
            return
        old, self._hicon = self._hicon, new_icon
        self._nid.hIcon = new_icon
        if self._added:
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))
        winui.destroy_icon(old)

    def set_tooltip(self, text: str) -> None:
        self._nid.szTip = text[:127]
        if self._added:
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def notify(self, message: str, title: str) -> None:
        self._nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_INFO
        self._nid.szInfo = message[:255]
        self._nid.szInfoTitle = title[:63]
        self._nid.dwInfoFlags = NIIF_NONE
        if self._added:
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))
        self._nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        self._nid.szInfo = ""

    def foreground(self) -> None:
        """Bring the message window to the foreground before showing the panel.

        Otherwise Windows does not consider us the foreground process, the popup
        never gains focus, and clicking elsewhere never produces the focus-out
        that dismisses it -- the panel just sits there.
        """
        user32.SetForegroundWindow(wintypes.HWND(self.hwnd))

    def pump(self) -> None:
        """Dispatch messages for **this window**.

        tkinter's mainloop makes no promise about dispatching messages for
        windows we created ourselves, so Peek/Dispatch them here.

        The second argument must be our own hwnd, as a filter. Passing None
        drains the entire thread queue -- tkinter's messages included -- and
        DispatchMessage outside Tk's notifier does not make Tk generate the
        corresponding Tk events. The result is that mouse moves and clicks are
        silently swallowed and the UI looks dead.
        """
        hwnd = wintypes.HWND(self.hwnd)
        while user32.PeekMessageW(ctypes.byref(self._msg), hwnd, 0, 0, 1):  # PM_REMOVE
            user32.TranslateMessage(ctypes.byref(self._msg))
            user32.DispatchMessageW(ctypes.byref(self._msg))

    def close(self) -> None:
        if self._added:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            self._added = False
        winui.destroy_icon(self._hicon)
        self._hicon = 0
        if self.hwnd:
            user32.DestroyWindow(wintypes.HWND(self.hwnd))
            self.hwnd = 0
