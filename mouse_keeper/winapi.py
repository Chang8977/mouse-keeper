"""Minimal Win32 wrappers, called straight through ctypes with no third-party deps.

This module is the core of the tool and covers four things:

1. ``send_mouse_move`` -- injects a **real** mouse input event via ``SendInput``.
   Do not reach for ``SetCursorPos``: it only relocates the cursor and never
   updates the system "last input time", so anything that judges idleness from
   ``GetLastInputInfo`` (Teams among them) will still mark you as away.
2. ``get_idle_seconds`` -- reads ``GetLastInputInfo`` to tell whether the user
   has actually stepped away.
3. ``keep_awake`` -- ``SetThreadExecutionState`` to block screen-off and sleep.
   That state is **per-thread** and has to be held by a long-lived thread.
4. ``HotKeyListener`` -- ``RegisterHotKey`` plus a message loop for global hotkeys.
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ULONG_PTR differs in width between 32- and 64-bit; wintypes.WPARAM happens to
# be exactly the pointer-sized unsigned integer we need.
ULONG_PTR = wintypes.WPARAM


# --------------------------------------------------------------------------
# SendInput: injecting mouse movement
# --------------------------------------------------------------------------

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001  # relative move (relative is the default without ABSOLUTE)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT


def send_mouse_move(dx: int, dy: int = 0) -> bool:
    """Inject one relative mouse move. Returns whether it succeeded.

    Windows still counts a zero-delta event as input and refreshes the idle
    timer, but some drivers optimise all-zero events away, so callers should
    pass a non-zero delta and move back afterwards.
    """
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi = MOUSEINPUT(dx=dx, dy=dy, mouseData=0, dwFlags=MOUSEEVENTF_MOVE, time=0, dwExtraInfo=0)
    sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    return sent == 1


def get_cursor_pos() -> tuple[int, int]:
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


# --------------------------------------------------------------------------
# GetLastInputInfo: idle time
# --------------------------------------------------------------------------


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


kernel32.GetTickCount.restype = wintypes.DWORD


def get_idle_seconds() -> float:
    """Seconds since the last real (or injected) input event.

    dwTime shares its origin with GetTickCount: both are 32-bit millisecond
    counters that wrap roughly every 49.7 days. Masking the subtraction keeps
    the result unsigned so it never goes negative across a wrap.
    """
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(lii)):
        return 0.0
    elapsed_ms = (kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF
    return elapsed_ms / 1000.0


# --------------------------------------------------------------------------
# SetThreadExecutionState: block screen-off / sleep
# --------------------------------------------------------------------------

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

kernel32.SetThreadExecutionState.argtypes = (wintypes.DWORD,)
kernel32.SetThreadExecutionState.restype = wintypes.DWORD


def keep_awake(display: bool = True) -> None:
    """Declare "this thread is busy" to block sleep, optionally the display too.

    A long-lived thread has to keep asserting this; Windows clears the state
    automatically as soon as that thread exits.
    """
    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    if display:
        flags |= ES_DISPLAY_REQUIRED
    kernel32.SetThreadExecutionState(flags)


def release_awake() -> None:
    """Drop the declaration above and restore default power behaviour."""
    kernel32.SetThreadExecutionState(ES_CONTINUOUS)


# --------------------------------------------------------------------------
# Is the session locked?
# --------------------------------------------------------------------------

DESKTOP_SWITCHDESKTOP = 0x0100

# The return type must be declared explicitly: ctypes defaults to c_int, which
# truncates the upper half of a desktop handle on 64-bit and would leave
# CloseDesktop closing a bogus handle.
user32.OpenInputDesktop.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
user32.OpenInputDesktop.restype = wintypes.HANDLE
user32.CloseDesktop.argtypes = (wintypes.HANDLE,)
user32.CloseDesktop.restype = wintypes.BOOL


def is_session_locked() -> bool:
    """Whether the session is locked / on the secure desktop / disconnected.

    How it works: locking switches the input desktop to Winlogon's secure
    desktop, after which ``OpenInputDesktop`` fails for an ordinary process.
    Compared with ``WTSRegisterSessionNotification`` this needs no hidden window
    and no message loop -- it can simply be polled from the main loop.

    Note this probes rather than subscribes, so it cannot tell a locked session
    apart from a disconnected RDP one. For our purposes they are the same case:
    injection will not land, so stop.
    """
    hdesk = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
    if not hdesk:
        return True
    user32.CloseDesktop(hdesk)
    return False


# --------------------------------------------------------------------------
# Single-instance mutex
# --------------------------------------------------------------------------

ERROR_ALREADY_EXISTS = 183
_mutex_handle = None


def acquire_single_instance(name: str = "Global\\MouseKeeperSingleInstance") -> bool:
    """Try to take the single-instance lock. False means one is already running.

    The handle is parked in a module-level variable and reclaimed by the system
    when the process exits.
    """
    global _mutex_handle
    handle = kernel32.CreateMutexW(None, wintypes.BOOL(True), name)
    if not handle:
        return True  # failing to get a mutex should not block startup
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _mutex_handle = handle
    return True


# --------------------------------------------------------------------------
# RegisterHotKey: global hotkey
# --------------------------------------------------------------------------

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_MODIFIER_NAMES = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
}

# Only the keys people actually bind; that is plenty for a config file.
_VK_NAMES = {
    **{f"f{i}": 0x6F + i for i in range(1, 25)},  # F1=0x70 ... F24=0x87
    "space": 0x20,
    "escape": 0x1B,
    "esc": 0x1B,
    "insert": 0x2D,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "pause": 0x13,
    "scrolllock": 0x91,
    "pageup": 0x21,
    "pagedown": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
}
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
    _VK_NAMES[_c.lower()] = ord(_c)
for _i in range(10):
    _VK_NAMES[f"num{_i}"] = 0x60 + _i

#: vk -> canonical name, for turning a captured key press back into a spec.
#: Built from _VK_NAMES so the two can never disagree; where a key has two
#: names the first one listed wins ("escape" over "esc").
_NAME_OF_VK: dict[int, str] = {}
for _name, _vk in _VK_NAMES.items():
    _NAME_OF_VK.setdefault(_vk, _name)

#: Display names that plain capitalisation would get wrong
_DISPLAY_NAMES = {"ctrl": "Ctrl", "control": "Ctrl", "escape": "Esc", "esc": "Esc",
                  "pageup": "PgUp", "pagedown": "PgDn", "scrolllock": "ScrollLock"}

#: Canonical modifier order for display and storage
_MOD_ORDER = (("ctrl", MOD_CONTROL), ("alt", MOD_ALT), ("shift", MOD_SHIFT), ("win", MOD_WIN))

VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN = 0x10, 0x11, 0x12, 0x5B, 0x5C
#: Keys that are only ever modifiers (incl. the left/right-specific codes)
_MODIFIER_VKS = {VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN,
                 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}

user32.GetKeyState.argtypes = (ctypes.c_int,)
user32.GetKeyState.restype = ctypes.c_short


def held_modifiers() -> int:
    """MOD_* flags for the modifier keys down right now, as seen by the thread
    processing the current key message (GetKeyState, not GetAsyncKeyState)."""
    def down(vk: int) -> bool:
        return bool(user32.GetKeyState(vk) & 0x8000)
    mods = 0
    if down(VK_CONTROL):
        mods |= MOD_CONTROL
    if down(VK_MENU):
        mods |= MOD_ALT
    if down(VK_SHIFT):
        mods |= MOD_SHIFT
    if down(VK_LWIN) or down(VK_RWIN):
        mods |= MOD_WIN
    return mods


def is_modifier_vk(vk: int) -> bool:
    return vk in _MODIFIER_VKS


def hotkey_spec(modifiers: int, vk: int) -> str | None:
    """(MOD_* flags, vk) -> "ctrl+alt+f12", or None if vk is not a bindable key."""
    name = _NAME_OF_VK.get(vk)
    if name is None:
        return None
    parts = [n for n, flag in _MOD_ORDER if modifiers & flag]
    return "+".join(parts + [name])


def format_hotkey(spec: str) -> str:
    """"ctrl+alt+f12" -> "Ctrl+Alt+F12" for display."""
    out = []
    for part in (p.strip().lower() for p in spec.split("+") if p.strip()):
        if part in _DISPLAY_NAMES:
            out.append(_DISPLAY_NAMES[part])
        elif len(part) == 1 or (part[0] == "f" and part[1:].isdigit()):
            out.append(part.upper())
        elif part.startswith("num") and part[3:].isdigit():
            out.append("Num " + part[3:])
        else:
            out.append(part.capitalize())
    return "+".join(out)


class HotKeyParseError(ValueError):
    pass


def parse_hotkey(spec: str) -> tuple[int, int]:
    """Parse "ctrl+alt+f12" into (modifiers, vk)."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if not parts:
        raise HotKeyParseError(f"empty hotkey: {spec!r}")
    modifiers = 0
    vk = None
    for part in parts:
        if part in _MODIFIER_NAMES:
            modifiers |= _MODIFIER_NAMES[part]
        elif part in _VK_NAMES:
            if vk is not None:
                raise HotKeyParseError(f"hotkey {spec!r} has more than one main key")
            vk = _VK_NAMES[part]
        else:
            raise HotKeyParseError(f"unrecognised key: {part!r} (in {spec!r})")
    if vk is None:
        raise HotKeyParseError(f"hotkey {spec!r} has no main key")
    return modifiers | MOD_NOREPEAT, vk


class HotKeyListener(threading.Thread):
    """Registers a global hotkey and pumps its messages on a dedicated thread.

    RegisterHotKey requires the registering thread to pump its own messages, so
    this has to be a thread of its own running a GetMessage loop; the main
    thread is not available because the tray UI owns it.
    """

    def __init__(self, spec: str, callback: Callable[[], None]):
        super().__init__(name="hotkey", daemon=True)
        self.spec = spec
        self.callback = callback
        self.error: str | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()

    def run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        try:
            modifiers, vk = parse_hotkey(self.spec)
        except HotKeyParseError as exc:
            self.error = str(exc)
            self._ready.set()
            return

        if not user32.RegisterHotKey(None, 1, modifiers, vk):
            self.error = f"could not register {self.spec} (another app may own it)"
            self._ready.set()
            return
        self._ready.set()

        try:
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    try:
                        self.callback()
                    except Exception:  # a failing callback must not kill the loop
                        pass
        finally:
            user32.UnregisterHotKey(None, 1)

    def wait_ready(self, timeout: float = 2.0) -> None:
        self._ready.wait(timeout)

    def stop(self) -> None:
        if self._thread_id is not None:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
