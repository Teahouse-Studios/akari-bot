# DON'T USE THEM - THEY ARE NOT FINISHED


import datetime
import os
import re
import traceback
import uuid
from urllib.parse import urlparse, parse_qs, urlencode, unquote

import aiohttp
import ujson as json

from config import Config
from core.logger import Logger

headers = {'Content-Type': 'application/json',
           'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate'
           }

signer = ...


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


async def fetch_device_token():
    data = {
        'RelyingParty': 'http://auth.xboxlive.com',
        'TokenType': 'JWT',
        'Properties': {
            'AuthMethod': 'ProofOfPossession',
            'Id': f'{{{uuid.uuid3(uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"), str(datetime.datetime.now().timestamp()))}}}',
            'DeviceType': 'Win32',
            'SerialNumber': f'{{{uuid.uuid3(uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"), str(datetime.datetime.now().timestamp()))}}}',
            'Version': '10.0.18363',
            'ProofKey': signer.proof_field}}
    h = {
        'Pragma': 'no-cache',
        'Accept': 'application/json',
        'Cache-Control': 'no-store, must-revalidate, no-cache',
        'Accept-Encoding': 'gzip, deflate, compress',
        'Accept-Language': 'en-US, en;q=0.9',
        'X-Xbl-Contract-Version': '2',
        'Signature': signer.sign('POST', urlparse('https://device.auth.xboxlive.com/device/authenticate').path,
                                 json.dumps(data).encode('utf-8')),
        'Content-Type': 'application/json;charset=utf-8',
    }
    async with aiohttp.ClientSession(headers=h, connector=aiohttp.TCPConnector(ssl=False)) as session:
        async with session.post(url="https://device.auth.xboxlive.com/device/authenticate",
                                data=json.dumps(data)) as resp:
            print(resp.status)
            return (await resp.json())['Token']


async def fetch_title_token(msaAuthtoken):
    deviceToken = await fetch_device_token()
    data = {
        'Properties': {
            'AuthMethod': 'RPS',
            'DeviceToken': deviceToken,
            'RpsTicket': 't=' + msaAuthtoken,
            'SiteName': 'user.auth.xboxlive.com',
            'ProofKey': signer.proof_field
        },
        'RelyingParty': 'http://auth.xboxlive.com',
        'TokenType': 'JWT'
    }
    sig = signer.sign('POST', urlparse('https://title.auth.xboxlive.com/title/authenticate').path,
                      json.dumps(data).encode('utf-8'))
    h = {
        'Pragma': 'no-cache',
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip, deflate, compress',
        'Accept-Language': 'en-US, en;q=0.9',
        'X-Xbl-Contract-Version': '2',
        'Signature': sig,
        'Content-Type': 'application/json;charset=utf-8',
    }

    async with aiohttp.ClientSession(headers=h, connector=aiohttp.TCPConnector(ssl=False)) as session:
        async with session.post(url="https://title.auth.xboxlive.com/title/authenticate",
                                data=json.dumps(data)) as resp:
            print(resp.status)
            print(await resp.text())


async def fetch_token(access_token, devicetoken):
    url = 'https://user.auth.xboxlive.com/user/authenticate'
    data = {
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT",
        "Properties": {
            "AuthMethod": "RPS",
            "SiteName": "user.auth.xboxlive.com",
            "RpsTicket": access_token,
        }}
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False),
                                     headers={'Content-Type': 'application/json'}) as session:
        async with session.post(url, data=json.dumps(data)) as resp:
            json_data = await resp.json()
            user_token = json_data['Token']
            auth_uhs = json_data['DisplayClaims']['xui'][0]['uhs']
            uhs = json_data['DisplayClaims']['xui'][0]['uhs']

    url = 'https://xsts.auth.xboxlive.com/xsts/authorize'
    data = {
        "RelyingParty": "rp://api.minecraftservices.com/",
        "TokenType": "JWT",
        "Properties": {
            "UserTokens": [user_token],
            "DeviceToken": devicetoken,
            "SandboxId": "RETAIL",
        }}
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False),
                                     headers={'Content-Type': 'application/json'}) as session:
        async with session.post(url, data=json.dumps(data)) as resp:
            json_data = await resp.json()
            auth_token = json_data['Token']
            return auth_token


async def login(email, password):
    # firstly we have to GET the login page and extract
    # certain data we need to include in our POST request.
    # sadly the data is locked away in some javascript code
    base_url = 'https://login.live.com/oauth20_authorize.srf?'

    # if the query string is percent-encoded the server
    # complains that client_id is missing
    qs = unquote(urlencode({
        'client_id': '0000000048093EE3',
        'redirect_uri': 'https://login.live.com/oauth20_desktop.srf',
        'response_type': 'token',
        'display': 'touch',
        'scope': 'service::user.auth.xboxlive.com::MBI_SSL',
        'locale': 'en',
    }))
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        async with session.get(base_url + qs) as resp:
            if resp.status != 200:
                raise Exception('Could not get login page')
            okcookies = resp.headers.getall('Set-Cookie')
            resp = await resp.read()

    # python 3.x will error if this string is not a
    # bytes-like object
    url_re = b'urlPost:\\\'([A-Za-z0-9:\\?_\\-\\.&/=]+)'
    ppft_re = b'sFTTag:\\\'.*value="(.*)"/>'

    login_post_url = re.search(url_re, resp).group(1).decode('utf-8')
    post_data = {
        'login': email,
        'passwd': password,
        'PPFT': re.search(ppft_re, resp).groups(1)[0].decode('utf-8'),
        'PPSX': 'Passpor',
        'SI': 'Sign in',
        'type': '11',
        'NewUser': '1',
        'LoginOptions': '1',
        'i3': '36728',
        'm1': '768',
        'm2': '1184',
        'm3': '0',
        'i12': '1',
        'i17': '0',
        'i18': '__Login_Host|1',
    }

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False),
                                     headers={'Connection': 'keep-alive', 'User-Agent': 'python-requests/2.26.0',
                                              'Content-Type': 'application/x-www-form-urlencoded',
                                              'Cookie': '; '.join(okcookies)}, ) as session:
        async with session.post(login_post_url, data=post_data) as resp:
            if resp.status != 200:
                raise Exception('Could not post login data')

            location = None
            for x in resp.history:
                get_location = x.headers.get('Location')
                if get_location is not None:
                    location = get_location

            if location is None:
                # we can only assume the login failed
                msg = 'Could not log in with supplied credentials'
                raise KeyError(msg)

            # the access token is included in fragment of the location header
            parsed = urlparse(location)
            fragment = parse_qs(parsed.fragment)
            access_token = fragment['access_token'][0]

            return access_token


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
