import re

import orjson as json
from mcstatus import BedrockServer, JavaServer

from core.builtins.message.internal import I18NContext
from core.logger import Logger
from core.utils.http import get_url


async def query_java_server(address: str, raw: bool = False, showplayer: bool = False) -> str:
    query_msg = []
    try:
        try:
            server = JavaServer.lookup(address)
            status: dict = (await server.async_status()).as_dict()["raw"]
        except TimeoutError:
            host = address.rsplit(":", 1)[0]
            port = (address.rsplit(":", 1) + [None])[1]
            url = f"http://motd.wd-api.com/v1/java?host={host}&port={port if port else 25565}"
            status: dict = json.loads(await get_url(url, 200, logging_err_resp=False))
        Logger.debug(str(status))
        query_msg.append("[JE]")

        description = status.get("description")
        if isinstance(description, str):
            query_msg.append(description)
        elif isinstance(description, dict):
            query_msg.append(description.get("text", ""))
            query_msg.append("".join(extra.get("text", "") for extra in description.get("extra", [])))

        onlinesplayer = (
            f"{str(I18NContext('server.message.player'))}{status['players']['online']} / {status['players']['max']}"
        )
        query_msg.append(onlinesplayer)

        if showplayer:
            playerlist = (
                [player["name"] for player in status["players"]["sample"]]
                if status.get("players", {}).get("sample")
                else []
            )
            players_text = "\n".join(playerlist) if playerlist else str(I18NContext("message.none"))
            query_msg.append(str(I18NContext("server.message.player.current")) + "\n" + players_text)

        if status.get("version") and status.get("version", {}).get("name"):
            query_msg.append(str(I18NContext("server.message.version")) + status["version"]["name"])

    except OSError:
        return ""
    except Exception:
        Logger.exception()
        return ""

    if raw:
        return "\n".join(query_msg)
    return re.sub(r"§\w", "", "\n".join(query_msg))


async def query_bedrock_server(address, raw=False) -> str:
    query_msg = []

    try:
        try:
            server = BedrockServer.lookup(address)
            status: dict = (await server.async_status()).as_dict()
            status["players_online"] = status["players"]["online"]
            status["players_max"] = status["players"]["max"]
            status["motd"] = status["motd"] + " - " + status.get("map_name", "")
        except TimeoutError:
            host = address.rsplit(":", 1)[0]
            port = (address.rsplit(":", 1) + [None])[1]
            url = f"http://motd.wd-api.com/v1/bedrock?host={host}&port={port if port else 19132}"
            raw_data = json.loads(await get_url(url, 200, logging_err_resp=False))
            status: dict = {
                key: value
                for key, value in zip(
                    ["edition", "motd_1", "_", "version", "players_online", "players_max", "__", "motd_2", "gamemode"],
                    raw_data["data"].split(";"),
                )
            }
            Logger.debug(str(status))
            status["motd"] = status["motd_1"] + " - " + status.get("motd_2", "")
        Logger.debug(str(status))
        query_msg.append("[BE]")
        query_msg.append(status["motd"])

        player_count = (
            f"{str(I18NContext('server.message.player'))}{status['players_online']} / {status['players_max']}"
        )
        query_msg.append(player_count)

        if status.get("version") and status.get("version", {}).get("name"):
            query_msg.append(str(I18NContext("server.message.version")) + status["version"]["name"])

        if status.get("gamemode"):
            game_mode = str(I18NContext("server.message.gamemode")) + status["gamemode"]
            query_msg.append(game_mode)

    except OSError:
        return ""
    except Exception:
        Logger.exception()
        return ""

    if raw:
        return "\n".join(query_msg)
    return re.sub(r"§\w", "", "\n".join(query_msg))
