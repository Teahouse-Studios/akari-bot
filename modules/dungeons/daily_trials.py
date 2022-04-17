import os
import traceback
import uuid

import ujson as json

import aiohttp

from config import Config
from core.logger import Logger

headers = {'Content-Type': 'application/json',
           'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate'
           }


async def get_token_from_playfab(xbox_token: str):
    data = {
        "XboxToken": xbox_token,
        "TitleId": "C839E",
        "CreateAccount": True,
        "InfoRequestParameters": {
            "GetUserAccountInfo": True,
            "GetPlayerProfile": True,
            "GetUserReadOnlyData": True
        }
    }
    headers['Content-Length'] = str(len(json.dumps(data)))
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(url='https://C839E.playfabapi.com/Client/LoginWithXbox',
                                data=json.dumps(data)) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return False


async def get_data_from_minecraft_dungeons_services(gametag: str, xbox_token: str):
    playfab_token = (await get_token_from_playfab(xbox_token))['data']['SessionTicket']
    if not playfab_token:
        raise Exception('Could not get playfab token')
    data = {
        "gamerTag": gametag,
        "identityToken": None,
        "loginType": "PLAYFAB",
        "namespace": "default",
        "platform": "onestore",
        "playfabToken": playfab_token,
        "xtoken": xbox_token}
    headers['Content-Length'] = str(len(json.dumps(data)))
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(url='https://api.minecraftservices.com/dungeons/login/',
                                data=json.dumps(data)) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return False


async def fetch_daily_trials(gametag: str, xbox_token: str):
    access_data = await get_data_from_minecraft_dungeons_services(gametag, xbox_token)
    if not access_data:
        raise Exception('Could not get dungeons access data')
    access_token = access_data['access_token']
    headers['Authorization'] = f'Bearer {access_token}'
    headers['Content-Length'] = '0'
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url='https://api.minecraftservices.com/trials/game/dungeons/') as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return False


web_render = Config('web_render')


async def json_render(json_data: dict):
    if not web_render:
        return False
    try:
        html = '<div class="json_output">' + json.dumps(json_data, indent=4) + '</div>'
        css = """
       <style>.json_output {
                white-space: pre;
                }</style>"""
        html = {'content': html + css, 'width': 1000}
        picname = os.path.abspath(f'./cache/{str(uuid.uuid4())}.jpg')
        if os.path.exists(picname):
            os.remove(picname)
        async with aiohttp.ClientSession() as session:
            async with session.post(web_render, headers={
                'Content-Type': 'application/json',
            }, data=json.dumps(html)) as resp:
                with open(picname, 'wb+') as jpg:
                    jpg.write(await resp.read())
        return picname
    except Exception:
        Logger.error(traceback.format_exc())
        return False
