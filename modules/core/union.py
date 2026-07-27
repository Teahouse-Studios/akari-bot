import string
from datetime import datetime, UTC

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from core.config import Config
from core.database.models import (
    UNION_SCOPE_SENDER,
    UNION_SCOPE_TARGET,
    SenderInfo,
    StoredData,
    TargetInfo,
    collect_union_conflicts,
    get_table_name,
    get_union_module_name,
)
from core.utils.container import ExpiringTempDict
from core.utils.random import Random

BIND_CODE_EXPIRED = 300  # 绑定码有效期（秒）
BIND_CODE_LENGTH = 6
BIND_CODE_ALPHABET = string.ascii_uppercase + string.digits

# 绑定码仅保存在 server 进程内存中，重启即失效。
_sender_bind_codes = ExpiringTempDict(exp=BIND_CODE_EXPIRED)
_target_bind_codes = ExpiringTempDict(exp=BIND_CODE_EXPIRED)


def _generate_code(store: ExpiringTempDict, union_id: str, holder_id: str) -> str:
    """
    为发起方生成一枚绑定码，同一 union 同时只保留最新的一枚。

    :param store: 绑定码存储。
    :param union_id: 发起方所属的 union ID。
    :param holder_id: 发起方的平台 ID，用于向对方展示绑定来源。
    :return: 绑定码。
    """
    for old_code in [code for code, entry in store.items() if entry.get("union_id") == union_id]:
        store.pop(old_code)

    code = "".join(Random.choices(BIND_CODE_ALPHABET, k=BIND_CODE_LENGTH))
    while code in store:
        code = "".join(Random.choices(BIND_CODE_ALPHABET, k=BIND_CODE_LENGTH))

    store[code] = ExpiringTempDict(
        exp=BIND_CODE_EXPIRED,
        data={"union_id": union_id, "holder_id": holder_id},
        root=False,
    )
    return code


def _take_code(store: ExpiringTempDict, code: str) -> dict | None:
    """
    取出并消费一枚绑定码。

    :param store: 绑定码存储。
    :param code: 用户输入的绑定码。
    :return: 绑定码对应的信息，无效或已过期时为 None。
    """
    code = code.strip().upper()
    entry = store.get(code)
    if not entry or "union_id" not in entry:
        return None
    info = {"union_id": entry.get("union_id"), "holder_id": entry.get("holder_id")}
    store.pop(code)
    return info


async def _issue_bind_code(
    msg: Bot.MessageSession, store: ExpiringTempDict, union_id: str, holder_id: str, prompt_key: str
) -> None:
    """
    生成绑定码并私信给发起方，随后在当前会话中给出提示。

    绑定码一旦出现在公屏上就可能被旁人抢先用掉，因此只走私信；私信发不出去时连同绑定码一起作废，
    以免它在有效期内躺在内存里被人撞上。

    :param store: 绑定码存储。
    :param union_id: 发起方所属的 union ID。
    :param holder_id: 发起方的平台 ID。
    :param prompt_key: 私信中绑定用法提示的 i18n 键。
    """
    if not msg.session_info.support_private_msg:
        await msg.finish(I18NContext("core.union.message.bind.code.private.unsupported"))

    generated = _generate_code(store, union_id, holder_id)
    sent = await msg.send_private_message(
        [
            I18NContext("core.union.message.bind.code", code=generated, disable_joke=True),
            I18NContext(
                prompt_key,
                minute=BIND_CODE_EXPIRED // 60,
                prefix=msg.session_info.prefixes[0],
                code=generated,
                disable_joke=True,
            ),
        ]
    )
    # 平台只在真的把消息投递出去时才会给回消息 ID，拿不到就说明这条私信没送达。
    if not sent:
        store.pop(generated)
        await msg.finish(I18NContext("core.union.message.bind.code.private.failed"))
    await msg.finish(I18NContext("core.union.message.bind.code.private.sent"))


def _id_lines(ids: list[str]) -> list:
    """
    将 ID 列表逐行展示，ID 不参与文本替换。
    """
    return [Plain(i, disable_joke=True) for i in ids]


async def _write_merge_log(keep_union: str, drop_union: str, snapshot: dict) -> None:
    """
    把合并前的快照写入存储，便于人工回溯。

    :param keep_union: 合并后保留的 union ID。
    :param drop_union: 被并入并删除的 union ID。
    :param snapshot: 合并前的双方数据快照。
    """
    stored, _ = await StoredData.get_or_create(stored_key=f"union_merge_log:{keep_union}", defaults={"value": []})
    logs = stored.value if isinstance(stored.value, list) else []
    logs.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "keep_union": keep_union,
            "drop_union": drop_union,
            **snapshot,
        }
    )
    stored.value = logs
    await stored.save()


async def _choose_conflicts(msg: Bot.MessageSession, conflicts: list[type]) -> set[str]:
    """
    逐个询问模块数据冲突时保留哪一份。

    :param conflicts: 双方都有数据的模块表模型。
    :return: 需要保留来源方（当前一侧）数据的表名集合。
    """
    keep_other_tables = set()
    for model in conflicts:
        if not await msg.wait_confirm(
            I18NContext("core.union.message.conflict.choose", module=get_union_module_name(model))
        ):
            keep_other_tables.add(get_table_name(model))
    return keep_other_tables


u = module("union", base=True, desc="{I18N:union.help.desc}", alias="uid")


@u.command("{{I18N:core.union.help}}")
async def _(msg: Bot.MessageSession):
    sender_info = msg.session_info.sender_info
    bound_ids = await sender_info.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.union.message.info", id=sender_info.union_id, disable_joke=True),
            I18NContext("core.union.message.info.bound", count=len(bound_ids)),
        ]
        + _id_lines(bound_ids)
    )


@u.command("bind [<code>] {{I18N:core.union.help.bind}}")
async def _(msg: Bot.MessageSession, code: str = None):
    current = msg.session_info.sender_info
    if not code:
        await _issue_bind_code(
            msg,
            _sender_bind_codes,
            current.union_id,
            msg.session_info.sender_id,
            "core.union.message.bind.code.prompt",
        )

    entry = _take_code(_sender_bind_codes, code)
    if not entry:
        await msg.finish(I18NContext("core.union.message.bind.code.invalid"))
    if entry["union_id"] == current.union_id:
        await msg.finish(I18NContext("core.union.message.bind.same"))

    # 生成绑定码的一方为发起方，冲突数据默认以发起方为准。
    initiator = await SenderInfo.get_or_none(union_id=entry["union_id"])
    if not initiator:
        await msg.finish(I18NContext("core.union.message.bind.code.invalid"))

    initiator_ids = await initiator.list_bound_ids()
    current_ids = await current.list_bound_ids()
    conflicts = await collect_union_conflicts(current.union_id, initiator.union_id, scope=UNION_SCOPE_SENDER)

    confirm_msg = [
        I18NContext("core.union.message.bind.confirm"),
        I18NContext("core.union.message.bind.confirm.initiator", count=len(initiator_ids)),
        *_id_lines(initiator_ids),
        I18NContext("core.union.message.bind.confirm.current", count=len(current_ids)),
        *_id_lines(current_ids),
    ]
    if Config("enable_petal", False):
        confirm_msg.append(
            I18NContext(
                "core.union.message.bind.confirm.petal",
                initiator=initiator.petal,
                current=current.petal,
                total=initiator.petal + current.petal,
            )
        )
    if conflicts:
        confirm_msg.append(
            I18NContext(
                "core.union.message.conflict",
                modules="{I18N:message.delimiter}".join(get_union_module_name(m) for m in conflicts),
            )
        )
    if not await msg.wait_confirm(confirm_msg):
        await msg.finish()

    keep_other_tables = await _choose_conflicts(msg, conflicts)
    await _write_merge_log(
        initiator.union_id,
        current.union_id,
        {
            "scope": UNION_SCOPE_SENDER,
            "keep_ids": initiator_ids,
            "drop_ids": current_ids,
            "keep_data": {
                "petal": initiator.petal,
                "warns": initiator.warns,
                "trusted": initiator.trusted,
                "superuser": initiator.superuser,
                "sender_data": initiator.sender_data,
            },
            "drop_data": {
                "petal": current.petal,
                "warns": current.warns,
                "trusted": current.trusted,
                "superuser": current.superuser,
                "sender_data": current.sender_data,
            },
        },
    )
    await initiator.merge_union(current, keep_other_tables)
    await msg.session_info.refresh_info()

    bound_ids = await initiator.list_bound_ids()
    await msg.finish([I18NContext("core.union.message.bind.success", count=len(bound_ids))] + _id_lines(bound_ids))


@u.command("unbind <user> {{I18N:core.union.help.unbind}}")
async def _(msg: Bot.MessageSession, user: str):
    sender_info = msg.session_info.sender_info
    bound_ids = await sender_info.list_bound_ids()
    if user not in bound_ids:
        await msg.finish(I18NContext("core.union.message.unbind.not_bound"))
    if len(bound_ids) <= 1:
        await msg.finish(I18NContext("core.union.message.unbind.last"))
    if not await msg.wait_confirm(I18NContext("core.union.message.unbind.confirm", id=user, disable_joke=True)):
        await msg.finish()
    if not await sender_info.unbind_id(user):
        await msg.finish(I18NContext("core.union.message.unbind.failed"))
    await msg.session_info.refresh_info()
    await msg.finish(I18NContext("core.union.message.unbind.success", id=user, disable_joke=True))


@u.command("target {{I18N:core.union.help.target}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    target_info = msg.session_info.target_info
    bound_ids = await target_info.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.union.message.target.info", id=target_info.union_id, disable_joke=True),
            I18NContext("core.union.message.target.info.bound", count=len(bound_ids)),
        ]
        + _id_lines(bound_ids)
    )


@u.command("target bind [<code>] {{I18N:core.union.help.target.bind}}", required_admin=True)
async def _(msg: Bot.MessageSession, code: str = None):
    current = msg.session_info.target_info
    if not code:
        await _issue_bind_code(
            msg,
            _target_bind_codes,
            current.union_id,
            msg.session_info.target_id,
            "core.union.message.target.bind.code.prompt",
        )

    entry = _take_code(_target_bind_codes, code)
    if not entry:
        await msg.finish(I18NContext("core.union.message.bind.code.invalid"))
    if entry["union_id"] == current.union_id:
        await msg.finish(I18NContext("core.union.message.target.bind.same"))

    initiator = await TargetInfo.get_or_none(union_id=entry["union_id"])
    if not initiator:
        await msg.finish(I18NContext("core.union.message.bind.code.invalid"))

    initiator_ids = await initiator.list_bound_ids()
    current_ids = await current.list_bound_ids()
    conflicts = await collect_union_conflicts(current.union_id, initiator.union_id, scope=UNION_SCOPE_TARGET)

    confirm_msg = [
        I18NContext("core.union.message.target.bind.confirm"),
        I18NContext("core.union.message.target.bind.confirm.initiator", count=len(initiator_ids)),
        *_id_lines(initiator_ids),
        I18NContext("core.union.message.target.bind.confirm.current", count=len(current_ids)),
        *_id_lines(current_ids),
    ]
    if conflicts:
        confirm_msg.append(
            I18NContext(
                "core.union.message.conflict",
                modules="{I18N:message.delimiter}".join(get_union_module_name(m) for m in conflicts),
            )
        )
    if not await msg.wait_confirm(confirm_msg):
        await msg.finish()

    keep_other_tables = await _choose_conflicts(msg, conflicts)
    await _write_merge_log(
        initiator.union_id,
        current.union_id,
        {
            "scope": UNION_SCOPE_TARGET,
            "keep_ids": initiator_ids,
            "drop_ids": current_ids,
            "keep_data": {
                "locale": initiator.locale,
                "modules": initiator.modules,
                "custom_admins": initiator.custom_admins,
                "banned_users": initiator.banned_users,
                "target_data": initiator.target_data,
            },
            "drop_data": {
                "locale": current.locale,
                "modules": current.modules,
                "custom_admins": current.custom_admins,
                "banned_users": current.banned_users,
                "target_data": current.target_data,
            },
        },
    )
    await initiator.merge_union(current, keep_other_tables)
    await msg.session_info.refresh_info()

    bound_ids = await initiator.list_bound_ids()
    await msg.finish(
        [I18NContext("core.union.message.target.bind.success", count=len(bound_ids))] + _id_lines(bound_ids)
    )


@u.command("target unbind <target> {{I18N:core.union.help.target.unbind}}", required_admin=True)
async def _(msg: Bot.MessageSession, target: str):
    target_info = msg.session_info.target_info
    bound_ids = await target_info.list_bound_ids()
    if target not in bound_ids:
        await msg.finish(I18NContext("core.union.message.target.unbind.not_bound"))
    if len(bound_ids) <= 1:
        await msg.finish(I18NContext("core.union.message.target.unbind.last"))
    if not await msg.wait_confirm(
        I18NContext("core.union.message.target.unbind.confirm", id=target, disable_joke=True)
    ):
        await msg.finish()
    if not await target_info.unbind_id(target):
        await msg.finish(I18NContext("core.union.message.target.unbind.failed"))
    await msg.session_info.refresh_info()
    await msg.finish(I18NContext("core.union.message.target.unbind.success", id=target, disable_joke=True))
