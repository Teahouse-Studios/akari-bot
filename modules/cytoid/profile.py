import traceback

import ujson as json

from core.builtins import Bot, Embed, EmbedField, Image, Plain
from core.utils.http import get_url
from .dbutils import CytoidBindInfoManager


async def cytoid_profile(msg: Bot.MessageSession):
    pat = msg.parsed_msg.get('<UserID>', False)
    if pat:
        query_id = pat.lower()
    else:
        query_id = CytoidBindInfoManager(msg).get_bind_username()
        if not query_id:
            await msg.finish(msg.locale.t('cytoid.message.user_unbound', prefix=msg.prefixes[0]))
    profile_url = 'http://services.cytoid.io/profile/' + query_id
    try:
        profile = json.loads(await get_url(profile_url, 200))
    except ValueError as e:
        if str(e).startswith('404'):
            await msg.finish(msg.locale.t('cytoid.message.user_not_found'))
        else:
            traceback.print_exc()
    uid = profile['user']['uid']
    nick = profile['user']['name']
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
    if max:
        grade_t.append(f'MAX: {max}')
    sss = grade.get('SSS')
    if sss:
        grade_t.append(f'SSS: {sss}')
    ss = grade.get('SS')
    if ss:
        grade_t.append(f'SS: {ss}')
    s = grade.get('S')
    if s:
        grade_t.append(f'S: {s}')
    aa = grade.get('AA')
    if aa:
        grade_t.append(f'AA: {aa}')
    a = grade.get('A')
    if a:
        grade_t.append(f'A: {a}')
    b = grade.get('B')
    if b:
        grade_t.append(f'B: {b}')
    c = grade.get('C')
    if c:
        grade_t.append(f'C: {c}')
    d = grade.get('D')
    if d:
        grade_t.append(f'D: {d}')
    f = grade.get('F')
    if f:
        grade_t.append(f'F: {f}')

    res = [EmbedField('UID', uid)]
    if nick:
        res.append(EmbedField('Nickname', nick))
    res.extend([EmbedField('Basic Exp', basic_exp),
                EmbedField('Level Exp', level_exp),
                EmbedField('Total Exp', total_exp),
                EmbedField('Level', current_level),
                EmbedField('Next Level Exp', next_level_exp),
                EmbedField('Rating', rating),
                EmbedField('Grade', '|'.join(grade_t))])

    await msg.finish(Embed(title='Cytoid Profile',
                           url=profile_url,
                           image=Image(avatar),
                           fields=res))
