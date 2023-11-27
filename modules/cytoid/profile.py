import ujson as json

from core.builtins import Bot, Image, Plain
from core.utils.http import get_url
from .dbutils import CytoidBindInfoManager


async def cytoid_profile(msg: Bot.MessageSession):
    pat = msg.parsed_msg.get('<UserID>', False)
    if pat:
        query_id = pat.lower()
    else:
        query_id = CytoidBindInfoManager(msg).get_bind_username()
        if query_id is None:
            await msg.finish(msg.locale.t('cytoid.message.user_unbound', prefix=msg.prefixes[0]))
    profile_url = 'http://services.cytoid.io/profile/' + query_id
    try:
        profile = json.loads(await get_url(profile_url, status_code=200))
    except ValueError as e:
        if str(e).startswith('404'):
            await msg.finish(msg.locale.t('cytoid.message.user_not_found'))
        raise e
    uid = profile['user']['uid']
    nick = profile['user']['name']
    if nick is None:
        nick = False
    avatar = profile['user']['avatar']['large']
    basic_exp = profile['exp']['basicExp']
    level_exp = profile['exp']['levelExp']
    total_exp = profile['exp']['totalExp']
    current_level = profile['exp']['currentLevel']
    next_level_exp = profile['exp']['nextLevelExp']
    rating = profile['rating']
    grade: dict = profile['grade']
    grade_t = []
    max = grade.get('MAX')
    if max is not None:
        grade_t.append(f'MAX: {max}')
    sss = grade.get('SSS')
    if sss is not None:
        grade_t.append(f'SSS: {sss}')
    ss = grade.get('SS')
    if ss is not None:
        grade_t.append(f'SS: {ss}')
    s = grade.get('S')
    if s is not None:
        grade_t.append(f'S: {s}')
    aa = grade.get('AA')
    if aa is not None:
        grade_t.append(f'AA: {aa}')
    a = grade.get('A')
    if a is not None:
        grade_t.append(f'A: {a}')
    b = grade.get('B')
    if b is not None:
        grade_t.append(f'B: {b}')
    c = grade.get('C')
    if c is not None:
        grade_t.append(f'C: {c}')
    d = grade.get('D')
    if d is not None:
        grade_t.append(f'D: {d}')
    f = grade.get('F')
    if f is not None:
        grade_t.append(f'F: {f}')
    text = f'UID: {uid}\n' + \
           (f'Nickname: {nick}\n' if nick else '') + \
           f'BasicExp: {basic_exp}\n' + \
           f'LevelExp: {level_exp}\n' + \
           f'TotalExp: {total_exp}\n' + \
           f'CurrentLevel: {current_level}\n' + \
           f'NextLevelExp: {next_level_exp}\n' + \
           f'Rating: {rating}\n' + \
           f'Grade: {", ".join(grade_t)}'
    message_chain = [Image(path=avatar), Plain(text)]
    await msg.finish(message_chain)
