import aiohttp

async def main(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            return await req.text()

command = {'get': 'get'}