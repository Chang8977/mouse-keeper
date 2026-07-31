"""The tray app: glue holding the tray icon, the Fluent panel and the engine.

The threading model is simple: **all UI lives on the main thread.** tkinter's
mainloop runs there, tray messages are drained by pump() from an after loop, and
the engine runs on its own background thread but only mutates data and never
touches the UI -- when a refresh is needed it just sets a flag that the
main-thread timer picks up.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import tkinter as tk
from pathlib import Path

from . import APP_NAME, __version__, autostart, i18n, icon as icon_art, winapi, winui
from .config import MODE_FORCE, MODE_SMART, Config, config_path, log_path
from .engine import Engine
from .i18n import t
from .menu import FluentMenu, Item, separator
from .trayicon import TrayIcon

#: Cadences offered in the panel. Capped below 300 s, the point at which Teams
#: decides you are away.
CADENCE_CHOICES = (30, 45, 60, 90, 120, 180)
AUTO_STOP_CHOICES = (0.0, 2.0, 4.0, 8.0, 12.0)
#: How often tray messages are drained
PUMP_MS = 20
#: How often the icon / tooltip are refreshed
REFRESH_MS = 2000
#: How often the open panel refreshes. The detail line is only accurate to the
#: second, so 1 s is plenty, and Panel.refresh compares content first and skips
#: the repaint when nothing changed.
PANEL_REFRESH_MS = 1000


class App:
    def __init__(self) -> None:
        winui.enable_dpi_awareness()   # must happen before any window exists

        self.config = Config.load()
        i18n.set_language(self.config.language)
        self.engine = Engine(self.config, on_change=self._mark_dirty, log=self._log)

        self.root = tk.Tk()
        self.root.withdraw()

        self._icon_dir = Path(tempfile.gettempdir()) / "mouse-keeper-icons"
        self._icon_paths = icon_art.export_all(self._icon_dir)   # {variant: {state: path}}

        self.tray = TrayIcon(self._tooltip(), on_left=self._on_left_click,
                             on_right=self._on_right_click)
        self.menu = FluentMenu(self.root, self._build_items)

        self.hotkey: winapi.HotKeyListener | None = None
        self._icon_state: str | None = None
        #: Which artwork set (light/dark taskbar) is currently shown. Tracked
        #: separately from the panel's own theme -- Windows lets the taskbar
        #: and app themes differ, see winui.taskbar_uses_dark_theme.
        self._icon_variant: str | None = None
        self._auto_stop_notified = False
        self._dirty = True
        #: Whether the panel is showing the main page or the language page.
        #: There are too many languages to fit on one row, and bringing back the
        #: cascading submenus we just removed was not appealing, so this is a
        #: second page within the same panel.
        self._page = "main"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def run(self) -> None:
        self._icon_variant = self._current_icon_variant()
        self._icon_state = icon_art.PAUSED
        if not self.tray.show(self._icon_paths[self._icon_variant][self._icon_state]):
            raise OSError("failed to register the tray icon")
        self.engine.start()
        self._start_hotkey()
        self.root.after(PUMP_MS, self._pump_loop)
        self.root.after(REFRESH_MS, self._refresh_loop)
        self.root.after(PANEL_REFRESH_MS, self._panel_loop)
        self._log(f"{APP_NAME} {__version__} started, lang={i18n.current()}, "
                  f"config={config_path()}")
        self.root.mainloop()

    def _quit(self) -> None:
        if self.hotkey:
            self.hotkey.stop()
        self.engine.shutdown()
        self.config.save()
        self._log("exit")
        self.menu.close()
        self.tray.close()
        self.root.quit()

    def _start_hotkey(self) -> None:
        listener = winapi.HotKeyListener(self.config.hotkey, self._on_hotkey)
        listener.start()
        listener.wait_ready()
        if listener.error:
            self._log(f"hotkey unavailable: {listener.error}")
            self._notify(t("notify_hotkey_fail", err=listener.error))
            self.hotkey = None
        else:
            self.hotkey = listener

    def _on_hotkey(self) -> None:
        # The hotkey callback arrives on the hotkey thread and must not touch the
        # UI directly, so hand it back to the main thread.
        self.root.after(0, self._toggle_from_hotkey)

    def _toggle_from_hotkey(self) -> None:
        active = self.engine.toggle()
        self._notify(t("notify_started") if active else t("notify_paused"))

    # ------------------------------------------------------------------
    # Main-thread timers
    # ------------------------------------------------------------------
    def _pump_loop(self) -> None:
        self.tray.pump()
        self.root.after(PUMP_MS, self._pump_loop)

    def _refresh_loop(self) -> None:
        # Lock state and the taskbar theme are both polled rather than pushed,
        # so compare unconditionally here regardless of the dirty flag.
        if (self._dirty or self.engine.state() != self._icon_state
                or self._current_icon_variant() != self._icon_variant):
            self._dirty = False
            self._apply_state()
        self.root.after(REFRESH_MS, self._refresh_loop)

    def _panel_loop(self) -> None:
        self.menu.refresh()
        self.root.after(PANEL_REFRESH_MS, self._panel_loop)

    def _mark_dirty(self) -> None:
        """Called from the engine thread: sets a flag only. The actual UI update
        happens on the main thread."""
        self._dirty = True

    def _current_icon_variant(self) -> str:
        return icon_art.DARK if winui.taskbar_uses_dark_theme() else icon_art.LIGHT

    def _apply_state(self) -> None:
        state = self.engine.state()
        variant = self._current_icon_variant()
        if state != self._icon_state or variant != self._icon_variant:
            self._icon_state = state
            self._icon_variant = variant
            self.tray.set_icon(self._icon_paths[variant][state])
        self.tray.set_tooltip(self._tooltip())

        if self.engine.stats.auto_stopped and not self._auto_stop_notified:
            self._auto_stop_notified = True
            self._notify(t("notify_autostop", h=self.config.auto_stop_hours))
        elif self.engine.active:
            self._auto_stop_notified = False

    def _tooltip(self) -> str:
        mode = t("opt_smart") if self.config.mode == MODE_SMART else t("opt_force")
        return (f"{APP_NAME} · {self.engine.state_text()} · "
                f"{mode} · {self.config.cadence_sec}s")

    def _notify(self, message: str) -> None:
        try:
            self.tray.notify(message, APP_NAME)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Tray clicks
    # ------------------------------------------------------------------
    def _on_left_click(self) -> None:
        self.menu.close()
        self.engine.toggle()
        self._apply_state()

    def _on_right_click(self) -> None:
        # Always start on the main page rather than wherever we were left
        self._page = "main"
        # The message window has to come to the foreground first, otherwise the
        # popup cannot take focus and will never get the FocusOut that dismisses
        # it when you click elsewhere.
        self.tray.foreground()
        x, y = winapi.get_cursor_pos()
        self.menu.popup(x, y)

    # ------------------------------------------------------------------
    # Panel contents
    # ------------------------------------------------------------------
    def _build_items(self) -> list[Item]:
        if self._page == "language":
            return self._language_items()
        return [
            Item(kind="status",
                 text=self.engine.state_text,
                 detail=self.engine.status_text,
                 state=self.engine.state,
                 action=self._toggle_active),
            separator(),
            Item(kind="segmented", text=lambda: t("row_mode"),
                 options=[(t("opt_smart"), MODE_SMART), (t("opt_force"), MODE_FORCE)],
                 value=lambda: self.config.mode, on_select=self._set_mode),
            Item(kind="segmented", text=lambda: t("row_cadence"),
                 options=[(str(s), s) for s in CADENCE_CHOICES],
                 value=lambda: self.config.cadence_sec, on_select=self._set_cadence),
            Item(kind="segmented", text=lambda: t("row_autostop"),
                 options=[(t("opt_unlimited") if h == 0 else f"{h:g}", h)
                          for h in AUTO_STOP_CHOICES],
                 value=lambda: self.config.auto_stop_hours, on_select=self._set_auto_stop),
            Item(kind="toggle", text=lambda: t("row_keep_display"),
                 action=self._toggle_display,
                 checked=lambda: self.config.keep_display_on),
            separator(),
            Item(kind="toggle",
                 text=lambda: (t("row_autostart_stale") if autostart.is_stale()
                               else t("row_autostart")),
                 action=self._toggle_autostart, checked=autostart.is_enabled),
            Item(kind="toggle", text=lambda: t("row_logging"), action=self._toggle_log,
                 checked=lambda: self.config.log_enabled),
            Item(text=lambda: f"{t('row_language')} · {i18n.LANGUAGES[i18n.current()][0]}",
                 action=self._open_language_page),
            Item(text=lambda: t("row_open_config"), action=self._open_config_dir),
            separator(),
            Item(text=lambda: t("row_quit"), action=self._quit),
            Item(kind="label", text=f"{APP_NAME} {__version__}"),
        ]

    def _language_items(self) -> list[Item]:
        items: list[Item] = [
            Item(text=lambda: f"‹  {t('row_back')}", action=self._close_language_page),
            separator(),
        ]
        for code, name in i18n.available():
            items.append(Item(kind="toggle", text=name, action=self._set_language(code),
                              checked=self._language_is(code)))
        return items

    # -- Panel callbacks ------------------------------------------------
    # Segmented controls and toggles are "change it and keep looking" actions,
    # so they repaint the panel instead of dismissing it.
    def _toggle_active(self) -> None:
        self.engine.toggle()
        self._after_change()

    def _set_mode(self, mode: str) -> None:
        self.config.mode = mode
        self._after_change(save=True)

    def _set_cadence(self, seconds: int) -> None:
        self.config.set_cadence(seconds)
        self._after_change(save=True)

    def _set_auto_stop(self, hours: float) -> None:
        self.config.auto_stop_hours = hours
        self._after_change(save=True)

    def _toggle_display(self) -> None:
        self.config.keep_display_on = not self.config.keep_display_on
        self._after_change(save=True)

    def _toggle_log(self) -> None:
        self.config.log_enabled = not self.config.log_enabled
        self._after_change(save=True)

    def _after_change(self, save: bool = False) -> None:
        if save:
            self.config.save()
        self._apply_state()
        # The user just clicked, so this must show immediately and not go down
        # the "skip when unchanged" path.
        self.menu.refresh(force=True)

    def _open_language_page(self) -> None:
        self._page = "language"
        self._rebuild_panel()

    def _close_language_page(self) -> None:
        self._page = "main"
        self._rebuild_panel()

    def _language_is(self, code: str):
        return lambda: i18n.current() == code

    def _set_language(self, code: str):
        def handler():
            self.config.language = code
            self.config.save()
            i18n.set_language(code)
            # Fonts are chosen per language, so they must be rebuilt after a
            # switch or some scripts render as tofu boxes.
            self.menu.rebuild_fonts()
            self._page = "main"
            self._apply_state()
            self._rebuild_panel()
        return handler

    def _rebuild_panel(self) -> None:
        """Switching page or language replaces the whole item list, so a plain
        repaint is not enough."""
        if self.menu.panel is not None:
            self.menu.panel.items = self._build_items()
        self.menu.refresh(force=True)

    def _toggle_autostart(self) -> None:
        try:
            # If the path changed, is_enabled() is false and this rewrites the
            # entry with the correct one.
            enabled = autostart.toggle()
        except OSError as exc:
            self._log(f"failed to change startup entry: {exc}")
            self._notify(t("notify_autostart_fail", err=exc))
            return
        self._log(f"startup entry: {'on' if enabled else 'off'}")
        self._notify(t("notify_autostart_on") if enabled else t("notify_autostart_off"))

    def _open_config_dir(self) -> None:
        path = config_path().parent
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(path)  # noqa: S606 - opens Explorer on a path we built
        except Exception:
            subprocess.Popen(["explorer", str(path)])

    # ------------------------------------------------------------------
    def _log(self, message: str) -> None:
        if not self.config.log_enabled:
            return
        try:
            path = log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with path.open("a", encoding="utf-8") as fh:
                fh.write(f"[{stamp}] {message}\n")
        except OSError:
            pass
