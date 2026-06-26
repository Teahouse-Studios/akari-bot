import orjson

from core.builtins.bot import Bot
from core.builtins.message.internal import Embed, EmbedField, Image, Url, I18NContext
from core.utils.func import truncate_text
from core.web_render import web_render, SourceOptions

DESC_LENGTH = 100


async def get_video_info(msg: Bot.MessageSession, query, get_detail=False, use_embed=False):
    if msg.session_info.sender_from in ["Discord|Client"]:
        use_embed = True
    try:
        url = f"https://api.bilibili.com/x/web-interface/view/detail{query}"
        res = await web_render.source(SourceOptions(url=url, raw_text=True, stealth=True))
        if res:
            load_json = orjson.loads(res)
            if load_json["code"] != 0:
                if load_json["code"] == -400:
                    return I18NContext("bilibili.message.invalid")
                return I18NContext("bilibili.message.not_found")
        else:
            return I18NContext("bilibili.message.failed")
    except orjson.JSONDecodeError:
        return I18NContext("bilibili.message.error.rejected")
    except Exception as e:
        raise e

    view = load_json.get("data", {}).get("View", {})
    stat = view.get("stat", {})

    video_url = f"https://www.bilibili.com/video/{view.get('bvid', '')}"
    pic = view.get("pic", "")
    title = view.get("title", "")
    tname = view.get("tname", "")
    desc = truncate_text(view.get("desc", ""), DESC_LENGTH)
    time = msg.format_time(view.get("pubdate", 0), iso=True, timezone=False)

    pages = view.get("pages", [])
    if len(pages) > 1:
        pages = str(I18NContext("message.brackets", msg=f"{len(pages)}P"))
    else:
        pages = ""

    stat_view = msg.format_num(stat.get("view", 0), 1)
    stat_danmaku = msg.format_num(stat.get("danmaku", 0), 1)
    stat_reply = msg.format_num(stat.get("reply", 0), 1)
    stat_favorite = msg.format_num(stat.get("favorite", 0), 1)
    stat_coin = msg.format_num(stat.get("coin", 0), 1)
    stat_share = msg.format_num(stat.get("share", 0), 1)
    stat_like = msg.format_num(stat.get("like", 0), 1)

    owner = view.get("owner", {}).get("name", "")
    avatar = view.get("owner", {}).get("face", "")
    card_data = load_json.get("data", {}).get("Card", {}).get("card", {})
    fans = msg.format_num(card_data.get("fans", 0), 1)

    if use_embed:
        return Embed(
            title=f"{title}{pages}",
            description=desc,
            url=video_url,
            author=f"{owner}{str(I18NContext('message.brackets', msg=fans))}",
            footer="Bilibili",
            image=Image(pic),
            thumbnail=Image(avatar),
            fields=[
                EmbedField("{I18N:bilibili.message.embed.type}", tname),
                EmbedField(
                    "{I18N:bilibili.message.embed.view}",
                    stat_view,
                    inline=True,
                ),
                EmbedField(
                    "{I18N:bilibili.message.embed.danmaku}",
                    stat_danmaku,
                    inline=True,
                ),
                EmbedField(
                    "{I18N:bilibili.message.embed.reply}",
                    stat_reply,
                    inline=True,
                ),
                EmbedField(
                    "{I18N:bilibili.message.embed.like}",
                    stat_like,
                    inline=True,
                ),
                EmbedField(
                    "{I18N:bilibili.message.embed.coin}",
                    stat_coin,
                    inline=True,
                ),
                EmbedField(
                    "{I18N:bilibili.message.embed.favorite}",
                    stat_favorite,
                    inline=True,
                ),
                EmbedField(
                    "{I18N:bilibili.message.embed.share}",
                    stat_share,
                    inline=True,
                ),
                EmbedField("{I18N:bilibili.message.embed.time}", time),
            ],
        )

    if not get_detail:
        output = I18NContext("bilibili.message", title=title, tname=tname, owner=owner, time=time)
    else:
        output = I18NContext(
            "bilibili.message.detail",
            title=title,
            pages=pages,
            tname=tname,
            owner=owner,
            fans=fans,
            view=stat_view,
            danmaku=stat_danmaku,
            reply=stat_reply,
            like=stat_like,
            coin=stat_coin,
            favorite=stat_favorite,
            share=stat_share,
            desc=desc,
            time=time,
        )
    return [Image(pic), Url(video_url, use_mm=False), output]
