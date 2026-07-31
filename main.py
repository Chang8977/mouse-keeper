"""Mouse Keeper entry point.

Usage:
    python main.py            # normal launch (lives in the tray)
    python main.py --check    # self-test: does SendInput really reset the
                              # system idle timer on this machine?
"""

from __future__ import annotations

import ctypes
import sys

from mouse_keeper import APP_NAME, __version__


def _message_box(text: str, title: str = APP_NAME) -> None:
    """Say something even with no console attached (a --noconsole exe)."""
    try:
        ctypes.WinDLL("user32").MessageBoxW(None, text, title, 0x40)
    except Exception:
        print(text)


def run_self_check() -> int:
    """Verify the premise the whole tool rests on: that an injected mouse event
    resets the idle timer.

    If this fails, SendInput is being blocked by the system or by security
    software, and running anyway will not stop Teams from going away.

    Output is English regardless of the UI language -- this is a diagnostic
    aimed at whoever is troubleshooting, and the README quotes it verbatim.
    """
    import time

    from mouse_keeper import autostart, winapi

    print(f"{APP_NAME} {__version__} self-check")
    print("-" * 52)

    locked = winapi.is_session_locked()
    print(f"Session lock probe : {'locked (injection cannot land)' if locked else 'unlocked'}")
    print(f"Start with Windows : {'on' if autostart.is_enabled() else 'off'}")
    print(f"Startup command    : {autostart.launch_command()}")

    print("\nWaiting 3 s to build up some idle time - please do not touch the mouse or keyboard ...")
    time.sleep(3)

    # Read the cursor position at the last possible moment. Taking it before the
    # wait would misreport "cursor did not return" whenever the user nudges the
    # mouse during those 3 seconds.
    x, y = winapi.get_cursor_pos()
    before = winapi.get_idle_seconds()
    print(f"Cursor before      : ({x}, {y})")
    print(f"Idle before        : {before:.2f}s")

    if before < 1.0:
        print()
        print("! Input was detected during the check, so this result is not trustworthy.")
        print("  Let go of the mouse and keyboard, wait a few seconds, and run --check again.")
        return 1

    ok = winapi.send_mouse_move(1, 0)
    time.sleep(0.05)
    ok = winapi.send_mouse_move(-1, 0) and ok
    time.sleep(0.1)

    after = winapi.get_idle_seconds()
    x2, y2 = winapi.get_cursor_pos()
    print(f"SendInput returned : {'ok' if ok else 'failed'}")
    print(f"Idle after         : {after:.2f}s")
    print(f"Cursor after       : ({x2}, {y2})")

    print("-" * 52)
    passed = ok and after < before and (x, y) == (x2, y2)
    if not ok:
        print("x SendInput failed - it may be blocked by security software.")
    elif after >= before:
        print("x The idle timer was not reset; this approach does not work on this machine.")
    elif (x, y) != (x2, y2):
        print("x The cursor did not return to its original spot. Either you touched the")
        print("  mouse during the check, or it sat against a screen edge (where the")
        print("  return move gets clamped). Both are harmless.")
    else:
        print("+ Self-check passed: injection works and the cursor returned exactly.")
    return 0 if passed else 1


def main() -> int:
    if "--check" in sys.argv:
        return run_self_check()

    from mouse_keeper import i18n, winapi
    from mouse_keeper.config import Config

    # A message box may be needed before App exists, so settle the language first
    i18n.set_language(Config.load().language)

    if not winapi.acquire_single_instance():
        _message_box(i18n.t("msg_already_running", app=APP_NAME))
        return 0

    from mouse_keeper.tray import App

    try:
        App().run()
    except Exception as exc:
        _message_box(i18n.t("msg_crashed", app=APP_NAME, err=repr(exc)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
