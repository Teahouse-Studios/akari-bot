import re
import traceback

from mcstatus import JavaServer, BedrockServer

from core.builtins import Bot
from core.config import Config
from core.logger import Logger


async def query_java_server(
    msg: Bot.MessageSession, address: str, raw: bool = False, showplayer: bool = False
) -> str:
    query_msg = []

    try:
        server = JavaServer.lookup(address)
        status = await server.async_status()
        Logger.debug(str(status))
        query_msg.append("[JE]")

        description = status.description
        if isinstance(description, str):
            query_msg.append(description)
        elif isinstance(description, dict):
            query_msg.append(description.get("text", ""))
            query_msg.append(
                "".join(extra.get("text", "") for extra in description.get("extra", []))
            )

        onlinesplayer = f"{msg.locale.t("server.message.player")}{status.players.online} / {status.players.max}"
        query_msg.append(onlinesplayer)

        if showplayer:
            playerlist = (
                [player.name for player in status.players.sample]
                if status.players.sample
                else []
            )
            players_text = (
                "\n".join(playerlist) if playerlist else msg.locale.t("message.none")
            )
            query_msg.append(
                msg.locale.t("server.message.player.current") + "\n" + players_text
            )

        if hasattr(status, "version") and hasattr(status.version, "name"):
            query_msg.append(msg.locale.t("server.message.version") + status.version.name)

    except Exception:
        if Config("debug", False):
            Logger.error(traceback.format_exc())
        return ""

    if raw:
        return "\n".join(query_msg)
    return re.sub(r"§\w", "", "\n".join(query_msg))


async def query_bedrock_server(msg, address, raw=False):
    query_msg = []

    try:
        server = BedrockServer.lookup(address)
        status = await server.async_status()
        Logger.debug(str(status))
        query_msg.append("[BE]")
        query_msg.append(status.motd.raw)

        player_count = f"{msg.locale.t("server.message.player")}{status.players_online} / {status.players_max}"
        query_msg.append(player_count)

        if hasattr(status, "version") and hasattr(status.version, "name"):
            query_msg.append(msg.locale.t("server.message.version") + status.version.name)

        if hasattr(status, "gamemode"):
            game_mode = msg.locale.t("server.message.gamemode") + status.gamemode
            query_msg.append(game_mode)

    except Exception:
        if Config("debug", False):
            Logger.error(traceback.format_exc())
        return ""

    if raw:
        return "\n".join(query_msg)
    return re.sub(r"§\w", "", "\n".join(query_msg))
