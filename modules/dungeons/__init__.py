from datetime import datetime

from config import Config
from core.builtins import Bot, Image
from core.component import module
from .daily_trials import fetch_daily_trials, json_render

dun = module('dungeons_trials', alias=['dungeons', 'dungeon', 'dungeonstrials', 'dungeontrials', 'dungeon_trials'],
             desc='获取Minecraft Dungeons每日挑战信息。缓存12小时重置一次。')

records = {'ts': 0}


@dun.handle()
async def _(msg: Bot.MessageSession):
    await msg.sendMessage('请稍等...')
    if datetime.now().timestamp() - records['ts'] > 43200:
        records['data'] = await fetch_daily_trials(Config('xbox_gametag'), Config('xbox_token'))
        if not records['data']:
            await msg.sendMessage('获取失败。')
            return
        else:
            records['ts'] = int(datetime.now().timestamp())

    if 'data' in records:
        i = []
        for x in records['data']['trials']:
            i.append(Image(await json_render(x)))
        await msg.sendMessage(i)


@dun.handle('reset {强制重置缓存。}')
async def _(msg: Bot.MessageSession):
    records['ts'] = 0
    await msg.sendMessage('重置成功。')

    """qc = BotDBUtil.CoolDown(msg, 'dungeons_trials_reset')
    c = qc.check(86400)
    if c == 0:
        qc.reset()
    else:
        await msg.sendMessage(f'距离上次执行已过去{int(c)}秒，本命令的冷却时间为一天。')"""
