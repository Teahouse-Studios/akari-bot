import re

import aiohttp


async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")


async def mcv():
    try:
        data = await get_data('http://launchermeta.mojang.com/mc/game/version_manifest.json', "json")
        message1 = f"■■■■{data['latest']['release']}■■■■■■■{data['latest']['snapshot']}"
    except (ConnectionError, OSError):  # Probably...
        message1 = "■■■■■■■■■■■■■■■■■■"
    try:
        mojira = await get_data('https://bugs.mojang.com/rest/api/2/project/10400/versions', 'json')
        release = []
        prefix = ' | '
        for v in mojira:
            if not v['archived']:
                release.append(v['name'])
        message2 = prefix.join(release)
    except Exception:
        message2 = "■■■■■■■■■■■■■■■■■■"
    return f"""■■■■■■■■■■■■■■■■■■
{message1}
■■■■■■■■■■■■■■■■■■■■■■■■■■■
{message2}
■■■■■■■■■■■■■■■■■■■■■■■■■■■"""


async def mcbv():
    try:
        data = await get_data('https://bugs.mojang.com/rest/api/2/project/10200/versions', "json")
    except (ConnectionError, OSError):  # Probably...
        return "发生错误：土豆熟了"
    beta = []
    release = []
    for v in data:
        if not v['archived']:
            match = re.match(r"(.*Beta)$", v["name"])
            if match:
                beta.append(match.group(1))
            else:
                release.append(v["name"])
    prefix = "■■■■■■■■■"
    return f'■■■■■■■■■{prefix.join(beta)}■■■■■■■■■{prefix.join(release)}\n' \
           f'■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■'


async def mcdv():
    try:
        data = await get_data('https://bugs.mojang.com/rest/api/2/project/11901/versions', "json")
    except (ConnectionError, OSError):  # Probably...
        return "发生错误：土豆熟了"
    for v in data:
        if not v['archived']:
            return f'■■■■■■■■■■■■■■■■■■{v.get("name")} \n■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■'
    return "出了点问题，快去锤develop（"
