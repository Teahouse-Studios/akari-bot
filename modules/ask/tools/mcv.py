import asyncio

from modules.mcv import mcv, mcbv, mcdv, mcev
from .utils import fake_msg, AkariTool


async def mcv_all():
    results = await asyncio.gather(
        mcv(fake_msg), mcbv(fake_msg), mcdv(fake_msg), mcev(fake_msg)
    )
    return '\n---'.join(results)


mcv_tool = AkariTool.from_function(
    name='minecraft_versions',
    func=mcv_all,
    description='A tool for checking current Minecraft: Java/Bedrock/Education Edition or Minecraft Dungeons versions. No input is required.'
)
