"""External keep-alive pinger for the Render-hosted app.

The in-process keep-alive in ``distract_yt.keep_alive`` already keeps the web
service warm by pinging its own ``/health``. This standalone script is the
belt-and-suspenders version: run it from anywhere *outside* Render (a spare VPS,
a Raspberry Pi, a Glitch/UptimeRobot cron, or a GitHub Actions scheduled job) to
continuously wake/ping the deployed URL too.

Usage::

    python scripts/keep_alive_pinger.py --url https://your-app.onrender.com --interval 30

It just GETs ``<url>/health`` on a loop and never exits. Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import time
from urllib.error import URLError
from urllib.request import urlopen


def ping(url: str) -> bool:
    try:
        with urlopen(url, timeout=10):  # noqa: S310
            return True
    except URLError:
        return False
    except Exception:  # noqa: BLE001 - never crash the loop
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Deployed base URL, e.g. https://app.onrender.com")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between pings (default 30)")
    parser.add_argument("--health", default="/health", help="Path to the liveness endpoint (default /health)")
    args = parser.parse_args()

    target = args.url.rstrip("/") + args.health
    print(f"keep-alive pinger -> {target} every {args.interval}s (Ctrl+C to stop)")
    while True:
        start = time.monotonic()
        ok = ping(target)
        if not ok:
            print(f"[{time.strftime('%H:%M:%S')}] ping failed (will retry)")
        time.sleep(max(0, args.interval - int(time.monotonic() - start)))


if __name__ == "__main__":
    main()