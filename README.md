# Mouse Keeper

**English** · [简体中文](README.zh-CN.md) · [日本語](README.ja.md)

A tray-resident keep-alive utility for Windows. It makes Windows believe you are
still at the keyboard, so apps that derive presence from the system idle timer —
Microsoft Teams being the usual reason people want this — stay marked as
available.

- Pure `ctypes` calls into Win32. No pyautogui, no pynput, no automation stack.
- Two modes: **Smart** (only moves when you have actually stepped away) and
  **Always** (moves on a fixed interval).
- Blocks screen-off and sleep as well.
- **Stops by itself when the session is locked** and says so, then resumes on unlock.
- **Stall watchdog**: recovers on its own after sleep / Modern Standby.
- One-click start-with-Windows.
- **Hand-drawn Fluent panel**: rounded corners, drop shadow, hover highlight,
  follows the system light/dark theme, crisp on high-DPI displays.
- **10 UI languages**, auto-detected from your Windows display language.
- **Tray icon matches your taskbar theme**, switching automatically if it changes
  while running.

---

## Quick start

**Run from source**

```bash
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt && .venv\Scripts\pythonw main.py
```

**Build an exe (recommended)**

```bash
powershell -ExecutionPolicy Bypass -File build.ps1
```

The result is `dist\MouseKeeper\MouseKeeper.exe`. Double-click it and the icon
appears in the system tray. **Move the whole `MouseKeeper` folder if you relocate it.**

`--onedir` (a folder) is the deliberate default rather than `--onefile` (a single
exe). A onefile build unpacks itself into a temp directory on every launch, and
that behaviour alone trips antivirus heuristics — it is one of the main reasons
PyInstaller output gets flagged as a trojan. onedir never unpacks, so false
positives are far rarer, and it starts faster too. If you really want one file:

```bash
powershell -ExecutionPolicy Bypass -File build.ps1 -OneFile
```

**Run the self-check first** (strongly recommended — it verifies the whole
approach actually works on your machine):

```bash
.venv\Scripts\python main.py --check
```

You want to see `+ Self-check passed`. If it fails, `SendInput` is being blocked
by the system or by security software, and this tool cannot work on that machine.

The self-check always prints in English, whatever the UI language is set to —
it is a diagnostic meant for whoever is troubleshooting, and it stays ASCII-only
so that piping its output on a CJK codepage cannot raise `UnicodeEncodeError`.

---

## The two modes

| | Smart (default) | Always |
|---|---|---|
| Trigger | System has been idle for the threshold (60 s by default) | Every N seconds unconditionally (45 s by default) |
| While you are using the PC | **Completely silent** — never moves | Keeps moving, occasionally fighting you for the cursor |
| Use it when | Day-to-day. Pick this unless you have a reason not to | You want fully predictable behaviour, or Smart mode misbehaves |

Smart mode has a neat self-consistency to it: the events this tool injects also
reset the system idle timer, so once you walk away an injection happens exactly
every `idle_threshold_sec`. The moment you touch the mouse again the idle counter
keeps resetting on its own and the tool never fires.

---

## The panel

Right-click the tray icon:

```
┌──────────────────────────────────────┐
│  ●  Running                          │  ← click to toggle
│     Up 12m · 8 moves · idle 23s      │
├──────────────────────────────────────┤
│  Mode                [Smart] Always  │
│  Interval · sec  30 45 [60] 90 120   │
│  Auto-stop · hours  Off 2 4 [8] 12   │
│  ✓ Also block screen-off / sleep     │
├──────────────────────────────────────┤
│    Start with Windows                │
│    Write log file                    │
│    Language · English                │
│    Open config folder                │
├──────────────────────────────────────┤
│    Quit                              │
└──────────────────────────────────────┘
```

| Item | Notes |
|---|---|
| Status card | The badge shows running / paused / locked. Click to toggle; left-clicking the tray icon does the same |
| Mode | Smart / Always |
| Interval | 30 / 45 / 60 / 90 / 120 / 180 seconds |
| Auto-stop | Off / 2 / 4 / 8 / 12 hours, stops on its own and shows a notification |
| Also block screen-off / sleep | Maps to `SetThreadExecutionState` |
| Start with Windows | Writes `HKCU\...\Run`. No admin rights needed |
| Write log file | Goes to `%APPDATA%\MouseKeeper\mouse-keeper.log` |
| Language | Opens a second page listing all 10 languages |
| Open config folder | Opens `%APPDATA%\MouseKeeper\` |
| Quit | Saves the config and exits |

Changing a setting **does not close the panel**, so you can adjust several in a
row. Only the toggle and the action rows dismiss it.

The tray icon has three states: **green arrow** (running), **grey pause**
(paused), **amber padlock** (locked).

**Global hotkey `Ctrl+Alt+F12`** pauses / resumes at any time — handy when you
are about to hand over your screen. It can be changed in the config file, e.g.
`"ctrl+shift+f9"`.

---

## Languages

English, 简体中文, 繁體中文, 日本語, 한국어, Deutsch, Français, Español,
Português, Русский.

The default is `auto`, which reads your Windows display language via
`GetUserDefaultLocaleName` and falls back to English when there is no match.
Chinese resolves to Traditional for `-TW` / `-HK` / `-MO` / `Hant` tags and to
Simplified otherwise.

The font follows the language rather than being fixed globally — YaHei has no
Hangul and Segoe UI has no CJK ideographs, so a single font would render tofu
boxes in some languages.

Log-file messages are always written in English regardless of the UI language.
Logs exist for troubleshooting, and a single log shouldn't end up half in one
language and half in another because someone changed a setting midway.

---

## Configuration

`%APPDATA%\MouseKeeper\config.json`. Restart to apply manual edits; anything you
can reach from the panel is saved immediately.

| Key | Default | Notes |
|---|---|---|
| `mode` | `"smart"` | `smart` / `force` |
| `idle_threshold_sec` | `60` | Smart mode: idle seconds before moving (10–280) |
| `interval_sec` | `45` | Always mode: fixed interval (5–280) |
| `move_pixels` | `1` | Pixels per move (moved straight back afterwards) |
| `keep_display_on` | `true` | Also block screen-off |
| `auto_stop_hours` | `8.0` | Stop after this many hours, `0` = never |
| `language` | `"auto"` | `auto` or a language code such as `ja`, `de`, `zh-Hans` |
| `hotkey` | `"ctrl+alt+f12"` | Global pause / resume |
| `start_active` | `true` | Begin keeping alive right after launch |
| `log_enabled` | `false` | Write a log file |

The 280-second ceiling exists because Teams marks you away after roughly five
minutes (300 s) without input; a cadence has to be comfortably below that to mean
anything.

---

## How it works

```
every 1 s (dedicated thread, not a message timer)
  ├─ SetThreadExecutionState(ES_CONTINUOUS|ES_SYSTEM_REQUIRED[|ES_DISPLAY_REQUIRED])
  │     → blocks screen-off / sleep
  ├─ OpenInputDesktop() to detect a locked session → skip this tick if locked
  ├─ Smart mode: GetLastInputInfo() — has idle time reached the threshold?
  │   Always mode: has enough time passed since the last move?
  └─ if so → SendInput(MOUSEEVENTF_MOVE, +1px) → wait 50 ms → SendInput(-1px)
        → the system "last input time" is refreshed, cursor lands exactly where it was

At the end of every tick two clocks (monotonic and wall) are compared.
If the tick really took ≥10 s, the machine was frozen or asleep:
re-assert the power request and inject once immediately.
```

Three things that matter:

1. **It has to be `SendInput`, not `SetCursorPos`.** The latter only relocates
   the cursor; it produces no input event, so the timestamp behind
   `GetLastInputInfo` never updates and Teams goes away anyway. This is the most
   common way to get this wrong.
2. **Tools like PowerToys Awake are not enough.** They call
   `SetThreadExecutionState`, which blocks sleep but **generates no input**, so it
   does nothing for the away-status problem. Blocking sleep and blocking "away"
   are two separate jobs; this tool does both.
3. **Movement is relative and cancels out**, so the cursor sits exactly where it
   was before and nothing you are doing gets disturbed.

### Why the tray menu is hand-drawn

A Windows tray menu is normally a native HMENU (`CreatePopupMenu` +
`TrackPopupMenuEx`) drawn by the OS. The OS only accepts semantic flags —
checked, disabled, radio, separator — and offers **no owner-draw hook**, so
rounded corners, padding and hover highlights are all out of reach. `pystray`
takes exactly that route, which is why the whole tray layer here is custom:

- `trayicon.py` — `Shell_NotifyIcon` plus a hidden message window, handling the
  clicks itself
- `menu.py` — an `overrideredirect` tkinter window with the entire panel painted
  onto one Canvas; the window's rounded corners and shadow come from DWM
  (`DWMWA_WINDOW_CORNER_PREFERENCE`)

**There are no cascading submenus.** Mode, interval and auto-stop are inline
segmented controls. Cascading menus force the pointer to travel diagonally across
other rows to reach the submenu — a long path that is easy to slide off, the
classic Fitts / Steering Law pain point. Segmented controls collapse three clicks
into one.

**There is no progress animation either.** The status card carries a plain
coloured badge with a white glyph, the same visual language as the tray icon. A
moving progress ring has to be repainted every second, which is the single most
likely thing to develop rendering artefacts, and what it tells you (seconds until
the next move) is not worth that.

Panel refreshes follow the same principle: `Panel.refresh()` first compares a
signature of everything that should currently be on screen and skips entirely if
nothing changed. The only thing that actually moves is one line of detail text,
and once per second is plenty.

Threading model: **all UI lives on the main thread.** tkinter's mainloop runs
there, tray messages are drained by `pump()` from an `after` loop, and the
keep-alive engine runs on a background thread that only mutates data — when the
UI needs updating it sets a flag that the main-thread timer picks up.

Three traps worth knowing about, all documented in the code:

1. `SetProcessDpiAwarenessContext` takes a **pointer-sized** handle. Passing
   Python's `-4` makes ctypes marshal a 32-bit int, and on 64-bit the call fails
   **silently** — no error, no bad return value, but the process stays DPI-unaware
   and the whole UI gets bitmap-stretched into a blur on a high-DPI display.
2. `PeekMessage` inside `pump()` **must filter on our own hwnd**. Passing `None`
   drains the entire thread queue, tkinter's messages included, and
   `DispatchMessage` outside Tk's notifier does not produce the corresponding Tk
   events — mouse input just vanishes.
3. When the pointer crosses into a window, Tk delivers `<Enter>` but not
   `<Motion>`. Binding only `<Motion>` means a row the mouse is resting on never
   highlights until you jiggle the mouse.

Windows 10 has no `DWMWA_WINDOW_CORNER_PREFERENCE`, so the window falls back to
square corners. Nothing else is affected.

### Two icon sets, one per taskbar theme

The tray icon ships as two complete artwork sets in `assets/tray/light/` and
`assets/tray/dark/` (`running` / `paused` / `locked` each). They are not a
light-mode default with a dark-mode fallback — each is drawn for contrast
against one specific taskbar colour, and using the wrong one is what makes an
icon go illegible rather than just look slightly off: the `light` set's cursor
is near-black for a light taskbar, the `dark` set's is near-white for a dark
one.

Windows exposes the taskbar's theme independently of the per-app theme that
drives the panel's own colours — `SystemUsesLightTheme` versus
`AppsUseLightTheme`, both under
`HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize`. Settings >
Personalization > Colors > Custom lets a user set "Default Windows mode" (the
taskbar) and "Default app mode" (window chrome) differently, so the two are
read separately in `winui.py` and the tray icon reacts to its own signal rather
than piggybacking on the panel's.

### Why the main loop avoids message timers

`arkane-systems/mousejiggler#130` is an open report about a nasty case: on Modern
Standby (S0 low-power idle) laptops, once the display turns off the `WM_TIMER`
messages that `System.Windows.Forms.Timer` depends on stop being delivered and the
jiggler stalls **permanently** — the process is still alive but never moves again.

This project's main loop is a dedicated thread with `Event.wait()`, so it is
immune to that. The same report also notes that `SetThreadExecutionState()` may
never register as a system power request on such machines, which is why the stall
watchdog exists: the moment a tick takes far longer than it should, the power
request is re-asserted and an injection is fired immediately.

`powercfg /a` tells you whether your machine is a Modern Standby one.

---

## Known limits

- **Keep-alive cannot work while the session is locked.** After `Win+L` or on the
  secure desktop, the input desktop belongs to Winlogon and `SendInput` cannot
  land. The tool detects this, stops, shows "Locked" in the tray, and resumes on
  unlock — but **your status will drop during the lock**. There is no way around
  that.
- **Elevated windows block it.** When the foreground window runs as
  administrator, UIPI rejects `SendInput` from a non-elevated process (visible in
  the log). That is Windows working as designed, not a bug.
- **Disconnected RDP sessions** are suspended and get treated as "locked" too.
- **Antivirus false positives.** PyInstaller output being misread as a trojan is
  common and has nothing to do with what this project does. The default onedir
  build keeps the odds as low as possible, but corporate EDR judges things very
  differently from consumer antivirus. If it gets blocked, just run from source
  (`pythonw main.py`).
- Windows only — it is Win32 API from top to bottom.

---

## Please check this first

Teams presence is meant to reflect real availability. At some companies, using a
tool to keep it green is against IT or HR policy, and on a machine managed with
Intune or an EDR agent, input injection is typically auditable. This tool has no
features for evading corporate monitoring and will not gain any. Decide for
yourself whether it is appropriate where you work.

---

## Project layout

```
mouse-keeper/
├── main.py                  entry point + --check self-test
├── mouse_keeper/
│   ├── winapi.py            SendInput / GetLastInputInfo / power / lock probe / hotkey
│   ├── winui.py             DPI awareness / DWM corners / system theme / HICON
│   ├── trayicon.py          Shell_NotifyIcon tray icon + hidden message window
│   ├── menu.py              hand-drawn Fluent panel
│   ├── i18n.py              UI strings for 10 languages + language detection
│   ├── config.py            config read/write and validation
│   ├── engine.py            keep-alive loop (background thread + stall watchdog)
│   ├── autostart.py         start with Windows (HKCU Run entry)
│   ├── icon.py              tray icons loaded from assets/tray, exported as .ico
│   └── tray.py              the App that wires all of the above together
├── assets/tray/             tray-icon source PNGs (light/ and dark/ taskbar variants)
├── build.ps1                PyInstaller build script (-OneFile for a single file)
└── requirements.txt         Pillow only — the UI is tkinter, from the stdlib
```

> `build.ps1` is stored as **UTF-8 with BOM**. Windows PowerShell 5.1 decodes a
> BOM-less `.ps1` using the system ANSI codepage, which mangles non-ASCII text and
> can break quote pairing badly enough that the script fails to parse.
>
> Code comments and documentation are both in English.

---

## License

[MIT](LICENSE).
