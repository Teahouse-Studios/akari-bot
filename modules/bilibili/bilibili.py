from datetime import datetime

from core.builtins import Bot, Image, Plain
from core.utils.http import get_url


async def get_info(msg: Bot.MessageSession, url, get_detail):
    res = await get_url(url, 200, fmt='json')
    if res['code'] != 0:
        if res['code'] == -400:
            await msg.finish(msg.locale.t("bilibili.message.error.invalid"))
        else:
            await msg.finish(msg.locale.t('bilibili.message.not_found'))

    view = res['data']['View']
    stat = view['stat']

    pic = view['pic']
    video_url = f"https://www.bilibili.com/video/{view['bvid']}\n"
    title = view['title']
    tname = view['tname']

    timestamp = view['ctime']
    timeobject = datetime.fromtimestamp(timestamp)
    time = timeobject.strftime('%Y-%m-%d %H:%M:%S')

    if len(view['pages']) > 1:
        pages = f" ({len(view['pages'])}P)"
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
        output = video_url + msg.locale.t("bilibili.message", title=title, tname=tname, owner=owner, time=time)
    else:
        output = video_url + msg.locale.t("bilibili.message.detail", title=title, pages=pages, tname=tname,
                                          owner=owner, fans=fans, view=stat_view, danmaku=stat_danmaku,
                                          reply=stat_reply,
                                          like=stat_like, coin=stat_coin, favorite=stat_favorite, share=stat_share,
                                          time=time)

    await msg.finish([Image(pic), Plain(output)])


def format_num(number):
    if number >= 1000000000:
        return f'{number / 1000000000:.1f}G'
    elif number >= 1000000:
        return f'{number / 1000000:.1f}M'
    elif number >= 1000:
        return f'{number / 1000:.1f}k'
    else:
        return str(number)
