from core.builtins import Bot, Plain, Image as BImage
from core.utils.image import msgchain2image
from modules.maimai.libraries.apidata import get_info, search_by_alias
from modules.maimai.libraries.best50 import generate
from modules.maimai.libraries.music import TotalList
from modules.maimai.libraries.utils import get_level_process, get_plate_process, get_player_score, get_rank, \
    get_score_list

goal_list = ["A", "AA", "AAA", "S", "S+", "SS", "SS+", "SSS", "SSS+", 
             "FC", "FC+", "AP", "AP+", "FS", "FS+", "FDX", "FDX+"]
level_list = ['1', '2', '3', '4', '5', '6', '7', '7+', '8', '8+', '9', '9+',
              '10', '10+', '11', '11+', '12', '12+', '13', '13+', '14', '14+', '15']
total_list = TotalList()


@mai.command('b50 [<username>] {{maimai.help.b50}}')
async def _(msg: Bot.MessageSession, username: str = None):
    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender, 'b50': True}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username, 'b50': True}
    img = await generate(msg, payload)
    await msg.finish([BImage(img)])


@mai.command('info <id_or_alias> [<username>] {{maimai.help.info}}')
async def _(msg: Bot.MessageSession, id_or_alias: str, username: str = None):
    if id_or_alias[:2].lower() == "id":
        sid = id_or_alias[2:]
    else:
        sid_list = await search_by_alias(msg, id_or_alias)

        if len(sid_list) == 0:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
        elif len(sid_list) > 1:
            res = msg.locale.t("maimai.message.song.prompt") + "\n"
            for sid in sorted(sid_list, key=int):
                s = (await total_list.get()).by_id(sid)
                res += f"{s['id']}\u200B. {s['title']}{' (DX)' if s['type'] == 'DX' else ''}\n"
            await msg.finish(res.strip())
        else:
            sid = str(sid_list[0])

    music = (await total_list.get()).by_id(sid)
    if not music:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))

    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    output = await get_player_score(msg, payload, sid)

    await msg.finish(await get_info(msg, music, Plain(output)))


@mai.command('plate <plate> [<username>] {{maimai.help.plate}}')
async def _(msg: Bot.MessageSession, plate: str, username: str = None):
    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    if plate == '真将' or (plate[1] == '者' and plate[0] != '霸'):
        await msg.finish(msg.locale.t('maimai.message.plate.plate_not_found'))

    output, get_img = await get_plate_process(msg, payload, plate)

    if get_img:
        img = await msgchain2image([Plain(output)])
        await msg.finish([BImage(img)])
    else:
        await msg.finish(output.strip())


@mai.command('process <level> <goal> [<username>] {{maimai.help.process}}')
async def _(msg: Bot.MessageSession, level: str, goal: str, username: str = None):
    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
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
        await msg.finish([BImage(img)])
    else:
        await msg.finish(output.strip())


@mai.command('rank [<username>] {{maimai.help.rank}}')
async def _(msg: Bot.MessageSession, username: str = None):
    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    await get_rank(msg, payload)


@mai.command('scorelist <level> [<username>] {{maimai.help.scorelist}}')
async def _(msg: Bot.MessageSession, level: str, username: str = None):
    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    res, get_img = await get_score_list(msg, payload, level)

    if get_img:
        img = await msgchain2image([Plain(res)])
        await msg.finish([BImage(img)])
    else:
        await msg.finish([Plain(res.strip())])