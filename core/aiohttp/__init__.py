import aiohttp


async def aiohttp_session(headers=None) -> aiohttp.ClientSession:
    async with aiohttp.ClientSession(headers=headers) as session:
        return session
