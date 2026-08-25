"""distract-yt — a distraction-free YouTube library.

Only content you explicitly allow ever appears. Videos play in an embedded
player with autoplay, related/clip suggestions and comments removed.
"""

from __future__ import annotations

import sys

from flask import Flask, send_from_directory

from . import api
from .config import STATIC_DIR


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None, template_folder=str(STATIC_DIR))
    app.config["JSON_SORT_KEYS"] = False
    app.url_map.strict_slashes = False

    app.register_blueprint(api.bp)

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/watch/<video_id>")
    def watch(video_id: str):
        # template_render never used on purpose; we pass the raw id to a page.
        return send_from_directory(STATIC_DIR, "watch.html")

    @app.get("/static/<path:filename>")
    def static_files(filename: str):
        return send_from_directory(STATIC_DIR, filename)

    @app.get("/service-worker.js")
    def service_worker():
        return send_from_directory(STATIC_DIR, "service-worker.js")

    return app


def main() -> None:
    from . import config
    from .db import init_db

    try:
        init_db()
    except Exception as err:
        print(
            "\n[distract-yt] Could not connect to PostgreSQL.\n"
            f"  -> {err}\n"
            "Make sure Postgres is running and DATABASE_URL in `.env` is correct.\n"
        )
        sys.exit(1)

    app = create_app()
    print(f"\n[distract-yt] Your distraction-free library: http://{config.HOST}:{config.PORT}\n")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
