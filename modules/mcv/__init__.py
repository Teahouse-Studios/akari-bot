from graia.application import MessageChain
from graia.application.message.elements.internal import Plain

from core.template import sendMessage
from .mcv import mcv, mcbv, mcdv


async def mcv_loader(kwargs: dict):
    run = await mcv()
    msgchain = MessageChain.create([Plain(run)])
    await sendMessage(kwargs, msgchain)


async def mcbv_loader(kwargs: dict):
    run = await mcbv()
    msgchain = MessageChain.create([Plain(run)])
    await sendMessage(kwargs, msgchain)


async def mcdv_loader(kwargs: dict):
    run = await mcdv()
    msgchain = MessageChain.create([Plain(run)])
    await sendMessage(kwargs, msgchain)


command = {'mcv': mcv_loader, 'mcbv': mcbv_loader, 'mcdv': mcdv_loader}
help = {'mcv': {'module': '查询当前Minecraft Java版启动器内最新版本。',
                'help': '~mcv - 查询当前Minecraft Java版启动器内最新版本。'},
        'mcbv': {'module': '查询当前Minecraft基岩版Jira上记录的最新版本。',
                 'help': '~mcbv - 查询当前Minecraft基岩版Jira上记录的最新版本。'},
        'mcdv': {'module': '查询当前Minecraft Dungeons Jira上记录的最新版本。',
                 'help': '~mcdv - 查询当前Minecraft Dungeons Jira上记录的最新版本。'}
        }
