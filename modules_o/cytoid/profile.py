import json

from graia.application import MessageChain, Group, Friend
from graia.application.message.elements.internal import Plain, Image, UploadMethods

from core.template import sendMessage
from core.utils import get_url


async def cytoid_profile(kwargs: dict):
    if Group in kwargs:
        mth = UploadMethods.Group
    if Friend in kwargs:
        mth = UploadMethods.Friend
    name = kwargs['trigger_msg']
    profile_url = 'http://services.cytoid.io/profile/' + name
    profile = json.loads(await get_url(profile_url))
    if 'statusCode' in profile:
        if profile['statusCode'] == 404:
            await sendMessage(kwargs, '发生错误：此用户不存在。')
            return
    uid = profile['user']['uid']
    nick = profile['user']['name']
    if nick is None:
        nick = False
    avatar = profile['user']['avatar']['large']
    basicExp = profile['exp']['basicExp']
    levelExp = profile['exp']['levelExp']
    totalExp = profile['exp']['totalExp']
    currentLevel = profile['exp']['currentLevel']
    nextLevelExp = profile['exp']['nextLevelExp']
    rating = profile['rating']
    grade = profile['grade']
    grade = f'A: {grade["A"]}, B: {grade["B"]}, C: {grade["C"]}, D: {grade["D"]}, F: {grade["F"]}, S: {grade["S"]}, SS: {grade["SS"]}'
    text = f'UID: {uid}\n' + \
           (f'Nickname: {nick}\n' if nick else '') + \
           f'BasicExp: {basicExp}\n' + \
           f'LevelExp: {levelExp}\n' + \
           f'TotalExp: {totalExp}\n' + \
           f'CurrentLevel: {currentLevel}\n' + \
           f'NextLevelExp: {nextLevelExp}\n' + \
           f'Rating: {rating}\n' + \
           f'Grade: {grade}'
    msg = MessageChain.create([Image.fromNetworkAddress(avatar, method=mth), Plain(text)])
    await sendMessage(kwargs, msg)
