"""Checking GitHub for a newer release.

This is the only network access the app makes, and it is deliberately modest:
one unauthenticated GET of the public "latest release" endpoint, shortly after
launch and then once a day. Nothing about the machine or its user is sent
beyond what any HTTPS request carries (the IP address, and a User-Agent naming
the app and its version). It never downloads or installs anything -- a newer
version just shows up as a row in the panel that opens the release page.

Turning off "Check for updates" in the panel (check_updates in the config)
stops it entirely.

Any failure -- offline, proxy, rate limit, GitHub down -- is silently ignored;
an update check is never worth an error dialog.
"""

from __future__ import annotations

import json
import re
import threading
import urllib.request
from typing import Callable

from . import APP_NAME, __version__

REPO = "Chang8977/mouse-keeper"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"

#: Wait a little after launch: at logon the network is often not up yet, and
#: the check has no reason to compete with everything else starting then.
FIRST_DELAY_SEC = 20
INTERVAL_SEC = 24 * 3600
TIMEOUT_SEC = 10


def parse_version(text: str) -> tuple[int, ...] | None:
    """'v1.2.0' / '1.2' -> (1, 2, 0) / (1, 2). None for anything else
    (including pre-release suffixes, which are never offered as updates)."""
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)", (text or "").strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def is_newer(candidate: str, current: str = __version__) -> bool:
    a, b = parse_version(candidate), parse_version(current)
    if a is None or b is None:
        return False
    # Pad so that 1.2 and 1.2.0 compare equal
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def fetch_latest() -> tuple[str, str] | None:
    """(version without the leading v, release page URL), or None on any failure."""
    req = urllib.request.Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{APP_NAME.replace(' ', '')}/{__version__}",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:  # noqa: S310 - fixed https URL
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    tag = str(data.get("tag_name") or "")
    if data.get("draft") or data.get("prerelease") or parse_version(tag) is None:
        return None
    url = str(data.get("html_url") or RELEASES_URL)
    if not url.startswith("https://github.com/"):
        url = RELEASES_URL
    return tag.lstrip("v"), url


class UpdateChecker(threading.Thread):
    """Background thread: check after FIRST_DELAY_SEC, then every INTERVAL_SEC.

    ``enabled`` is consulted before every check, so switching the option off
    takes effect without restarting the thread. ``poke()`` runs a check right
    away (used when the option is switched back on).
    """

    def __init__(self, enabled: Callable[[], bool],
                 on_found: Callable[[str, str], None],
                 log: Callable[[str], None] | None = None):
        super().__init__(name="update-check", daemon=True)
        self._enabled = enabled
        self._on_found = on_found
        self._log = log or (lambda _msg: None)
        self._wake = threading.Event()
        self._stop = threading.Event()

    def poke(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def run(self) -> None:
        delay = FIRST_DELAY_SEC
        while not self._stop.is_set():
            self._wake.wait(delay)
            self._wake.clear()
            if self._stop.is_set():
                return
            delay = INTERVAL_SEC
            if not self._enabled():
                continue
            result = fetch_latest()
            if result is None:
                self._log("update check: no answer (offline or blocked)")
                continue
            version, url = result
            if is_newer(version):
                self._log(f"update check: {version} available")
                self._on_found(version, url)
            else:
                self._log(f"update check: up to date ({__version__})")
