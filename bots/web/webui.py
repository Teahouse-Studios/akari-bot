import os
import sys

import orjson as json
from flask import Flask, redirect, send_from_directory, url_for

sys.path.append(os.getcwd())

from bots.web.bot import API_PORT, WEBUI_HOST, WEBUI_PORT  # noqa: E402
from core.config import Config  # noqa: E402
from core.constants.path import webui_path  # noqa: E402
from core.logger import Logger  # noqa: E402


if os.path.exists(os.path.join(webui_path, "index.html")):

    def generate_config():
        webui_config_path = os.path.join(webui_path, "config.json")
        if os.path.exists(webui_path):
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

    if __name__ == "__main__" and Config("enable", True, table_name="bot_web") and \
            os.path.exists(os.path.join(webui_path, "index.html")):
        generate_config()
        Logger.info(f"Visit AkariBot WebUI: http://{WEBUI_HOST}:{WEBUI_PORT}")
        app.run(host=WEBUI_HOST, port=WEBUI_PORT, debug=False)
