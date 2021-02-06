import aiohttp


async def get_url(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            text = await req.text()
            return text
