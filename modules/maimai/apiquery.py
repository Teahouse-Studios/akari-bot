import re

from core.builtins import Bot, Plain, Image as BImage
from core.utils.image import msgchain2image
from .chunithm import chu
from .dbutils import DivingProberBindInfoManager
from .libraries.maimaidx_apidata import get_alias, get_info, search_by_alias
from .libraries.maimaidx_best50 import generate
from .libraries.maimaidx_music import TotalList
from .libraries.maimaidx_utils import *
from .maimai import mai
from .regex import mai_regex

mai_total_list = TotalList()


@chu.handle('bind <username> {{maimai.help.bind}}', exclude_from=['QQ', 'QQ|Group'])
async def _(msg: Bot.MessageSession, username: str):
    bind = DivingProberBindInfoManager(msg).set_bind_info(username=username)
    if bind:
        await msg.finish(msg.locale.t('maimai.message.bind.success') + username)


@chu.handle('unbind {{maimai.help.unbind}}', exclude_from=['QQ', 'QQ|Group'])
async def _(msg: Bot.MessageSession):
    unbind = DivingProberBindInfoManager(msg).remove_bind_info()
    if unbind:
        await msg.finish(msg.locale.t('maimai.message.unbind.success'))


@mai.handle('bind <username> {{maimai.help.bind}}', exclude_from=['QQ', 'QQ|Group'])
async def _(msg: Bot.MessageSession, username: str):
    bind = DivingProberBindInfoManager(msg).set_bind_info(username=username)
    if bind:
        await msg.finish(msg.locale.t('maimai.message.bind.success') + username)


@mai.handle('unbind {{maimai.help.unbind}}', exclude_from=['QQ', 'QQ|Group'])
async def _(msg: Bot.MessageSession):
    unbind = DivingProberBindInfoManager(msg).remove_bind_info()
    if unbind:
        await msg.finish(msg.locale.t('maimai.message.unbind.success'))


@mai.command('info <id_or_alias> [<username>] {{maimai.help.info}}')
async def _(msg: Bot.MessageSession, id_or_alias: str, username: str = None):
    await query_song_info(msg, id_or_alias, username)


@mai_regex.regex(re.compile(r"(.+)\s?有什[么麼]分\s?(.+)?"), desc='{maimai.help.maimai_regex.info}')
async def _(msg: Bot.MessageSession):
    songname = msg.matched_msg.groups()[0]
    username = msg.matched_msg.groups()[1]
    await query_song_info(msg, songname, username)


async def query_song_info(msg, query, username):
    if query[:2].lower() == "id":
        sid = query[2:]
    else:
        sid_list = await search_by_alias(msg, query)

        if len(sid_list) == 0:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
        elif len(sid_list) > 1:
            res = msg.locale.t("maimai.message.song.prompt") + "\n"
            for sid in sorted(sid_list, key=int):
                s = (await mai_total_list.get()).by_id(sid)
                res += f"{s['id']}\u200B. {s['title']}{' (DX)' if s['type'] == 'DX' else ''}\n"
            await msg.finish(res.strip())
        else:
            sid = str(sid_list[0])

    music = (await mai_total_list.get()).by_id(sid)
    if not music:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))

    if not username:
        if msg.target.sender_from == "QQ":
            payload = {'qq': msg.session.sender}
        else:
            username = DivingProberBindInfoManager(msg).get_bind_username()
            if not username:
                await msg.finish(msg.locale.t("maimai.message.user_unbound", prefix=msg.prefixes[0]))
            payload = {'username': username}
    else:
        payload = {'username': username}

    output = await get_player_score(msg, payload, sid)
    await msg.finish(await get_info(msg, music, Plain(output)))


@mai.command('plate <plate> [<username>] {{maimai.help.plate}}')
async def _(msg: Bot.MessageSession, plate: str, username: str = None):
    await query_plate(msg, plate, username)


@mai_regex.regex(re.compile(r"(.?)([極极将將舞神者]舞?)[进進]度\s?(.+)?"), desc='{maimai.help.maimai_regex.plate}')
async def _(msg: Bot.MessageSession):
    plate = msg.matched_msg.groups()[0] + msg.matched_msg.groups()[1]
    username = msg.matched_msg.groups()[2]
    await query_plate(msg, plate, username)


async def query_plate(msg, plate, username):
    if not username:
        if msg.target.sender_from == "QQ":
            payload = {'qq': msg.session.sender}
        else:
            username = DivingProberBindInfoManager(msg).get_bind_username()
            if not username:
                await msg.finish(msg.locale.t("maimai.message.user_unbound", prefix=msg.prefixes[0]))
            payload = {'username': username}
    else:
        payload = {'username': username}

    if plate in ['真将', '真將'] or (plate[1] == '者' and plate[0] != '霸'):
        await msg.finish(msg.locale.t('maimai.message.plate.plate_not_found'))

    output, get_img = await get_plate_process(msg, payload, plate)

    if get_img:
        img = await msgchain2image([Plain(output)], msg)
        if img:
            await msg.finish([BImage(img)])
        else:
            await msg.finish(output.strip())
    else:
        await msg.finish(output.strip())


@mai.command('process <level> <goal> [<username>] {{maimai.help.process}}')
async def _(msg: Bot.MessageSession, level: str, goal: str, username: str = None):
    goal_list = ["A", "AA", "AAA", "S", "S+", "SS", "SS+", "SSS", "SSS+", 
             "FC", "FC+", "AP", "AP+", "FS", "FS+", "FDX", "FDX+"]
    level_list = ['1', '2', '3', '4', '5', '6', '7', '7+', '8', '8+', '9', '9+',
              '10', '10+', '11', '11+', '12', '12+', '13', '13+', '14', '14+', '15']

    if not username:
        if msg.target.sender_from == "QQ":
            payload = {'qq': msg.session.sender}
        else:
            username = DivingProberBindInfoManager(msg).get_bind_username()
            if not username:
                await msg.finish(msg.locale.t("maimai.message.user_unbound", prefix=msg.prefixes[0]))
            payload = {'username': username}
    else:
        payload = {'username': username}

    if level in level_list:
        level_num = int(level.split('+')[0])
        if level_num < 8:
            await msg.finish(msg.locale.t("maimai.message.process.less_than_8"))
    else:
        await msg.finish(msg.locale.t("maimai.message.level_invalid"))

    if goal.upper() not in goal_list:
        await msg.finish(msg.locale.t("maimai.message.goal_invalid"))

    output, get_img = await get_level_process(msg, payload, level, goal)

    if get_img:
        img = await msgchain2image([Plain(output)])
        if img:
            await msg.finish([BImage(img)])
        else:
            await msg.finish(output.strip())
    else:
        await msg.finish(output.strip())


@mai.command('rank [<username>] {{maimai.help.rank}}')
async def _(msg: Bot.MessageSession, username: str = None):
    if not username:
        if msg.target.sender_from == "QQ":
            payload = {'qq': msg.session.sender}
        else:
            username = DivingProberBindInfoManager(msg).get_bind_username()
            if not username:
                await msg.finish(msg.locale.t("maimai.message.user_unbound", prefix=msg.prefixes[0]))
            payload = {'username': username}
    else:
        payload = {'username': username}

    await get_rank(msg, payload)


@mai.command('scorelist <level> <page> [<username>] {{maimai.help.scorelist}}')
async def _(msg: Bot.MessageSession, level: str, page: str, username: str = None):
    if not username:
        if msg.target.sender_from == "QQ":
            payload = {'qq': msg.session.sender}
        else:
            username = DivingProberBindInfoManager(msg).get_bind_username()
            if not username:
                await msg.finish(msg.locale.t("maimai.message.user_unbound", prefix=msg.prefixes[0]))
            payload = {'username': username}
    else:
        payload = {'username': username}

    output, get_img = await get_score_list(msg, payload, level, page)

    if get_img:
        img = await msgchain2image([Plain(output)])
        if img:
            await msg.finish([BImage(img)])
        else:
            await msg.finish(output.strip())
    else:
        await msg.finish([Plain(output.strip())])
