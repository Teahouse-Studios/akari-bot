import orjson as json

from core.builtins import Bot
from core.component import module
from core.dirty_check import check
from core.logger import Logger
from core.utils.http import post_url

n = module("nbnhhsh",
           desc="{nbnhhsh.help.desc}",
           doc=True,
           developers=["Dianliang233"],
           support_languages=["zh_cn"]
           )


@n.command("<term> {{nbnhhsh.help}}")
async def _(msg: Bot.MessageSession, term: str):
    res_nbnhhsh = await nbnhhsh(msg, term)
    chk = await check(res_nbnhhsh)
    res = f"{term.lower()}\n"
    for i in chk:
        res += i["content"]
    await msg.finish(res.strip())


async def nbnhhsh(msg: Bot.MessageSession, term: str):
    req = json.dumps({'text': term})
    data = await post_url('https://lab.magiconch.com/api/nbnhhsh/guess',
                          data=req,
                          headers={'Content-Type': 'application/json', 'Accept': '*/*',
                                   'Content-Length': str(len(req))},
                          fmt='json')
    Logger.debug(data)
    try:
        result = data[0]
    except IndexError:
        await msg.finish(msg.locale.t("nbnhhsh.message.not_found"))
    if 'trans' in result:
        trans = result['trans']
        return "、".join(trans)
    if 'inputting' in result:
        inputting = result['inputting']
        if inputting:
            return f'{msg.locale.t("nbnhhsh.message.guess", term=term)}{"、".join(inputting)}'
        await msg.finish(msg.locale.t("nbnhhsh.message.not_found"))
