import datetime
import traceback

import aiohttp

from core import dirty_check as dirty


def darkCheck(msg: str):
    blacklist = [
        'china-dictatorship'
        'cirosantilli',
        'gfwlist',
        'v2ray',
        'shadowsocks',
        'xi-yu-yan-kai-fa',
        'xi-winnie-rainbow-fart',
        'xi-speech-synthesizer',
        'dnmkrgi',
        'xi-speech-demo',
        'zhao',
        'programthink'
    ]
    for i in blacklist:
        if msg.find(i) > -1:
            return True
    return False


def time_diff(time: str):
    datetimed = datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%SZ').timestamp()
    now = datetime.datetime.now().timestamp()
    diff = now - datetimed

    diff = diff
    t = diff / 60 / 60 / 24
    dw = ' day(s)'
    if t < 1:
        t = diff / 60 / 60
        dw = ' hour(s)'
        if t < 1:
            t = diff / 60
            dw = ' minute(s)'
            if t < 1:
                t = diff
                dw = ' second(s)'
    diff = str(int(t)) + dw
    return diff


async def dirty_check(text, *whitelist_check):
    whitelist = [
        'Teahouse-Studios',
        'Dianliang233',
        'OasisAkari',
        'Lakejason0',
        'wyapx',
        'XxLittleCxX',
        'lakejason0'
    ]
    if whitelist_check in whitelist:
        return False
    check = await dirty.check(text)
    for x in check:
        if not x['status']:
            return True
    return False


async def query(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                if hasattr(req, fmt):
                    return await getattr(req, fmt)()
                else:
                    raise ValueError(f"NoSuchMethod: {fmt}")
        except Exception:
            traceback.print_exc()
            return False
