from langconv.converter import LanguageConverter
from langconv.language.zh import zh_tw

from core.builtins import Bot, Plain, Url
from core.component import module
from core.utils.http import get_url

msg_types = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"]

hitokoto = module(
    "hitokoto",
    developers=["bugungu", "DoroWolf"],
    desc="{hitokoto.help.desc}",
    doc=True,
    alias=["htkt", "yiyan"],
    support_languages=["zh_cn", "zh_tw"],
)


@hitokoto.command()
@hitokoto.command("[<msg_type>] {{hitokoto.help.type}}")
async def _(msg: Bot.MessageSession, msg_type: str = None):
    url = "https://v1.hitokoto.cn/"
    if msg_type:
        if msg_type in msg_types:
            url += "?c=" + msg_type
        else:
            await msg.finish(msg.locale.t("hitokoto.message.invalid"))

    data = await get_url(url, 200, fmt="json")
    if msg.locale.locale == "zh_tw":
        data = {
            k: (
                LanguageConverter.from_language(zh_tw).convert(v)
                if isinstance(v, str)
                else v
            )
            for k, v in data.items()
        }
    from_who = data["from_who"] or ""
    tp = msg.locale.t("hitokoto.message.type") + msg.locale.t(
        "hitokoto.message.type." + data["type"]
    )
    link = f"https://hitokoto.cn?id={data['id']}"
    await msg.finish(
        [Plain(f"{data['hitokoto']}\n——{from_who}「{data['from']}」\n{tp}"), Url(link)]
    )
