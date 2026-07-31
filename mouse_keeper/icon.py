"""Tray icons, loaded from the hand-designed PNGs in ``assets/tray``.

There are two complete sets, one per taskbar theme:

  assets/tray/light/{running,paused,locked}.png   for a light taskbar
  assets/tray/dark/{running,paused,locked}.png    for a dark taskbar

Windows exposes the taskbar's own theme independently of the per-app theme
(``SystemUsesLightTheme`` vs ``AppsUseLightTheme`` -- see ``winui.py``), so the
"dark" set is not a fallback for missing assets, it is the one actually meant to
be shown when the taskbar itself is dark. Each source PNG only needs enough
internal contrast to work well against *one* taskbar colour; trying to make a
single set legible against both is why the un-badged parts of an icon (the
cursor here) tend to wash out on one theme or the other.

Each source is loaded once, resized down by Pillow into the sizes Windows
actually asks for, and saved as a multi-resolution .ico (the tray wants an
HICON, which can only be loaded from a file).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64)]

RUNNING, PAUSED, LOCKED = "running", "paused", "locked"
STATES = (RUNNING, PAUSED, LOCKED)

LIGHT, DARK = "light", "dark"
VARIANTS = (LIGHT, DARK)


def _asset_root() -> Path:
    """Where the source PNGs live, in source and in a frozen build alike.

    PyInstaller sets ``sys._MEIPASS`` in both onefile and onedir builds -- for
    onedir it points at the bundled resource directory (``_internal`` by
    default), so the same relative layout works whether or not the app has
    been packaged.
    """
    base = Path(getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent.parent)
    return base / "assets" / "tray"


def _source_path(variant: str, state: str) -> Path:
    return _asset_root() / variant / f"{state}.png"


def icon_for(state: str, variant: str = LIGHT) -> Image.Image:
    path = _source_path(variant, state if state in STATES else PAUSED)
    return Image.open(path).convert("RGBA")


def export_all(directory: str | Path) -> dict[str, dict[str, Path]]:
    """Write every (variant, state) combination as an .ico. Returns
    ``{variant: {state: path}}``."""
    directory = Path(directory)
    out: dict[str, dict[str, Path]] = {}
    for variant in VARIANTS:
        variant_dir = directory / variant
        variant_dir.mkdir(parents=True, exist_ok=True)
        out[variant] = {}
        for state in STATES:
            path = variant_dir / f"{state}.ico"
            icon_for(state, variant).save(path, format="ICO", sizes=ICO_SIZES)
            out[variant][state] = path
    return out


def export_ico(path: str | Path, variant: str = LIGHT) -> Path:
    """Export a single multi-size .ico for PyInstaller to use as the exe's own
    icon. Not theme-reactive -- it is baked into the binary at build time --
    so it defaults to the light-taskbar "running" artwork, matching how most
    Windows apps ship a single icon designed against a light background."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    icon_for(RUNNING, variant).save(path, format="ICO", sizes=ICO_SIZES)
    return path


if __name__ == "__main__":
    out = export_ico(Path(__file__).resolve().parent.parent / "assets" / "app.ico")
    print(f"icon written to {out}")
