"""Keep the Render web service from spinning down during idle.

Render's free tier pauses a web service after ~15 minutes with no traffic and
wakes it again on the next request. That wake-up adds a cold-start delay, and if
the instance has been slept too long some services behave as "inactive".

A lightweight background thread that periodically hits the app's own (public)
health endpoint keeps the instance continuously "busy", so Render does not put
it to sleep. This runs *inside* the web process, so it needs no extra machine.

Usage
-----
The thread is started automatically by ``main()`` when ``KEEP_ALIVE=1`` is set
(see ``config.py`` and ``.env``). You can also start it yourself::

    from distract_yt.keep_alive import start_keep_alive
    start_keep_alive(interval_seconds=30, base_url="http://127.0.0.1:8000")
"""

from __future__ import annotations

import logging
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen

_log = logging.getLogger("distract_yt.keep_alive")

# Worker threads keep a process alive even when the main thread is idle, so the
# web service never ends up with nothing left to do.
_should_stop = threading.Event()


def _ping(endpoint: str) -> bool:
    """Hit one endpoint and return whether anything responded (any status)."""
    try:
        with urlopen(endpoint, timeout=5):  # noqa: S310  (endpoint is app-controlled)
            return True
    except URLError:
        return False
    except Exception:  # noqa: BLE001 - keep-alive must never crash the loop
        return False


def _loop(base_url: str, interval_seconds: float) -> None:
    health = base_url.rstrip("/") + "/health"
    while not _should_stop.is_set():
        started = time.monotonic()
        _ping(health)  # keep-alive requests never block on the response for long
        elapsed = time.monotonic() - started
        time.sleep(max(0.0, interval_seconds - elapsed))


def start_keep_alive(
    interval_seconds: float = 30.0,
    base_url: str = "http://127.0.0.1:8000",
    daemon: bool = True,
) -> threading.Thread:
    """Start the background keep-alive loop in a daemon thread."""
    thread = threading.Thread(
        target=_loop,
        args=(base_url, float(interval_seconds)),
        name="render-keep-alive",
        daemon=daemon,
    )
    thread.start()
    _log.info("keep-alive started: %s every %ss", base_url, interval_seconds)
    return thread


def stop_keep_alive() -> None:
    _should_stop.set()