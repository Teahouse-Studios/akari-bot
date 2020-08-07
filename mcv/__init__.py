import re
import aiohttp


async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")


async def mcv():
    try:
        data = await get_data('http://launchermeta.mojang.com/mc/game/version_manifest.json', "json")
    except (ConnectionError, OSError):  # Probably...
        return "发生错误：土豆熟了"
    return f"最新版：{data['latest']['release']}，最新快照：{data['latest']['snapshot']}"


async def mvdv():
    try:
        data = await get_data('https://bugs.mojang.com/rest/api/2/project/11901/versions', "json")
    except (ConnectionError, OSError):  # Probably...
        return "发生错误：土豆熟了"
    for v in data:
        if not v['archived']:
            return f'最新版：{v.get("name")} \n（数据来源于MoJira，可能会比官方发布要早一段时间。信息仅供参考。）'
    return "出了点问题，快去锤develop（"


async def mcbv():
    try:
        data = await get_data('https://bugs.mojang.com/rest/api/2/project/10200/versions', "json")
    except (ConnectionError, OSError):  # Probably...
        return "发生错误：土豆熟了"
    beta = []
    release = []
    for v in data:
        if not v['archived']:
            match = re.match(r"(.*)Beta$", v["name"])
            if match:
                beta.append(match.group(1))
            else:
                release.append(v["name"])
    prefix = "| "
    return f'Beta：{prefix.join(beta)}，Release：{prefix.join(release)}\n' \
           f'（数据来源于MoJira，可能会比官方发布要早一段时间。信息仅供参考。）'
