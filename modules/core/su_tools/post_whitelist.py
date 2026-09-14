from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.database.models import TargetUnionInfo

post_whitelist = module(
    "post-whitelist", alias="post_whitelist", required_superuser=True, base=True, doc=True, available_for="QQ"
)


@post_whitelist.command("<group_id> {{I18N:core.help.post-whitelist}}")
async def _(msg: Bot.MessageSession, group_id: str):
    if not group_id.startswith("QQ|Group|"):
        await msg.finish(I18NContext("message.id.invalid.target", target="QQ|Group"))
    target_union_info = await TargetUnionInfo.get_by_target_id(group_id, create=False)
    if not target_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.target.confirm"), append_instruction=False):
            await msg.finish()
        target_union_info = await TargetUnionInfo.resolve_union(group_id)

    k = "in_post_whitelist"
    v = not target_union_info.target_data.get(k, False)
    await target_union_info.edit_target_data(k, v)
    await msg.finish(I18NContext("core.message.set.option.edit.success", k=k, v=v))
