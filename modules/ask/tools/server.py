import asyncio
from .utils import fake_msg, AkariTool
from modules.server.server import server

async def server_all(input: str):
    results = await asyncio.gather(
        server(input, fake_msg, mode='j'), server(input, fake_msg, mode='b'),
    )
    return f'Java Edition result: {results[0]}\n\nBedrock Edition result: {results[1]}'

server_tool = AkariTool(
    name = 'Minecraft Server',
    func=server_all,
    description='A tool for checking the status of Minecraft: Java/Bedrock Edition servers. Input should be a valid Minecraft server address.'
)
