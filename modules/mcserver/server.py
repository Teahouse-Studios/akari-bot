import re
import traceback

from mcstatus import JavaServer, BedrockServer

from core.builtins import Bot
from core.config import Config
from core.logger import Logger


async def query_java_server(
    msg: Bot.MessageSession, address: str, raw: bool = False, showplayer: bool = False
) -> str:
    match_object = re.match(r"(.*)[\s:](\d*)", address, re.M | re.I)
    serip = match_object.group(1) if match_object else address
    port = int(match_object.group(2)) if match_object else 25565
    servers = []

    try:
        server = JavaServer.lookup(f"{serip}:{port}")
        status = await server.async_status()
        Logger.debug(str(status))
        servers.append("[JE]")

        description = status.description
        if isinstance(description, str):
            servers.append(description)
        elif isinstance(description, dict):
            servers.append(description.get("text", ""))
            servers.append(
                "".join(extra.get("text", "") for extra in description.get("extra", []))
            )

        onlinesplayer = f"{msg.locale.t('server.message.player')}{status.players.online} / {status.players.max}"
        servers.append(onlinesplayer)

        if showplayer:
            playerlist = (
                [player.name for player in status.players.sample]
                if status.players.sample
                else []
            )
            players_text = (
                "\n".join(playerlist) if playerlist else msg.locale.t("message.none")
            )
            servers.append(
                msg.locale.t("server.message.player.current") + "\n" + players_text
            )

        if hasattr(status, "version") and hasattr(status.version, "name"):
            servers.append(msg.locale.t("server.message.version") + status.version.name)

        servers.append(f"{serip}:{port}")

    except Exception:
        if Config("debug", False):
            Logger.error(traceback.format_exc())
        return ""

    if raw:
        return "\n".join(servers)
    return re.sub(r"§\w", "", "\n".join(servers))


async def query_bedrock_server(msg, address, raw=False):
    match_object = re.match(r"(.*)[\s:](\d*)", address, re.M | re.I)
    serip = match_object.group(1) if match_object else address
    port = int(match_object.group(2)) if match_object else 19132
    servers = []

    try:
        server = BedrockServer.lookup(f"{serip}:{port}")
        status = await server.async_status()
        Logger.debug(str(status))
        servers.append("[BE]")
        servers.append(status.motd.raw)

        player_count = f"{msg.locale.t('server.message.player')}{status.players_online} / {status.players_max}"
        servers.append(player_count)

        if hasattr(status, "version") and hasattr(status.version, "name"):
            servers.append(msg.locale.t("server.message.version") + status.version.name)

        if hasattr(status, "gamemode"):
            game_mode = msg.locale.t("server.message.gamemode") + status.gamemode
            servers.append(game_mode)

        servers.append(f"{serip}:{port}")

    except Exception:
        if Config("debug", False):
            Logger.error(traceback.format_exc())
        return ""

    if raw:
        return "\n".join(servers)
    return re.sub(r"§\w", "", "\n".join(servers))
