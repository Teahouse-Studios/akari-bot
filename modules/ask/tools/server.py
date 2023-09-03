import asyncio

from modules.server.server import server
from .utils import fake_msg, AkariTool


async def minecraft_server(address: str):
    results = await asyncio.gather(
        server(address, fake_msg, mode='j'), server(address, fake_msg, mode='b'),
    )
    return f'Java Edition result: {results[0]}\n\nBedrock Edition result: {results[1]}'


server_tool = AkariTool.from_function(
    func=minecraft_server,
    description='A tool for checking the status of Minecraft: Java/Bedrock Edition servers. Input should be a valid Minecraft server address.'
)
