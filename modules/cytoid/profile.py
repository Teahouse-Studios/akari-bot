import ujson as json

from core.builtins.message import MessageSession
from core.elements import Plain, Image
from core.utils import get_url
from .dbutils import CytoidBindInfoManager


async def cytoid_profile(msg: MessageSession):
    pat = msg.parsed_msg['<UserID>']
    if pat:
        query_id = pat
    else:
        query_id = CytoidBindInfoManager(msg).get_bind_username()
        if query_id is None:
            return await msg.sendMessage('未绑定用户，请使用~cytoid bind <friendcode>绑定一个用户。')
    profile_url = 'http://services.cytoid.io/profile/' + query_id
    profile = json.loads(await get_url(profile_url, status_code=200))
    if 'statusCode' in profile:
        if profile['statusCode'] == 404:
            await msg.sendMessage('发生错误：此用户不存在。')
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
    grade: dict = profile['grade']
    gradet = ''
    a = grade.get('A')
    if a is not None:
        gradet += f'A: {a},'
    b = grade.get('B')
    if b is not None:
        gradet += f' B: {b},'
    c = grade.get('C')
    if c is not None:
        gradet += f' C: {c},'
    d = grade.get('D')
    if d is not None:
        gradet += f' D: {d},'
    e = grade.get('E')
    if e is not None:
        gradet += f' E: {e},'
    s = grade.get('S')
    if s is not None:
        gradet += f' S: {s},'
    ss = grade.get('SS')
    if ss is not None:
        gradet += f' SS: {ss}'
    text = f'UID: {uid}\n' + \
           (f'Nickname: {nick}\n' if nick else '') + \
           f'BasicExp: {basicExp}\n' + \
           f'LevelExp: {levelExp}\n' + \
           f'TotalExp: {totalExp}\n' + \
           f'CurrentLevel: {currentLevel}\n' + \
           f'NextLevelExp: {nextLevelExp}\n' + \
           f'Rating: {rating}\n' + \
           f'Grade: {gradet}'
    msgchain = [Image(path=avatar), Plain(text)]
    await msg.finish(msgchain)
