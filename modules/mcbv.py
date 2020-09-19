import aiohttp
import re


async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")


async def main():
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
    prefix = " | "
    return f'Beta：{prefix.join(beta)}，Release：{prefix.join(release)}\n' \
           f'（数据来源于MoJira，可能会比官方发布要早一段时间。信息仅供参考。）'


command = 'mcbv'
