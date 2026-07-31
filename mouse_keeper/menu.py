"""The hand-drawn Fluent-style popup panel.

The whole panel is painted onto a single Canvas rather than assembled from a
pile of Frames and Labels: hover highlights need rounded corners, which a Frame
cannot do, and the Canvas version is actually less code -- hit testing is just a
coordinate lookup in a list of rectangles.

The window's own rounded corners and shadow come from DWM
(DwmSetWindowAttribute), so on Win11 it matches the system menus. Win10 falls
back to square corners with no loss of function.

There are **no cascading submenus** here: mode / interval / auto-stop are all
inline segmented controls. Cascading menus force the pointer to travel
diagonally across other rows to reach the submenu -- a long path that is easy to
slide off, the classic Fitts / Steering Law pain point. Segmented controls
collapse three clicks into one.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass, field
from typing import Any, Callable

from . import i18n, winui

# ---- Palettes (follow the system light/dark theme) -----------------------
LIGHT = dict(bg="#f9f9f9", fg="#1b1b1b", dim="#767676", hover="#ededed",
             sep="#e5e5e5", accent="#005fb8", accent_hover="#1a6fc4",
             on_accent="#ffffff", chip="#ffffff", chip_hover="#e4e4e4",
             chip_edge="#d8d8d8", badge_run="#2ea043", badge_idle="#8a8a8a",
             badge_lock="#bf8700", badge_fg="#ffffff")
DARK = dict(bg="#2c2c2c", fg="#ffffff", dim="#a0a0a0", hover="#383838",
            sep="#3d3d3d", accent="#4cc2ff", accent_hover="#7ad3ff",
            on_accent="#00243d", chip="#3a3a3a", chip_hover="#525252",
            chip_edge="#4a4a4a", badge_run="#3fb950", badge_idle="#7d7d7d",
            badge_lock="#d29922", badge_fg="#ffffff")

# ---- Metrics (logical pixels at 96 DPI, scaled at runtime) ---------------
MIN_WIDTH = 250
#: Deliberately wider than CJK needs: German and Russian labels are noticeably
#: longer, and a 400 cap would ellipsise a whole batch of rows.
MAX_WIDTH = 460
ELLIPSIS = "…"
ROW_H = 26            # ordinary row
CARD_H = 50           # status card at the top
SEG_ROW_H = 30        # row carrying a segmented control
LABEL_ROW_H = 20
SEP_H = 7
PAD_Y = 4
PAD_X = 4
GUTTER = 26           # left gutter reserved for the check mark
RIGHT_PAD = 14
HOVER_RADIUS = 4
CHIP_RADIUS = 4
CHIP_PAD_X = 6
CHIP_GAP = 3
BADGE = 28            # diameter of the round badge on the status card

GLYPH_CHECK = "✓"
STATE_GLYPH = {"running": "▶", "paused": "⏸", "locked": "🔒"}
STATE_COLOR = {"running": "badge_run", "paused": "badge_idle", "locked": "badge_lock"}


@dataclass
class Item:
    """One entry in the panel.

    kind:
      status     the status card (badge + state + detail); clicking runs action
      action     an ordinary row
      toggle     an ordinary row plus a check mark
      segmented  a label on the left, a row of choices on the right
      label      dimmed explanatory text, not clickable
      separator  a divider line
    """
    kind: str = "action"
    text: str | Callable[[], str] = ""
    action: Callable[[], None] | None = None
    checked: Callable[[], bool] | None = None

    # status only
    state: Callable[[], str] | None = None
    detail: Callable[[], str] | None = None

    # segmented only
    options: list[tuple[str, Any]] = field(default_factory=list)
    value: Callable[[], Any] | None = None
    on_select: Callable[[Any], None] | None = None

    def resolve_text(self) -> str:
        return self.text() if callable(self.text) else self.text

    def is_checked(self) -> bool:
        return bool(self.checked and self.checked())


def separator() -> Item:
    return Item(kind="separator")


@dataclass
class _Zone:
    """A clickable / hoverable region.

    Full-width regions show their highlight using the panel's shared hover bar.
    The little blocks of a segmented control cannot: they have a fill of their
    own that completely hides the bar underneath. Those regions therefore record
    their own canvas item id plus two fill colours and simply recolour themselves.
    """
    x0: int
    y0: int
    x1: int
    y1: int
    action: Callable[[], None]
    radius: int
    shape_id: int | None = None
    fill: str = ""
    fill_hover: str = ""


class Panel:
    """The popup panel window."""

    def __init__(self, menu: "FluentMenu", items: list[Item]):
        self.menu = menu
        self.items = items
        self.zones: list[_Zone] = []
        self._hover: int | None = None
        self._signature: tuple | None = None

        c = menu.colors
        self.win = tk.Toplevel(menu.root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=c["bg"])

        self.canvas = tk.Canvas(self.win, bg=c["bg"], highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Motion>", self._on_motion)
        # When the pointer crosses into the window Tk delivers <Enter> but not
        # <Motion>. Binding Motion alone means a row the mouse is resting on
        # never highlights until you jiggle the mouse.
        self.canvas.bind("<Enter>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<Button-1>", self._on_click)

        self.build()

    # ------------------------------------------------------------------
    # Layout and painting
    # ------------------------------------------------------------------
    def _measure_width(self) -> int:
        m = self.menu
        width = m.px(MIN_WIDTH)
        for it in self.items:
            if it.kind == "separator":
                continue
            if it.kind == "segmented":
                need = (m.px(GUTTER) + m.font.measure(it.resolve_text()) + m.px(12)
                        + self._chips_width(it) + m.px(RIGHT_PAD))
            elif it.kind == "status":
                # Measure the real strings. A hard-coded sample would be wrong
                # the moment the language changes -- "Autom. gestoppt" is far
                # wider than a three-character CJK state.
                need = (m.px(GUTTER + BADGE) + m.px(10)
                        + max(m.font_strong.measure(it.resolve_text()),
                              m.font_dim.measure(it.detail() if it.detail else ""))
                        + m.px(RIGHT_PAD))
            else:
                f = m.font_dim if it.kind == "label" else m.font
                need = m.px(GUTTER) + f.measure(it.resolve_text()) + m.px(RIGHT_PAD)
            width = max(width, need)
        return min(m.px(MAX_WIDTH), width)

    def _fit(self, text: str, font, avail: int) -> str:
        """Truncate with an ellipsis when the text does not fit.

        Without this step an over-long label gets painted straight past the edge
        of the panel: the Canvas does not clip text, so it looks like the string
        has leaked outside the window frame.
        """
        if avail <= 0 or font.measure(text) <= avail:
            return text
        ell = font.measure(ELLIPSIS)
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if font.measure(text[:mid]) + ell <= avail:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo].rstrip() + ELLIPSIS

    def _chips_width(self, item: Item) -> int:
        m = self.menu
        total = 0
        for label, _v in item.options:
            total += m.font_small.measure(label) + 2 * m.px(CHIP_PAD_X) + m.px(CHIP_GAP)
        return total - m.px(CHIP_GAP) if total else 0

    def signature(self) -> tuple:
        """Everything dynamic that should currently be on screen.

        Used to decide whether a repaint is worth doing at all.
        """
        sig = []
        for it in self.items:
            sig.append((it.kind, it.resolve_text(),
                        it.detail() if it.detail else None,
                        it.state() if it.state else None,
                        it.value() if it.value else None,
                        it.is_checked()))
        return tuple(sig)

    def build(self) -> None:
        """Repaint everything from scratch."""
        m, c = self.menu, self.menu.colors
        self.canvas.delete("all")
        self.zones.clear()
        self._signature = self.signature()

        width = self._measure_width()
        y = m.px(PAD_Y)

        # The hover bar always sits at the bottom of the display list; from here
        # on only its coordinates change.
        self._hover_id = m.rounded_rect(self.canvas, 0, 0, 0, 0, m.px(HOVER_RADIUS),
                                        fill=c["hover"], outline="")
        self.canvas.itemconfigure(self._hover_id, state="hidden")

        for it in self.items:
            if it.kind == "separator":
                yy = y + m.px(SEP_H) // 2
                self.canvas.create_line(m.px(GUTTER // 2), yy,
                                        width - m.px(GUTTER // 2), yy, fill=c["sep"])
                y += m.px(SEP_H)
            elif it.kind == "status":
                y = self._draw_status(it, y, width)
            elif it.kind == "segmented":
                y = self._draw_segmented(it, y, width)
            elif it.kind == "label":
                h = m.px(LABEL_ROW_H)
                avail = width - m.px(GUTTER) - m.px(RIGHT_PAD)
                self.canvas.create_text(
                    m.px(GUTTER), y + h // 2,
                    text=self._fit(it.resolve_text(), m.font_dim, avail),
                    anchor="w", font=m.font_dim, fill=c["dim"])
                y += h
            else:
                y = self._draw_row(it, y, width)

        self.width = width
        self.height = y + m.px(PAD_Y)
        self.canvas.configure(width=self.width, height=self.height)
        self.win.geometry(f"{self.width}x{self.height}")

    def _draw_row(self, it: Item, y: int, width: int) -> int:
        m, c = self.menu, self.menu.colors
        h = m.px(ROW_H)
        mid = y + h // 2
        if it.is_checked():
            self.canvas.create_text(m.px(GUTTER) // 2, mid, text=GLYPH_CHECK,
                                    anchor="center", font=m.font_glyph, fill=c["accent"])
        avail = width - m.px(GUTTER) - m.px(RIGHT_PAD)
        self.canvas.create_text(m.px(GUTTER), mid,
                                text=self._fit(it.resolve_text(), m.font, avail),
                                anchor="w", font=m.font, fill=c["fg"])
        if it.action:
            self.zones.append(_Zone(m.px(PAD_X), y, width - m.px(PAD_X), y + h,
                                    it.action, m.px(HOVER_RADIUS)))
        return y + h

    def _draw_status(self, it: Item, y: int, width: int) -> int:
        m, c = self.menu, self.menu.colors
        h = m.px(CARD_H)
        state = it.state() if it.state else "paused"

        # A flat coloured badge with a white glyph, the same visual language as
        # the tray icon. Deliberately no progress ring: it would need repainting
        # every second, which is the single most likely thing to develop
        # rendering artefacts, and what it conveys (seconds until the next move)
        # is not worth that cost.
        box = m.px(BADGE)
        x0 = m.px(GUTTER) // 2 + m.px(2)
        y0 = y + (h - box) // 2
        self.canvas.create_oval(x0, y0, x0 + box, y0 + box,
                                fill=c[STATE_COLOR.get(state, "badge_idle")], outline="")
        cx, cy = x0 + box // 2, y0 + box // 2
        self.canvas.create_text(cx, cy, text=STATE_GLYPH.get(state, "▶"),
                                anchor="center", font=m.font_small, fill=c["badge_fg"])

        tx = x0 + box + m.px(10)
        avail = width - tx - m.px(RIGHT_PAD)
        self.canvas.create_text(tx, y + h // 2 - m.px(8),
                                text=self._fit(it.resolve_text(), m.font_strong, avail),
                                anchor="w", font=m.font_strong, fill=c["fg"])
        self.canvas.create_text(tx, y + h // 2 + m.px(9),
                                text=self._fit(it.detail() if it.detail else "",
                                               m.font_dim, avail),
                                anchor="w", font=m.font_dim, fill=c["dim"])
        if it.action:
            self.zones.append(_Zone(m.px(PAD_X), y, width - m.px(PAD_X), y + h,
                                    it.action, m.px(HOVER_RADIUS + 1)))
        return y + h

    def _draw_segmented(self, it: Item, y: int, width: int) -> int:
        m, c = self.menu, self.menu.colors
        h = m.px(SEG_ROW_H)
        mid = y + h // 2
        chips_w = self._chips_width(it)
        x = width - m.px(RIGHT_PAD) - chips_w
        # The label may only use the space left of the chips, otherwise a verbose
        # language runs straight over them.
        avail = x - m.px(GUTTER) - m.px(8)
        self.canvas.create_text(m.px(GUTTER), mid,
                                text=self._fit(it.resolve_text(), m.font, avail),
                                anchor="w", font=m.font, fill=c["fg"])

        current = it.value() if it.value else None
        chip_h = m.px(20)
        cy0, cy1 = mid - chip_h // 2, mid + chip_h // 2
        for label, value in it.options:
            w = m.font_small.measure(label) + 2 * m.px(CHIP_PAD_X)
            selected = value == current
            fill = c["accent"] if selected else c["chip"]
            fill_hover = c["accent_hover"] if selected else c["chip_hover"]
            shape = m.rounded_rect(self.canvas, x, cy0, x + w, cy1, m.px(CHIP_RADIUS),
                                   fill=fill, outline=("" if selected else c["chip_edge"]))
            self.canvas.create_text(x + w // 2, mid, text=label, anchor="center",
                                    font=m.font_small,
                                    fill=(c["on_accent"] if selected else c["fg"]))
            if it.on_select:
                self.zones.append(_Zone(x, cy0, x + w, cy1,
                                        _select(it.on_select, value), m.px(CHIP_RADIUS),
                                        shape_id=shape, fill=fill, fill_hover=fill_hover))
            x += w + m.px(CHIP_GAP)
        return y + h

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def _zone_at(self, x: int, y: int) -> int | None:
        for i, z in enumerate(self.zones):
            if z.x0 <= x < z.x1 and z.y0 <= y < z.y1:
                return i
        return None

    def _on_motion(self, event) -> None:
        self._apply_hover(self._zone_at(event.x, event.y))

    def _apply_hover(self, idx: int | None) -> None:
        if idx == self._hover:
            return
        # First restore the previously hovered region if it owns its fill
        if self._hover is not None and 0 <= self._hover < len(self.zones):
            prev = self.zones[self._hover]
            if prev.shape_id is not None:
                self.canvas.itemconfigure(prev.shape_id, fill=prev.fill)
        self._hover = idx

        if idx is None:
            self.canvas.itemconfigure(self._hover_id, state="hidden")
            return
        z = self.zones[idx]
        if z.shape_id is not None:
            self.canvas.itemconfigure(self._hover_id, state="hidden")
            self.canvas.itemconfigure(z.shape_id, fill=z.fill_hover)
            return
        self.menu.move_rounded_rect(self.canvas, self._hover_id,
                                    z.x0, z.y0 + self.menu.px(1),
                                    z.x1, z.y1 - self.menu.px(1), z.radius)
        self.canvas.itemconfigure(self._hover_id, state="normal")
        self.canvas.tag_lower(self._hover_id)

    def _on_leave(self, _event) -> None:
        self._apply_hover(None)

    def _on_click(self, event) -> None:
        idx = self._zone_at(event.x, event.y)
        if idx is None:
            return
        self.zones[idx].action()

    def sync_hover(self) -> None:
        """The panel may pop up directly under the cursor, in which case no mouse
        event ever arrives, so work the highlight out from the pointer position."""
        try:
            px, py = self.win.winfo_pointerxy()
        except tk.TclError:
            return
        x, y = px - self.win.winfo_rootx(), py - self.win.winfo_rooty()
        self._hover = -1  # force a recompute
        self._apply_hover(self._zone_at(x, y) if 0 <= x < self.width and 0 <= y < self.height
                          else None)

    # ------------------------------------------------------------------
    def show_at(self, x: int, y: int) -> None:
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        x = max(0, min(int(x), sw - self.width))
        y = max(0, min(int(y), sh - self.height))
        self.win.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.win.deiconify()
        self.win.lift()
        hwnd = winui.hwnd_of(self.win)
        winui.round_corners(hwnd)
        winui.use_dark_titlebar(hwnd, self.menu.dark)
        self.sync_hover()

    def refresh(self, force: bool = False) -> bool:
        """Repaint only when something actually changed.

        Redrawing the whole Canvas unconditionally once a second is both wasteful
        and the easiest way to make flicker visible. Returns whether a repaint
        happened.
        """
        if not force and self.signature() == self._signature:
            return False
        self.build()
        self.sync_hover()
        return True

    def destroy(self) -> None:
        self.win.destroy()


def _select(handler: Callable[[Any], None], value: Any) -> Callable[[], None]:
    """Closure factory -- a lambda written inline in the loop would capture the
    last value rather than the current one."""
    return lambda: handler(value)


class FluentMenu:
    def __init__(self, root: tk.Tk, items_provider: Callable[[], list[Item]],
                 on_closed: Callable[[], None] | None = None):
        self.root = root
        self.items_provider = items_provider
        self.on_closed = on_closed or (lambda: None)
        self.dark = winui.system_uses_dark_theme()
        self.colors = DARK if self.dark else LIGHT
        self.panel: Panel | None = None
        self._visible = False

        self.scale = winui.dpi_of(root) / 96.0
        self._families = set(tkfont.families())
        self.rebuild_fonts()

    def rebuild_fonts(self) -> None:
        """Pick the font for the current language.

        The font follows the language: YaHei has no Hangul and Segoe UI has no
        CJK ideographs, so one font for everything would render tofu boxes in
        some languages.
        """
        family = i18n.font_family()
        if family not in self._families:
            family = "Segoe UI" if "Segoe UI" in self._families else "Tahoma"
        self.font = tkfont.Font(family=family, size=-self.px(12))
        self.font_strong = tkfont.Font(family=family, size=-self.px(13), weight="bold")
        self.font_dim = tkfont.Font(family=family, size=-self.px(11))
        self.font_small = tkfont.Font(family=family, size=-self.px(11))
        self.font_glyph = tkfont.Font(family=family, size=-self.px(12))

    # ------------------------------------------------------------------
    def px(self, n: float) -> int:
        return max(1, round(n * self.scale))

    @property
    def visible(self) -> bool:
        return self._visible

    def popup(self, x: int, y: int) -> None:
        if self._visible:
            self.close()
            return
        dark = winui.system_uses_dark_theme()
        if dark != self.dark or self.panel is None:
            self.dark = dark
            self.colors = DARK if dark else LIGHT
            self._discard()
            self.panel = Panel(self, self.items_provider())
        else:
            self.panel.items = self.items_provider()
            self.panel.build()

        # Expand up and to the left, away from the tray
        self.panel.show_at(x - self.panel.width, y - self.panel.height)
        self._visible = True
        win = self.panel.win
        win.focus_force()
        win.bind("<FocusOut>", lambda _e: self.close())
        win.bind("<Escape>", lambda _e: self.close())

    def refresh(self, force: bool = False) -> None:
        """Called on a timer while the panel is open so the status text keeps up."""
        if self._visible and self.panel is not None:
            self.panel.refresh(force=force)

    def close(self) -> None:
        if not self._visible:
            return
        self._visible = False
        if self.panel is not None:
            self.panel.win.withdraw()
        self.on_closed()

    def _discard(self) -> None:
        if self.panel is not None:
            self.panel.destroy()
            self.panel = None

    # ------------------------------------------------------------------
    @staticmethod
    def _rounded_points(x0, y0, x1, y1, r):
        r = max(0, min(r, (x1 - x0) // 2, (y1 - y0) // 2))
        return [
            x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
            x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
            x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
        ]

    def rounded_rect(self, canvas: tk.Canvas, x0, y0, x1, y1, r, **kw):
        """Approximate a rounded rectangle with a smoothed polygon -- the Canvas
        has no native rounded-rectangle primitive."""
        return canvas.create_polygon(self._rounded_points(x0, y0, x1, y1, r),
                                     smooth=True, splinesteps=12, **kw)

    def move_rounded_rect(self, canvas: tk.Canvas, item_id, x0, y0, x1, y1, r) -> None:
        canvas.coords(item_id, *self._rounded_points(x0, y0, x1, y1, r))
