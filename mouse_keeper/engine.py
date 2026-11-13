"""The keep-alive engine: one long-lived background thread.

The thread stays alive even while paused, for two reasons:
  * the sleep-blocking state from ``SetThreadExecutionState`` is per-thread and
    evaporates the moment that thread exits;
  * pause/resume is just a flag flip, which is simpler and more reliable than
    starting and stopping a thread over and over.

The main loop deliberately avoids ``WM_TIMER``-style message timers: on Modern
Standby (S0 low-power idle) machines those messages can stop being delivered
once the display turns off, and a message-driven jiggler then stalls forever
(arkane-systems/mousejiggler#130). This uses a dedicated thread plus
``Event.wait``, with a stall watchdog on top so it recovers by itself after the
machine has been frozen.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from . import schedule, winapi
from .config import MODE_SMART, Config
from .i18n import t

#: Main-loop heartbeat. Smaller means faster reaction to pause/exit.
TICK_SEC = 1.0
#: Gap between the "move out" and "move back" halves of one jiggle.
JIGGLE_GAP_SEC = 0.05
#: A tick that really took longer than this means the system was frozen/asleep.
STALL_THRESHOLD_SEC = 10.0


@dataclass
class Stats:
    jiggles: int = 0
    #: Wall-clock start of the current "running" stretch. Wall clock rather than
    #: monotonic so that "stop after N hours" still behaves intuitively across
    #: a sleep.
    started_at: float = 0.0
    last_jiggle_at: float = 0.0
    auto_stopped: bool = False   # stopped because the run-time limit was hit
    stalls: int = 0              # how many freeze/wake events were detected
    blocked: bool = False        # currently unable to inject (locked session)
    off_hours: bool = False      # paused because the work-hours window closed
    #: When a timed pause ("pause until 13:30") ends; None when there is none
    resume_at: datetime | None = None
    #: Something the engine switched by itself that deserves a notification:
    #: "on" / "off" (work hours began / ended) or "resume" (a timed pause
    #: ended). The UI consumes it -- resets it to "" -- so it shows exactly once.
    event: str = ""

    @property
    def active_seconds(self) -> float:
        if not self.started_at:
            return 0.0
        # A clock change (NTP sync, manual edit) can make this negative; clamp it.
        return max(0.0, time.time() - self.started_at)


class Engine:
    def __init__(self, config: Config, on_change: Callable[[], None] | None = None,
                 log: Callable[[str], None] | None = None):
        self.config = config
        self.stats = Stats()
        self._on_change = on_change or (lambda: None)
        self._log = log or (lambda _msg: None)

        self._active = False
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._awake_asserted = False
        self._last_force_jiggle = 0.0
        #: Whether the previous tick was inside the work-hours window. None
        #: means "unknown", which makes the next tick apply the schedule as-is.
        self._was_inside: bool | None = None
        self._thread = threading.Thread(target=self._run, name="engine", daemon=True)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self.config.schedule_enabled:
            # The schedule decides the initial state: launching at 20:00 should
            # not start keeping alive just because start_active is on.
            inside = self._inside_now()
            self._was_inside = inside
            if inside:
                self.set_active(True)
            else:
                self.stats.off_hours = True
        elif self.config.start_active:
            self.set_active(True)
        self._thread.start()

    def shutdown(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3.0)

    @property
    def active(self) -> bool:
        return self._active

    def set_active(self, value: bool) -> None:
        with self._lock:
            if value == self._active:
                return
            self._active = value
            # Any explicit change -- user, hotkey or schedule -- ends "off hours"
            # and cancels a timed pause; whoever is pausing sets them again.
            self.stats.off_hours = False
            self.stats.resume_at = None
            if value:
                self.stats.started_at = time.time()
                self.stats.auto_stopped = False
                self.stats.blocked = False
                # Jiggle straight away so presence turns green now rather than
                # after a full cycle.
                self._last_force_jiggle = 0.0
            else:
                self.stats.started_at = 0.0
                self.stats.blocked = False
        self._log("keep-alive started" if value else "keep-alive paused")
        self._on_change()

    def toggle(self) -> bool:
        self.set_active(not self._active)
        return self._active

    def pause_until(self, when: datetime) -> None:
        """Pause now and switch back on by itself at ``when``.

        Calling it again while already paused just moves the resume time.
        """
        self.set_active(False)
        self.stats.resume_at = when
        self.stats.off_hours = False
        self.stats.auto_stopped = False
        self._log(f"paused until {when:%Y-%m-%d %H:%M}")
        self._on_change()

    def schedule_changed(self) -> None:
        """Settings of the schedule changed: re-apply it on the next tick.

        Turning the schedule on (or moving the window) means "follow it from
        now on", so the current state is brought in line straight away rather
        than waiting for the next boundary.
        """
        self._was_inside = None
        if not self.config.schedule_enabled:
            self.stats.off_hours = False

    # -- Three read-only views for the UI --------------------------------
    def state(self) -> str:
        """paused | locked | running"""
        if not self._active:
            return "paused"
        return "locked" if self.stats.blocked else "running"

    def state_text(self) -> str:
        state = self.state()
        if state == "paused" and self.stats.off_hours:
            return t("state_off_hours")
        if state == "paused" and self.stats.auto_stopped:
            return t("state_stopped")
        return t(f"state_{state}")

    def status_text(self) -> str:
        """The detail line on the status card."""
        if not self._active:
            if self.stats.resume_at is not None:
                return t("detail_resume_at", when=self.when_text(self.stats.resume_at))
            if self.stats.off_hours:
                when = self.next_start_text()
                return t("detail_next_start", when=when) if when else t("detail_start")
            return t("detail_limit") if self.stats.auto_stopped else t("detail_start")
        if self.stats.blocked:
            return t("detail_locked")
        parts = [t("detail_uptime", d=_fmt_duration(self.stats.active_seconds)),
                 t("detail_injections", n=self.stats.jiggles)]
        if self.config.mode == MODE_SMART:
            parts.append(t("detail_idle", n=f"{winapi.get_idle_seconds():.0f}"))
        return " · ".join(parts)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def _run(self) -> None:
        last_tick = time.monotonic()
        last_wall = time.time()
        try:
            while not self._stop.is_set():
                try:
                    self._tick()
                except Exception as exc:  # one bad tick must not kill keep-alive
                    self._log(f"tick failed: {exc!r}")

                self._stop.wait(TICK_SEC)

                now, now_wall = time.monotonic(), time.time()
                # Consult both clocks: on Windows monotonic can pause in some
                # sleep states, while the wall clock can jump on a time sync.
                # The larger gap is the honest estimate of the real stall.
                gap = max(now - last_tick, now_wall - last_wall)
                last_tick, last_wall = now, now_wall
                if gap >= STALL_THRESHOLD_SEC:
                    self._on_resume(gap)
        finally:
            winapi.release_awake()

    def _on_resume(self, gap: float) -> None:
        """The system was just frozen or asleep; bring everything back up.

        This is where Modern Standby machines fall over: after waking, the power
        request may no longer be in effect, and the ordinary next-tick logic
        does not necessarily restore it.
        """
        self.stats.stalls += 1
        self._log(f"system stall of ~{gap:.0f}s detected (sleep / modern standby), keep-alive re-armed")
        if self._active:
            winapi.keep_awake(display=self.config.keep_display_on)
            self._awake_asserted = True
            self._last_force_jiggle = 0.0  # make Always mode fire immediately
        self._on_change()

    def next_start_text(self) -> str:
        """When the next work-hours window opens, see when_text."""
        nxt = schedule.next_start(self.config.schedule_days, self.config.schedule_start,
                                  datetime.now())
        return self.when_text(nxt) if nxt else ""

    @staticmethod
    def when_text(when: datetime) -> str:
        """'13:30' if it is today, else with the weekday: 'Mo 13:30'."""
        hhmm = when.strftime("%H:%M")
        if when.date() == datetime.now().date():
            return hhmm
        return f"{t('days_short').split()[when.weekday()]} {hhmm}"

    def _check_resume(self) -> None:
        """End a timed pause once its time has come. Comparing against the
        clock (rather than counting down) also covers waking from sleep after
        the resume time has passed."""
        when = self.stats.resume_at
        if when is None or self._active or datetime.now() < when:
            return
        self._log("timed pause over, keep-alive on")
        self.set_active(True)
        self.stats.event = "resume"
        self._on_change()

    def _inside_now(self) -> bool:
        c = self.config
        return schedule.in_window(c.schedule_days, c.schedule_start, c.schedule_end,
                                  datetime.now())

    def _check_schedule(self) -> None:
        """Act on the *edges* of the work-hours window only.

        Reacting to edges rather than forcing the state every tick is what
        keeps manual control usable: pausing for lunch inside the window, or
        switching on for an evening call outside it, sticks until the next
        boundary instead of being undone a second later.
        """
        if not self.config.schedule_enabled:
            self._was_inside = None
            return
        inside = self._inside_now()
        if inside == self._was_inside:
            return
        self._was_inside = inside
        if inside and not self._active:
            self._log("work hours started, keep-alive on")
            self.set_active(True)
            self.stats.event = "on"
        elif not inside and self._active:
            self._log("work hours over, keep-alive paused")
            self.set_active(False)
            self.stats.off_hours = True
            self.stats.event = "off"
        elif not inside:
            # Already paused when work hours end -- e.g. still on a lunch-style
            # timed pause. The end of the day wins: drop the pending resume so
            # it does not switch back on in the evening.
            self.stats.off_hours = True
            self.stats.resume_at = None
        self._on_change()

    def _tick(self) -> None:
        self._check_schedule()
        self._check_resume()
        if not self._active:
            if self._awake_asserted:
                winapi.release_awake()
                self._awake_asserted = False
            return

        # Re-assert the power request every tick: it costs almost nothing and
        # covers the case where another program changed it.
        winapi.keep_awake(display=self.config.keep_display_on)
        self._awake_asserted = True

        if self._reached_auto_stop():
            self._log("run-time limit reached, stopping automatically")
            with self._lock:
                self._active = False
                self.stats.started_at = 0.0
                self.stats.auto_stopped = True
            winapi.release_awake()
            self._awake_asserted = False
            self._on_change()
            return

        # Injection cannot land while the session is locked or disconnected, so
        # stop and report it honestly instead of bumping the counter and showing
        # a fake "running" in the tray.
        blocked = winapi.is_session_locked()
        if blocked != self.stats.blocked:
            self.stats.blocked = blocked
            self._log("session locked, pausing injection" if blocked
                      else "session unlocked, resuming injection")
            self._on_change()
        if blocked:
            return

        if self._should_jiggle():
            self._jiggle()

    def _reached_auto_stop(self) -> bool:
        limit = self.config.auto_stop_hours
        return bool(limit) and self.stats.active_seconds >= limit * 3600

    def _should_jiggle(self) -> bool:
        if self.config.mode == MODE_SMART:
            # The events we inject refresh the idle timer too, so once the user
            # walks away this condition naturally becomes true once every
            # idle_threshold_sec. While they are using the PC the idle value
            # keeps resetting, so it never fires and never steals the cursor.
            return winapi.get_idle_seconds() >= self.config.idle_threshold_sec
        now = time.monotonic()
        return (now - self._last_force_jiggle) >= self.config.interval_sec

    def _jiggle(self) -> None:
        px = self.config.move_pixels
        ok = winapi.send_mouse_move(px, 0)
        time.sleep(JIGGLE_GAP_SEC)
        # Relative movement, so moving back lands the cursor exactly where it was
        ok = winapi.send_mouse_move(-px, 0) and ok

        self._last_force_jiggle = time.monotonic()
        if ok:
            self.stats.jiggles += 1
            self.stats.last_jiggle_at = time.time()
        else:
            # A refusal usually means the foreground window runs at a higher
            # integrity level (an elevated app, the secure desktop). That is
            # Windows working as designed, not a bug.
            self._log("SendInput refused by the system (foreground window may be elevated)")
        self._on_change()


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return t("dur_hm", h=h, m=m)
    if m:
        return t("dur_ms", m=m, s=s)
    return t("dur_s", s=s)
