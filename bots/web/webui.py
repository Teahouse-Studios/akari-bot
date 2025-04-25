import os
import sys

import orjson as json
from flask import Flask, redirect, send_from_directory, url_for

sys.path.append(os.getcwd())

from bots.web.bot import API_PORT, WEBUI_HOST, WEBUI_PORT  # noqa: E402
from bots.web.utils import find_available_port  # noqa: E402
from core.config import Config  # noqa: E402
from core.constants.path import webui_path  # noqa: E402
from core.logger import Logger  # noqa: E402

default_locale = Config("default_locale", cfg_type=str)

if os.path.exists(os.path.join(webui_path, "index.html")):

    def generate_config(api_port):
        webui_config_path = os.path.join(webui_path, "config.json")
        if os.path.exists(webui_path):
            with open(webui_config_path, "wb") as f:
                f.write(json.dumps(
                    {"api_url": f"http://127.0.0.1:{api_port}",
                     "locale": default_locale}
                ))

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
        webui_port = find_available_port(WEBUI_PORT, host=WEBUI_HOST)
        if webui_port == 0:
            Logger.warning(f"API port is disabled, abort to run.")
            sys.exit(0)
        generate_config(API_PORT)
        Logger.info(f"Visit AkariBot WebUI: http://{WEBUI_HOST}:{webui_port}")
        app.run(host=WEBUI_HOST, port=webui_port, debug=False)
