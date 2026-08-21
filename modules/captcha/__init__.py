import asyncio

from tortoise.transactions import in_transaction

from core.builtins.bot import Bot
from core.builtins.message.internal import ButtonFrame, I18NContext, Image, Mention
from core.builtins.session.info import EventInfo
from core.builtins.utils import command_prefix
from core.component import module
from core.config.base import CoreConfig
from core.constants.path import assets_path
from core.database.models import SenderUnionInfo, TargetUnionInfo, union_mutation
from core.logger import Logger
from core.utils.button import arrange_buttons
from core.utils.random import SecureRandom
from modules.captcha.database.models import CaptchaChallenge, CaptchaTrust
from modules.captcha.service import (
    get_origin_session,
    new_token,
    notify_origin,
    trust_challenge,
    verification_id,
)

CAPTCHA_MUTE_SECONDS = 30 * 24 * 60 * 60
CAPTCHA_EMOTE_ANSWER_OFFSET = 101
CAPTCHA_EMOTE_DIR = assets_path / "emotes" / "captcha_held"
CAPTCHA_EMOTES = tuple(sorted(path.stem for path in CAPTCHA_EMOTE_DIR.glob("*.gif")))
CAPTCHA_BUTTON_ROWS = 5
CAPTCHA_BUTTONS_PER_ROW = 4
CAPTCHA_CHOICE_COUNT = CAPTCHA_BUTTON_ROWS * CAPTCHA_BUTTONS_PER_ROW

captcha = module(
    "captcha",
    desc="{I18N:captcha.help.desc}",
    event=True,
    available_for="QQBot|Group",
)
token_module = module("token", base=True, hidden=True, available_for="QQBot")


def make_choices(answer: int) -> list[int]:
    """生成包含答案的 20 个不重复数字。"""
    choices = {answer}
    while len(choices) < CAPTCHA_CHOICE_COUNT:
        choices.add(SecureRandom.randint(1, 100))
    values = list(choices)
    SecureRandom.shuffle(values)
    return values


def make_emote_choices(answer: int) -> list[int]:
    """生成包含答案的 20 个不重复表情资源编号。"""
    if len(CAPTCHA_EMOTES) < CAPTCHA_CHOICE_COUNT:
        raise ValueError(f"At least {CAPTCHA_CHOICE_COUNT} captcha emotes are required.")
    choices = {answer}
    maximum = CAPTCHA_EMOTE_ANSWER_OFFSET + len(CAPTCHA_EMOTES) - 1
    while len(choices) < CAPTCHA_CHOICE_COUNT:
        choices.add(SecureRandom.randint(CAPTCHA_EMOTE_ANSWER_OFFSET, maximum))
    values = list(choices)
    SecureRandom.shuffle(values)
    return values


def captcha_emote_name(answer: int) -> str | None:
    index = answer - CAPTCHA_EMOTE_ANSWER_OFFSET
    if 0 <= index < len(CAPTCHA_EMOTES):
        return CAPTCHA_EMOTES[index]
    return None


async def _release_restriction_after_delivery_failure(
    session: Bot.MessageSession,
    challenge: CaptchaChallenge,
) -> bool:
    """验证码无法投递时尝试解禁，并保守记录仍可能存在的平台限制。"""
    # 先写成活跃失败状态：若解禁调用抛错、取消或进程在结果落库前退出，Union 删除和
    # 解绑逻辑仍会保留这条真实平台限制的归属，不会把受限成员遗失在无引用状态。
    challenge.status = "failed"
    await challenge.save(update_fields=["status"])
    try:
        result = await session.unrestrict_member(challenge.sender_id, wait=True)
    except asyncio.CancelledError:
        raise
    except Exception:
        Logger.exception(f"Failed to release captcha restriction for {challenge.sender_id}: ")
        return False

    if not result or not result.get("success"):
        Logger.warning(f"Failed to release captcha restriction for {challenge.sender_id}.")
        return False

    # 只有平台明确确认解禁成功后，才把记录降为无需外部清理的普通错误。
    challenge.status = "error"
    await challenge.save(update_fields=["status"])
    return True


@captcha.event("member_left", available_for="QQBot|Group")
async def member_left(event: EventInfo):
    async with union_mutation():
        async with in_transaction("default") as connection:
            # 解绑与事件可能并发；锁内按平台 ID 重解析，确保清理的是成员当前所属的 Union。
            # Challenge 与 Trust 必须一起删除，避免后一步异常留下无法再由退群事件清理的半状态。
            # 事务内只有一条连接，避免 EventInfo.refresh_info() 用 gather 同时占用它。
            target = await TargetUnionInfo.resolve_union(event.target_id, create=False)
            sender = await SenderUnionInfo.resolve_union(event.sender_id, create=False)
            if not target:
                raise ValueError(f"TargetUnionInfo not found for target_id: {event.target_id}")
            if not sender:
                return
            event.target_union_info = target
            event.target_union_id = target.union_id
            event.sender_union_info = sender
            event.sender_union_id = sender.union_id
            await (
                CaptchaChallenge.filter(
                    target_union_id=event.target_union_id,
                    sender_union_id=event.sender_union_id,
                )
                .using_db(connection)
                .delete()
            )
            await (
                CaptchaTrust.filter(
                    target_union_id=event.target_union_id,
                    sender_union_id=event.sender_union_id,
                )
                .using_db(connection)
                .delete()
            )


@captcha.event("member_joined", available_for="QQBot|Group")
async def member_joined(event: EventInfo):
    # 只把事件的 Union 重解析和 challenge 的创建／重置放在 mutation 锁内；平台禁言、
    # 发消息等网络操作在锁外执行。这样解绑不会在旧 EventInfo 与建行之间插入，也不会
    # 因等待平台响应而阻塞其它 Union 管理操作。
    async with union_mutation():
        await event.refresh_info()
        challenge_id = verification_id(event.target_union_id, event.sender_union_id)

        if await CaptchaTrust.exists(
            target_union_id=event.target_union_id,
            sender_union_id=event.sender_union_id,
        ):
            return

        existing = await (
            CaptchaChallenge.filter(
                target_union_id=event.target_union_id,
                sender_union_id=event.sender_union_id,
            )
            .order_by("-updated_at")
            .first()
        )
        if existing and existing.status in {"pending", "failed", "verified"}:
            return

        if CoreConfig.use_emote and len(CAPTCHA_EMOTES) >= CAPTCHA_CHOICE_COUNT:
            answer = CAPTCHA_EMOTE_ANSWER_OFFSET + SecureRandom.randint(0, len(CAPTCHA_EMOTES) - 1)
            choices = make_emote_choices(answer)
        else:
            if CoreConfig.use_emote:
                Logger.warning(
                    f"Captcha emote mode requires at least {CAPTCHA_CHOICE_COUNT} GIF resources in {CAPTCHA_EMOTE_DIR}."
                )
            answer = SecureRandom.randint(1, 100)
            choices = make_choices(answer)
        defaults = {
            "target_union_id": event.target_union_id,
            "sender_union_id": event.sender_union_id,
            "target_id": event.target_id,
            "sender_id": event.sender_id,
            "token": new_token(),
            "answer": answer,
            "choices": choices,
            "status": "preparing",
            "verified_at": None,
        }
        if existing and existing.status == "preparing":
            challenge = existing
            if len(challenge.choices) != CAPTCHA_CHOICE_COUNT:
                update_fields = ["choices"]
                if captcha_emote_name(challenge.answer) and len(CAPTCHA_EMOTES) >= CAPTCHA_CHOICE_COUNT:
                    challenge.choices = make_emote_choices(challenge.answer)
                else:
                    if captcha_emote_name(challenge.answer):
                        challenge.answer = SecureRandom.randint(1, 100)
                        update_fields.append("answer")
                    challenge.choices = make_choices(challenge.answer)
                await challenge.save(update_fields=update_fields)
        elif existing:
            for key, value in defaults.items():
                setattr(existing, key, value)
            challenge = existing
            await challenge.save(update_fields=list(defaults))
        else:
            challenge, created = await CaptchaChallenge.get_or_create(challenge_id=challenge_id, defaults=defaults)
            if not created:
                return

    fetched = await Bot.fetch_target(event.target_id, sender_id=event.sender_id, create=False)
    if not fetched:
        challenge.status = "error"
        await challenge.save(update_fields=["status"])
        return

    session = await Bot.FetchedMessageSession.from_session_info(fetched)
    restrict_result = await session.restrict_member(event.sender_id, CAPTCHA_MUTE_SECONDS, wait=True)
    if not restrict_result or not restrict_result.get("success"):
        challenge.status = "error"
        await challenge.save(update_fields=["status"])
        await session.send_message(I18NContext("captcha.message.permission_error"), quote=False)
        return

    prefix = event.prefixes[0]
    command = f"{prefix}token {challenge.token}"
    private_command = f"{command_prefix[0]}token {challenge.token}"
    emote_name = captcha_emote_name(challenge.answer)
    if emote_name:
        locale = session.session_info.locale
        buttons = [
            (locale.t(f"captcha.emote.{captcha_emote_name(choice)}"), f"{command} {choice}")
            for choice in challenge.choices
        ]
        support_markdown = session.session_info.support_markdown
        session.session_info.support_markdown = False
        try:
            image_sent = await session.send_message(Image(CAPTCHA_EMOTE_DIR / f"{emote_name}.gif"), quote=False)
        finally:
            session.session_info.support_markdown = support_markdown
        if not image_sent.message_id:
            Logger.warning(f"Failed to send verification emote in {event.target_id}.")
            await _release_restriction_after_delivery_failure(session, challenge)
            return
        message = [
            Mention(event.sender_id),
            I18NContext("captcha.message.emote_welcome"),
            I18NContext(
                "captcha.message.emote_challenge",
                bot_name=session.session_info.bot_name,
                command=private_command,
            ),
            ButtonFrame(arrange_buttons(buttons, per_row=CAPTCHA_BUTTONS_PER_ROW)),
        ]
    else:
        buttons = [(str(choice), f"{command} {choice}") for choice in challenge.choices]
        message = [
            Mention(event.sender_id),
            I18NContext("captcha.message.challenge", answer=challenge.answer, command=private_command),
            ButtonFrame(arrange_buttons(buttons, per_row=CAPTCHA_BUTTONS_PER_ROW)),
        ]
    sent = await session.send_message(message, quote=False)
    if sent.message_id:
        challenge.status = "pending"
        await challenge.save(update_fields=["status"])
        return

    Logger.warning(f"Failed to send verification challenge in {event.target_id}.")
    await _release_restriction_after_delivery_failure(session, challenge)


@token_module.command("<token> [<answer>]", available_for="QQBot")
async def token(msg: Bot.MessageSession, token: str, answer: int | None = None):
    challenge = await CaptchaChallenge.get_or_none(token=token)
    if not challenge:
        await msg.finish(I18NContext("token.message.invalid"))
    if challenge.sender_union_id != msg.session_info.sender_union_id:
        await msg.finish(I18NContext("token.message.wrong_user"))
    if challenge.status == "failed":
        await msg.finish(I18NContext("token.message.failed"))
    if challenge.status == "verified":
        await msg.finish(I18NContext("token.message.verified"))
    if challenge.status != "pending":
        await msg.finish(I18NContext("token.message.unavailable"))

    if answer is not None and answer != challenge.answer:
        # 只允许仍处于 pending 的请求写入失败状态。另一个正确请求可能已在本次查询后完成验证，
        # 旧实例不得再把 verified 覆盖回 failed，留下“已有 Trust 但挑战仍活跃”的矛盾状态。
        updated = await CaptchaChallenge.filter(challenge_id=challenge.challenge_id, status="pending").update(
            status="failed"
        )
        if not updated:
            fresh = await CaptchaChallenge.get_or_none(challenge_id=challenge.challenge_id)
            if not fresh:
                await msg.finish(I18NContext("token.message.invalid"))
            if fresh.status == "verified":
                await msg.finish(I18NContext("token.message.verified"))
            if fresh.status == "failed":
                await msg.finish(I18NContext("token.message.failed"))
            await msg.finish(I18NContext("token.message.unavailable"))
        challenge.status = "failed"
        await notify_origin(challenge, "captcha.message.failed")
        await msg.finish(I18NContext("token.message.incorrect"))

    origin = await get_origin_session(challenge)
    if not origin:
        await msg.finish(I18NContext("token.message.unavailable"))
    unrestrict_result = await origin.unrestrict_member(challenge.sender_id, wait=True)
    if not unrestrict_result or not unrestrict_result.get("success"):
        await msg.finish(I18NContext("token.message.unrestrict_failed"))

    if not await trust_challenge(challenge):
        await msg.finish(I18NContext("token.message.unavailable"))
    if msg.session_info.target_id != challenge.target_id:
        await notify_origin(challenge, "captcha.message.success")
    await msg.finish(I18NContext("token.message.success"))
