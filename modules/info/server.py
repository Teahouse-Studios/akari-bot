import re
import traceback
import orjson as json

from mcstatus import JavaServer, BedrockServer

from core.builtins import Bot
from core.config import Config
from core.logger import Logger
from core.utils.http import get_url


async def query_java_server(
    msg: Bot.MessageSession, address: str, raw: bool = False, showplayer: bool = True
) -> str:
    match_object = re.match(r"(.*)[\s:](\d*)", address, re.M | re.I)
    serip = match_object.group(1) if match_object else address
    port = match_object.group(2) if match_object else 25565
    servers = []

    try:
        url = f'http://motd.wd-api.com/v1/java?host={serip}&port={port}'
        jemotd = await get_url(url, 200, logging_err_resp=False)
        jejson = json.loads(jemotd)
    except ValueError:
        return ''
    try:
        servers.append('[JE]')
        if 'description' in jejson:
            description = jejson['description']
            if 'text' in description and description['text'] != '':
                servers.append(str(description['text']))
            if 'extra' in description and description['extra'] != '':
                extra = description['extra']
                text = []
                for item in extra[:]:
                    if isinstance(item, dict):
                        text.append(str(item['text']))
                    else:
                        text.append(item)
                servers.append(''.join(text))
            else:
                servers.append(str(description))
        if 'players' in jejson:
            onlinesplayer = f"{msg.locale.t('server.message.player')}{str(
                jejson['players']['online'])} / {str(jejson['players']['max'])}"
            servers.append(onlinesplayer)
            if showplayer:
                playerlist = []
                if 'sample' in jejson['players']:
                    for x in jejson['players']['sample']:
                        playerlist.append(x['name'])
                    servers.append(
                        msg.locale.t('server.message.player.current') + '\n' + '\n'.join(playerlist))
                else:
                    if jejson['players']['online'] == 0:
                        servers.append(
                            msg.locale.t('server.message.player.current') + '\n' + msg.locale.t('message.none'))
        if 'version' in jejson:
            versions = msg.locale.t('server.message.version') + jejson['version']['name']
            servers.append(versions)
        servers.append(serip + ':' + port)
    except Exception:
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
    port = match_object.group(2) if match_object else 19132
    servers = []

    try:
        try:
            url = f'http://motd.wd-api.com/v1/bedrock?host={serip}&port={port}'
            bemotd = await get_url(url, 200, logging_err_resp=False)
            bejson = json.loads(bemotd)
        except ValueError:
            return ''
        unpack_data = bejson['data'].split(';')
        edition = unpack_data[0]
        motd_1 = unpack_data[1]
        version_name = unpack_data[3]
        player_count = unpack_data[4]
        max_players = unpack_data[5]
        motd_2 = unpack_data[7]
        game_mode = unpack_data[8]
        bemsg = '[BE]\n' + \
                motd_1 + ' - ' + motd_2 + \
                '\n' + msg.locale.t('server.message.player') + player_count + '/' + max_players + \
                '\n' + msg.locale.t('server.message.version') + edition + version_name + \
                '\n' + msg.locale.t('server.message.gamemode') + game_mode
        servers.append(bemsg)
        servers.append(serip + ':' + port)
    except Exception:
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
