from attrs import fields as attrs_fields

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.builtins.session.features import Features
from core.component import module

features = module("features", required_superuser=True, base=True, doc=True)


@features.command("{{I18N:core.help.features}}")
async def _(msg: Bot.MessageSession):
    fetched = await Bot.fetch_target(msg.session_info.target_id)

    yes = str(I18NContext("message.yes"))
    no = str(I18NContext("message.no"))
    unknown = str(I18NContext("message.unknown"))

    lines = []
    diff_count = 0
    for field in attrs_fields(Features):
        current = getattr(msg.session_info, field.name)
        if fetched:
            fetched_value = getattr(fetched, field.name)
            differs = current != fetched_value
            diff_count += differs
            fetched_text = yes if fetched_value else no
        else:
            differs = False
            fetched_text = unknown
        # 差异项加星号标出，聊天窗口里没有颜色可用
        lines.append(f"{'*' if differs else ''}{field.name}: {yes if current else no} / {fetched_text}")

    result = [I18NContext("core.message.features.prompt", target=msg.session_info.target_from, disable_joke=True)]
    if not fetched:
        result.append(I18NContext("core.message.features.fetch.failed"))
    # 特性名是代码标识符，不能参与文本替换
    result.append(Plain("\n".join(lines), disable_joke=True))
    if diff_count:
        result.append(I18NContext("core.message.features.diff", count=diff_count))

    await msg.finish(result)
