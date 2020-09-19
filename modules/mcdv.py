import aiohttp

async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")

async def main():
    try:
        data = await get_data('https://bugs.mojang.com/rest/api/2/project/11901/versions', "json")
    except (ConnectionError, OSError):  # Probably...
        return "发生错误：土豆熟了"
    for v in data:
        if not v['archived']:
            return f'最新版：{v.get("name")} \n（数据来源于MoJira，可能会比官方发布要早一段时间。信息仅供参考。）'
    return "出了点问题，快去锤develop（"


command = 'mcdv'