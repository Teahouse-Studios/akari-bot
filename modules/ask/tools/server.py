import asyncio

from modules.mcserver.server import query_java_server, query_bedrock_server
from .utils import fake_msg, AkariTool


async def minecraft_server(address: str):
    results = await asyncio.gather(
        query_java_server(fake_msg, address),
        query_bedrock_server(fake_msg, address),
    )
    return f"Java Edition result: {results[0]}\n\nBedrock Edition result: {results[1]}"


server_tool = AkariTool.from_function(
    func=minecraft_server,
    description="A tool for checking the status of Minecraft: Java/Bedrock Edition servers. Input should be a valid Minecraft server address.",
)
