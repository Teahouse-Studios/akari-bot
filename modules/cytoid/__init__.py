import re
from .profile import cytoid_profile
from .rating import get_rating
from core.template import sendMessage
from graia.application.message.elements.internal import Image
from graia.application import MessageChain


async def cytoid(kwargs: dict):
    command = kwargs['trigger_msg']
    command = re.sub('cytoid ', '', command)
    command_split = command.split(' ')
    if command_split[0] == 'profile':
        kwargs['trigger_msg'] = re.sub(r'^profile ', '', command)
        await cytoid_profile(kwargs)
    if command_split[0] in ['b30', 'r30']:
        uid = re.sub(r'^.*?30 ', '', command)
        img = await get_rating(uid, command_split[0])
        if 'path' in img:
            await sendMessage(kwargs, MessageChain.create([Image.fromLocalFile(img['path'])]))
        if 'text' in img:
            await sendMessage(kwargs, img['text'])


command = {'cytoid': cytoid}
help = {'cytoid': {'help': {'~cytoid profile <uid> - 获取一个用户的Cytoid账号信息。\n' + \
                            '~cytoid b30 <uid> - 获取一个用户的Best30信息。\n' + \
                            '~cytoid r30 <uid> - 获取一个用户的Recent30信息。'}}}
