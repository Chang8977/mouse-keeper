"""Reading, writing and validating the config.

The file lives in %APPDATA%\\MouseKeeper\\config.json so that settings persist
even for a onefile exe, which may sit in a read-only directory or unpack itself
to a fresh temp folder on every launch.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from . import schedule
from .i18n import LANGUAGES

MODE_SMART = "smart"
MODE_FORCE = "force"
VALID_MODES = (MODE_SMART, MODE_FORCE)


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "MouseKeeper"


def config_path() -> Path:
    return config_dir() / "config.json"


def log_path() -> Path:
    return config_dir() / "mouse-keeper.log"


@dataclass
class Config:
    #: smart = only move once you have actually stepped away; force = move on a timer
    mode: str = MODE_SMART
    #: Smart mode: idle seconds before injecting (also the cadence while away)
    idle_threshold_sec: int = 60
    #: Always mode: fixed seconds between injections
    interval_sec: int = 45
    #: Pixels per injection (moved out and straight back, so the cursor ends up put)
    move_pixels: int = 1
    #: Whether to block screen-off and sleep as well
    keep_display_on: bool = True
    #: Stop automatically after this many hours of running; 0 means never
    auto_stop_hours: float = 8.0
    #: UI language. "auto" follows the Windows display language.
    language: str = "auto"
    #: Global pause / resume hotkey; an empty string turns it off
    hotkey: str = "ctrl+alt+f12"
    #: Follow a work-hours schedule: switch on when a window opens, off when it
    #: closes. Manual toggles in between still work (see engine).
    schedule_enabled: bool = False
    #: Weekdays the schedule covers, Monday = 0 ... Sunday = 6
    schedule_days: list[int] = field(default_factory=lambda: list(schedule.DEFAULT_DAYS))
    #: "HH:MM". An end earlier than the start runs past midnight.
    schedule_start: str = schedule.DEFAULT_START
    schedule_end: str = schedule.DEFAULT_END
    #: Look for a newer release on GitHub (once at startup, then daily)
    check_updates: bool = True
    #: Last time picked in the panel's "Pause until" row ("HH:MM")
    pause_until: str = schedule.DEFAULT_PAUSE_UNTIL
    #: Start keeping alive immediately on launch
    start_active: bool = True
    #: Write a log file
    log_enabled: bool = False

    # ------------------------------------------------------------------
    def clamp(self) -> None:
        """Pull out-of-range values back in so a hand-edited file cannot break things."""
        if self.mode not in VALID_MODES:
            self.mode = MODE_SMART
        self.idle_threshold_sec = _clamp_int(self.idle_threshold_sec, 10, 280, 60)
        self.interval_sec = _clamp_int(self.interval_sec, 5, 280, 45)
        self.move_pixels = _clamp_int(self.move_pixels, 1, 50, 1)
        self.auto_stop_hours = _clamp_float(self.auto_stop_hours, 0.0, 72.0, 8.0)
        self.keep_display_on = bool(self.keep_display_on)
        self.start_active = bool(self.start_active)
        self.log_enabled = bool(self.log_enabled)
        # "" is a deliberate "no hotkey"; only a non-string is treated as broken
        if not isinstance(self.hotkey, str):
            self.hotkey = "ctrl+alt+f12"
        self.hotkey = self.hotkey.strip().lower()
        self.schedule_enabled = bool(self.schedule_enabled)
        self.schedule_days = schedule.clean_days(self.schedule_days)
        self.schedule_start = schedule.fmt_hhmm(
            schedule.parse_hhmm(self.schedule_start, schedule.DEFAULT_START))
        self.schedule_end = schedule.fmt_hhmm(
            schedule.parse_hhmm(self.schedule_end, schedule.DEFAULT_END))
        self.check_updates = bool(self.check_updates)
        self.pause_until = schedule.fmt_hhmm(
            schedule.parse_hhmm(self.pause_until, schedule.DEFAULT_PAUSE_UNTIL))
        if self.language != "auto" and self.language not in LANGUAGES:
            self.language = "auto"

    @property
    def cadence_sec(self) -> int:
        """The cadence that actually applies: idle threshold for Smart, interval for Always."""
        return self.idle_threshold_sec if self.mode == MODE_SMART else self.interval_sec

    def set_cadence(self, seconds: int) -> None:
        if self.mode == MODE_SMART:
            self.idle_threshold_sec = seconds
        else:
            self.interval_sec = seconds

    # ------------------------------------------------------------------
    @classmethod
    def load(cls) -> "Config":
        path = config_path()
        cfg = cls()
        if path.exists():
            try:
                # utf-8-sig: a hand-edited config often carries a BOM (Notepad
                # and PowerShell's Out-File both add one), and plain utf-8 would
                # blow up with a JSONDecodeError on it.
                raw = json.loads(path.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, OSError):
                raw = {}
            known = {f.name for f in fields(cls)}
            for key, value in raw.items():
                if key in known:
                    setattr(cfg, key, value)
        cfg.clamp()
        return cfg

    def save(self) -> None:
        self.clamp()
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(self), indent=2, ensure_ascii=False)
        # Write to a temp file and swap it in, so losing power mid-write cannot
        # leave a half-written config behind.
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)


def _clamp_int(value, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _clamp_float(value, low: float, high: float, default: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default
