import os
import sys
import time
from flask import Flask, redirect, send_from_directory, url_for
from urllib.parse import urlparse

import orjson as json

sys.path.append(os.getcwd())

from bots.web.bot import API_PORT, WEBUI_PORT  # noqa: E402
from core.config import Config  # noqa: E402
from core.constants.path import webui_path  # noqa: E402
from core.logger import Logger  # noqa: E402


if os.path.exists(webui_path):

    def generate_config():
        webui_config_path = os.path.join(webui_path, "config.json")
        if os.path.exists(webui_config_path):
            with open(webui_config_path, "wb") as f:
                f.write(json.dumps({"api_url": f"http://127.0.0.1:{API_PORT}"}))

    app = Flask(__name__)

    @app.route("/")
    def redirect_to_webui():
        return redirect(url_for("index"))

    @app.route("/webui")
    @app.route("/webui/<path:path>")
    def index(path=None):
        return send_from_directory(webui_path, "index.html")

    @app.route("/<path:path>")
    def static_files(path):
        return send_from_directory(webui_path, path)

    @app.route("/api")
    @app.route("/api/<path:path>")
    def api_redirect(path=None):
        if path:
            from urllib.parse import urlparse
            parsed_path = urlparse(path)
            if not parsed_path.netloc and not parsed_path.scheme:
                return redirect(f"http://127.0.0.1:{API_PORT}/api/{path}")
            else:
                return redirect(f"http://127.0.0.1:{API_PORT}/api")
        else:
            return redirect(f"http://127.0.0.1:{API_PORT}/api")

if __name__ == "__main__" and Config("enable", True, table_name="bot_web") and os.path.exists(webui_path):
    generate_config()
    Logger.info(f"Visit AkariBot WebUI: http://127.0.0.1:{WEBUI_PORT}")
    app.run(port=WEBUI_PORT)
    Logger.error("WebUI crashed, is the port occupied?")
    Logger.error("Please check and restart WebUI manually.")
