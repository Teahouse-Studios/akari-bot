import orjson

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from core.constants.path import assets_path


data_path = assets_path / "modules" / "threedsdb"


threedsdb = module("3dsdb", desc="{I18N:threedsdb.help.desc}", developers=["OasisAkari"])


@threedsdb.command("<keywords> {{I18N:threedsdb.help.command}}")
async def _(msg: Bot.MessageSession, keywords: str):
    message_str = []
    i = 0
    if keywords.isdigit():
        for file in data_path.glob("*.json"):
            load_json = orjson.loads(file.read_text(encoding="utf-8"))
            for item in load_json:
                if keywords in item.get("TitleID", ""):
                    if i < 10:
                        message_str += [f"{k}: {v}" for k, v in item.items()]
                        message_str.append("\n")
                        i += 1

    else:
        for file in data_path.glob("*.json"):
            load_json = orjson.loads(file.read_text(encoding="utf-8"))
            for item in load_json:
                if keywords.lower() in item.get("Name", "").lower():
                    if i < 10:
                        message_str += [f"{k}: {v}" for k, v in item.items()]
                        message_str.append("\n")
                        i += 1
    if message_str:
        await msg.finish([Plain("\n".join(message_str)), (I18NContext("threedsdb.message.limited_results") if i >= 10 else None)])
    else:
        await msg.finish(I18NContext("threedsdb.message.no_results"))
