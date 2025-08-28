import os
import sys

import uvicorn

sys.path.append(os.getcwd())

from bots.web.api import *  # noqa: E402
from bots.web.info import *  # noqa: E402
from bots.web.client import web_host, avaliable_web_port  # noqa: E402
from bots.web.context import WebContextManager  # noqa: E402
from core.builtins.bot import Bot  # noqa: E402
from core.builtins.message.chain import MessageChain  # noqa: E402
from core.builtins.session.info import SessionInfo  # noqa: E402
from core.builtins.temp import Temp  # noqa: E402

Bot.register_bot(client_name=client_name)

ctx_id = Bot.register_context_manager(WebContextManager)


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    if __name__ != "bots.web.bot":
        await websocket.close(code=1008, reason="Bot server process is not running")
        return

    await websocket.accept()
    Temp.data["web_chat_websocket"] = websocket
    target_id = f"{target_prefix}|0"
    sender_id = f"{sender_prefix}|0"
    try:
        while True:
            rmessage = await websocket.receive_text()
            if rmessage:
                try:
                    message = json.loads(rmessage)
                except json.JSONDecodeError:
                    continue

                if message["action"] == "heartbeat" and message["message"] == "ping!":
                    Logger.debug("Heartbeat received.")
                    resp = {"action": "heartbeat", "message": "pong!"}
                    await websocket.send_text(json.dumps(resp).decode())
                    continue

                msg_chain = MessageChain.assign(message["message"][0]["content"])
                session = await SessionInfo.assign(target_id=target_id,
                                                   sender_id=sender_id,
                                                   sender_name="Console",
                                                   target_from=target_prefix,
                                                   sender_from=sender_prefix,
                                                   client_name=client_name,
                                                   message_id=message["id"],
                                                   messages=msg_chain,
                                                   ctx_slot=ctx_id
                                                   )

                await Bot.process_message(session, message)
    except WebSocketDisconnect:
        pass
    except Exception:
        Logger.exception()
        await websocket.close()
    finally:
        if "web_chat_websocket" in Temp.data:
            del Temp.data["web_chat_websocket"]


async def restart():
    await asyncio.sleep(1)
    os._exit(233)


@app.post("/api/restart")
async def restart_bot(request: Request):
    verify_jwt(request)

    if __name__ != "bots.web.bot":
        raise HTTPException(status_code=503, detail="Bot server process is not running")

    asyncio.create_task(restart())
    return Response(status_code=202)


if Config("enable", True, table_name="bot_web") or __name__ == "__main__":
    if avaliable_web_port == 0:
        Logger.error("API port is disabled.")
        sys.exit(0)
    if not enable_https:
        Logger.warning("HTTPS is disabled. HTTP mode is insecure and should only be used in trusted environments.")

    uvicorn.run(app, host=web_host, port=avaliable_web_port, log_level="info")
