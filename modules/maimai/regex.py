import re

from core.builtins import Bot, Plain, Image as BImage
from core.component import module
from modules.maimai.libraries.maimaidx_api_data import get_alias
from modules.maimai.libraries.maimaidx_music import *

total_list = TotalList()

mai_regex = module('maimai_regex',
                     desc='{maimai.help.maimai_regex.desc}', recommend_modules=['maimai'],
                     alias='maimai_regex', developers=['DoroWolf'])


@mai_regex.handle(re.compile(r"(.+)是什么歌"), desc='{maimai.help.maimai_regex.song}')
async def _(msg: Bot.MessageSession):
    name = msg.matched_msg.groups()[0].strip()
    if name == "":
        return
    elif name.lower().startswith("id"):
        music = (await total_list.get()).by_id(name[2:])
        if music is None:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    else:
        sid_list = await get_alias(name, get_music=True)
        if len(sid_list) == 0:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
        elif len(sid_list) > 1:
            res = msg.locale.t("maimai.message.song.prompt") + "\n"
            for sid in sorted(sid_list, key=int):
                s = (await total_list.get()).by_id(sid)
                res += f"{s['id']} {s['title']}{' (DX)' if s['type'] == 'DX' else ''}\n"
            await msg.finish(res.strip())
        else:
            music = (await total_list.get()).by_id(str(sid_list[0]))

    file = f"https://www.diving-fish.com/covers/{get_cover_len5_id(music['id'])}.png"
    await msg.finish(
        [Plain(f"{music['id']} {music['title']} {' (DX)' if music['type'] == 'DX' else ''}\n"),
         BImage(f"{file}"),
         Plain(msg.locale.t("maimai.message.song",
                            artist=music['basic_info']['artist'], genre=music['basic_info']['genre'],
                            bpm=music['basic_info']['bpm'], version=music['basic_info']['from'],
                            level='/'.join((str(ds) for ds in music['ds']))))]) 