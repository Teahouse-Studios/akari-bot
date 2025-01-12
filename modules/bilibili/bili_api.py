from core.builtins import Bot, Embed, EmbedField, ErrorMessage, Image, Plain, Url
from core.utils.http import get_url
from core.utils.web_render import webrender

DESC_LENGTH = 100


async def get_video_info(
    msg: Bot.MessageSession, query, get_detail=False, use_embed=False
):
    if msg.target.sender_from in ["Discord|Client"]:
        use_embed = True
    try:
        url = f"https://api.bilibili.com/x/web-interface/view/detail{query}"
        res = await get_url(
            webrender("source", url), 200, fmt="json", request_private_ip=True
        )
        if res["code"] != 0:
            if res["code"] == -400:
                await msg.finish(msg.locale.t("bilibili.message.invalid"))
            else:
                await msg.finish(msg.locale.t("bilibili.message.not_found"))
    except ValueError as e:
        if str(e).startswith("412"):
            await msg.finish(
                ErrorMessage(
                    "{bilibili.message.error.rejected}", locale=msg.locale.locale
                )
            )
        else:
            raise e

    view = res["data"]["View"]
    stat = view["stat"]

    video_url = f"https://www.bilibili.com/video/{view['bvid']}"
    pic = view["pic"]
    title = view["title"]
    tname = view["tname"]
    desc = view["desc"]
    desc = (desc[:100] + "...") if len(desc) > 100 else desc
    time = msg.ts2strftime(view["ctime"], iso=True, timezone=False)

    if len(view["pages"]) > 1:
        pages = msg.locale.t("message.brackets", msg=f"{len(view['pages'])}P")
    else:
        pages = ""

    stat_view = msg.locale.num(stat["view"], 1)
    stat_danmaku = msg.locale.num(stat["danmaku"], 1)
    stat_reply = msg.locale.num(stat["reply"], 1)
    stat_favorite = msg.locale.num(stat["favorite"], 1)
    stat_coin = msg.locale.num(stat["coin"], 1)
    stat_share = msg.locale.num(stat["share"], 1)
    stat_like = msg.locale.num(stat["like"], 1)

    owner = view["owner"]["name"]
    avatar = view["owner"]["face"]
    fans = msg.locale.num(res["data"]["Card"]["card"]["fans"], 1)

    if use_embed:
        await msg.send_message(
            Embed(
                title=f"{title}{pages}",
                description=desc,
                url=video_url,
                author=f"{owner}{msg.locale.t('message.brackets', msg=fans)}",
                footer="Bilibili",
                image=Image(pic),
                thumbnail=Image(avatar),
                fields=[
                    EmbedField(msg.locale.t("bilibili.message.embed.type"), tname),
                    EmbedField(
                        msg.locale.t("bilibili.message.embed.view"),
                        stat_view,
                        inline=True,
                    ),
                    EmbedField(
                        msg.locale.t("bilibili.message.embed.danmaku"),
                        stat_danmaku,
                        inline=True,
                    ),
                    EmbedField(
                        msg.locale.t("bilibili.message.embed.reply"),
                        stat_reply,
                        inline=True,
                    ),
                    EmbedField(
                        msg.locale.t("bilibili.message.embed.like"),
                        stat_like,
                        inline=True,
                    ),
                    EmbedField(
                        msg.locale.t("bilibili.message.embed.coin"),
                        stat_coin,
                        inline=True,
                    ),
                    EmbedField(
                        msg.locale.t("bilibili.message.embed.favorite"),
                        stat_favorite,
                        inline=True,
                    ),
                    EmbedField(
                        msg.locale.t("bilibili.message.embed.share"),
                        stat_share,
                        inline=True,
                    ),
                    EmbedField(msg.locale.t("bilibili.message.embed.time"), time),
                ],
            )
        )
    elif not get_detail:
        output = msg.locale.t(
            "bilibili.message", title=title, tname=tname, owner=owner, time=time
        )
        await msg.send_message([Image(pic), Url(video_url), Plain(output)])
    else:
        output = msg.locale.t(
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
        await msg.send_message([Image(pic), Url(video_url), Plain(output)])
