import re

from graia.application import MessageChain
from graia.application.message.elements.internal import Image

from core.template import sendMessage
from database import BotDB as database
from .profile import cytoid_profile
from .rating import get_rating


async def cytoid(kwargs: dict):
    command = kwargs['trigger_msg']
    command = re.sub('cytoid ', '', command)
    command_split = command.split(' ')
    if command_split[0] == 'profile':
        kwargs['trigger_msg'] = re.sub(r'^profile ', '', command)
        await cytoid_profile(kwargs)
    if command_split[0] in ['b30', 'r30']:
        c = database.check_time(kwargs, 'cytoidrank', 300)
        if not c:
            database.write_time(kwargs, 'cytoidrank')
            uid = re.sub(r'^.*?30 ', '', command)
            img = await get_rating(uid, command_split[0])
            if 'path' in img:
                await sendMessage(kwargs, MessageChain.create([Image.fromLocalFile(img['path'])]))
            if 'text' in img:
                await sendMessage(kwargs, img['text'])
        else:
            await sendMessage(kwargs, f'距离上次执行已过去{int(-c)}秒，本命令的冷却时间为300秒。')


command = {'cytoid': cytoid}
help = {'cytoid': {'help': '~cytoid profile <uid> - 获取一个用户的Cytoid账号信息。\n' +
                           '~cytoid b30 <uid> - 获取一个用户的Best30信息。\n' +
                           '~cytoid r30 <uid> - 获取一个用户的Recent30信息。'}}
