import re
import traceback

import aiohttp
import ujson as json

from core.builtins import ErrorMessage
from core.logger import Logger
from core.utils.http import get_url


async def server(msg, address, raw=False, showplayer=False, mode='JE'):
    match_object = re.match(r'(.*)[\s:](.*)', address, re.M | re.I)
    servers = []

    if match_object:
        serip = match_object.group(1)
        port1 = match_object.group(2)
        port2 = match_object.group(2)
    else:
        serip = address
        port1 = '25565'
        port2 = '19132'

    if mode == 'JE':
        try:
            url = f'http://motd.wd-api.com/v1/java?host={serip}&port={port1}'
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

            if 'players' in jejson:
                onlinesplayer = f"{msg.locale.t('server.message.player')}{str(jejson['players']['online'])} / {str(jejson['players']['max'])}"
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
                                msg.locale.t('server.message.player.current') + '\n' + msg.locale.t('none'))
            if 'version' in jejson:
                versions = msg.locale.t('server.message.version') + jejson['version']['name']
                servers.append(versions)
            servers.append(serip + ':' + port1)
        except Exception:
            traceback.print_exc()
            servers.append(Plain(ErrorMessage(msg.locale.t('server.message.error'))))
        if raw:
            return '\n'.join(servers)
        return re.sub(r'§\w', "", '\n'.join(servers))

    if mode == 'BE':
        try:
            url = f'http://motd.wd-api.com/v1/bedrock?host={serip}&port={port2}'
            bemotd = await get_url(url, 200, logging_err_resp=False)
            bejson = json.loads(bemotd)
        except ValueError:
            return ''
        try:
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
            servers.append(serip + ':' + port2)
        except Exception:
            traceback.print_exc()
            servers.append(Plain(ErrorMessage(msg.locale.t('server.message.error'))))
        if raw:
            return '\n'.join(servers)
        return re.sub(r'§\w', "", '\n'.join(servers))
