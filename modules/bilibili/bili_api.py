from datetime import datetime

from core.builtins import Bot, Image, Plain, Url
from core.utils.cooldown import CoolDown
from core.utils.http import get_url

DESC_LENGTH = 100

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/53736 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.69"
}

async def get_video_info(msg: Bot.MessageSession, query, get_detail=False):
    if msg.target.target_from == 'TEST|Console':
        c = 0
    else:
        qc = CoolDown('call_bili_api', msg, all=True)
        c = qc.check(30)
    if c == 0:
        try:
            url = f'https://api.bilibili.com/x/web-interface/view/detail{query}'
            res = await get_url(url, 200, headers=headers, fmt='json')
            if res['code'] != 0:
                if res['code'] == -400:
                    await msg.finish(msg.locale.t("bilibili.message.invalid"))
                else:
                    await msg.finish(msg.locale.t('bilibili.message.not_found'))
        except ValueError as e:
            if str(e).startswith('412'):
                await msg.finish(msg.locale.t('bilibili.message.error.rejected'))

        view = res['data']['View']
        stat = view['stat']

        pic = view['pic']
        video_url = f"https://www.bilibili.com/video/{view['bvid']}"
        title = view['title']
        tname = view['tname']
        desc = view['desc']
        desc = (desc[:100] + '...') if len(desc) > 100 else desc
        time = msg.ts2strftime(view['ctime'], iso=True, timezone=False)

        if len(view['pages']) > 1:
            pages = msg.locale.t("message.brackets", msg=f"{len(view['pages'])}P")
        else:
            pages = ''

        stat_view = format_num(stat['view'])
        stat_danmaku = format_num(stat['danmaku'])
        stat_reply = format_num(stat['reply'])
        stat_favorite = format_num(stat['favorite'])
        stat_coin = format_num(stat['coin'])
        stat_share = format_num(stat['share'])
        stat_like = format_num(stat['like'])

        owner = view['owner']['name']
        fans = format_num(res['data']['Card']['card']['fans'])

        if not get_detail:
            output = msg.locale.t("bilibili.message", title=title, tname=tname, owner=owner, time=time)
        else:
            output = msg.locale.t("bilibili.message.detail", title=title, pages=pages, tname=tname,
                                              owner=owner, fans=fans, view=stat_view, danmaku=stat_danmaku,
                                              reply=stat_reply,
                                              like=stat_like, coin=stat_coin, favorite=stat_favorite, share=stat_share,
                                              desc=desc, time=time)
        if msg.target.target_from != 'TEST|Console':
            qc.reset()
        await msg.finish([Image(pic), Url(video_url), Plain(output)])
    else:
        return c


def format_num(number):
    if number >= 1000000000:
        return f'{number / 1000000000:.1f}G'
    elif number >= 1000000:
        return f'{number / 1000000:.1f}M'
    elif number >= 1000:
        return f'{number / 1000:.1f}k'
    else:
        return str(number)
