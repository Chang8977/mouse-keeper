"""Start with Windows, via the HKCU Run key.

Only ``HKEY_CURRENT_USER`` is touched, so no admin rights are needed and other
users are unaffected.
"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "MouseKeeper"


def _quote(path: str) -> str:
    return f'"{path}"'


def launch_command() -> str:
    """The command line that should launch this particular copy.

    In a packaged exe sys.frozen is true and the exe path is used directly. When
    running from source it has to be pythonw (not python), otherwise every boot
    pops up a console window.
    """
    if getattr(sys, "frozen", False):
        return _quote(sys.executable)

    main_py = Path(__file__).resolve().parent.parent / "main.py"
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else exe
    return f"{_quote(str(interpreter))} {_quote(str(main_py))}"


def _read() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return value
    except FileNotFoundError:
        return None
    except OSError:
        return None


def is_enabled() -> bool:
    """Only counts as enabled if an entry exists *and* points at this copy.

    That way, after the program is moved the menu shows it as off, one more
    click repoints it at the new path, and no dead entry is left behind.
    """
    return _read() == launch_command()


def is_stale() -> bool:
    """An entry exists but points somewhere else -- usually the program was moved."""
    current = _read()
    return current is not None and current != launch_command()


def enable() -> None:
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())


def disable() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass


def toggle() -> bool:
    """Returns the state after toggling."""
    if is_enabled():
        disable()
        return False
    enable()
    return True
