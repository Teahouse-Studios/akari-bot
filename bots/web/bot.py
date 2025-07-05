import asyncio
import os
import sys

import uvicorn
import orjson as json
from fastapi import WebSocket, WebSocketDisconnect

sys.path.append(os.getcwd())

from bots.web.api import *  # noqa: E402
from bots.web.client import web_host, avaliable_web_port  # noqa: E402
from bots.web.info import *  # noqa: E402
from bots.web.message import MessageSession  # noqa: E402
from bots.web.utils import generate_webui_config  # noqa: E402
from core.builtins import Info, Temp  # noqa: E402
from core.config import Config  # noqa: E402
from core.parser.message import parser  # noqa: E402
from core.types import MsgInfo, Session  # noqa: E402


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    Temp.data["web_chat_websocket"] = websocket
    try:
        while True:
            rmessage = await websocket.receive_text()
            if rmessage:
                message = json.loads(rmessage)
                msg = MessageSession(
                    target=MsgInfo(
                        target_id=f"{target_prefix}|0",
                        sender_id=f"{sender_prefix}|0",
                        sender_name="Console",
                        target_from=target_prefix,
                        sender_from=sender_prefix,
                        client_name=client_name,
                        message_id=message["id"],
                    ),
                    session=Session(
                        message=message, target=f"{target_prefix}|0", sender=f"{sender_prefix}|0"
                    ))
                asyncio.create_task(parser(msg))
    except WebSocketDisconnect:
        pass
    except Exception:
        Logger.exception()
        await websocket.close()
    finally:
        if "web_chat_websocket" in Temp.data:
            del Temp.data["web_chat_websocket"]


if Config("enable", True, table_name="bot_web") or __name__ == "__main__":
    Info.client_name = client_name
    if "subprocess" in sys.argv:
        Info.subprocess = True
    if avaliable_web_port == 0:
        Logger.error("API port is disabled.")
        sys.exit(0)
    if not enable_https:
        Logger.warning("HTTPS is disabled. HTTP mode is insecure and should only be used in trusted environments.")

    if os.path.exists(webui_path):
        generate_webui_config(enable_https, default_locale)

    uvicorn.run(app, host=web_host, port=avaliable_web_port, log_level="info")
