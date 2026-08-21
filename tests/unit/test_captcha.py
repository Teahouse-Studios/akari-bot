"""QQBot 入群验证码模块单元测试。"""

import asyncio

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.message.elements import ButtonFrameElement, I18NContextElement, ImageElement
from core.builtins.session.features import Features
from core.builtins.session.info import EventInfo, SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.utils import command_prefix
from core.constants.exceptions import SessionFinished
from core.database.models import SenderUnionInfo, TargetUnionInfo
from core.tester import Tester, func_case
from modules.captcha import (
    CAPTCHA_BUTTON_ROWS,
    CAPTCHA_BUTTONS_PER_ROW,
    CAPTCHA_CHOICE_COUNT,
    CAPTCHA_EMOTE_ANSWER_OFFSET,
    CAPTCHA_EMOTE_DIR,
    CAPTCHA_EMOTES,
    captcha_emote_name,
    make_choices,
    make_emote_choices,
    member_joined,
    member_left,
    token as process_token,
)
from modules.captcha.database.models import CaptchaChallenge, CaptchaTrust
from modules.captcha.service import trust_challenge, verification_id

MYSQL_MAX_INDEX_BYTES = 3072
UTF8MB4_MAX_BYTES_PER_CHAR = 4


def _test_captcha_indexes_fit_mysql_limit():
    """验证码表的显式与字段索引均不得超过 MySQL InnoDB 的索引长度上限。"""
    for model in (CaptchaTrust, CaptchaChallenge):
        for field in model._meta.fields_map.values():
            if not (getattr(field, "index", False) or getattr(field, "unique", False) or getattr(field, "pk", False)):
                continue
            max_length = getattr(field, "max_length", None)
            if max_length and max_length * UTF8MB4_MAX_BYTES_PER_CHAR > MYSQL_MAX_INDEX_BYTES:
                return False

        for index in model._meta.indexes:
            if not isinstance(index, tuple):
                continue
            index_bytes = sum(
                (getattr(model._meta.fields_map[field_name], "max_length", 0) or 0) * UTF8MB4_MAX_BYTES_PER_CHAR
                for field_name in index
            )
            if index_bytes > MYSQL_MAX_INDEX_BYTES:
                return False
    return True


def _test_choices_are_valid():
    for answer in (1, 50, 100):
        choices = make_choices(answer)
        if len(choices) != CAPTCHA_CHOICE_COUNT or len(set(choices)) != CAPTCHA_CHOICE_COUNT or answer not in choices:
            return False
        if any(choice < 1 or choice > 100 for choice in choices):
            return False
    return True


def _test_emote_choices_are_valid():
    if len(CAPTCHA_EMOTES) < CAPTCHA_CHOICE_COUNT:
        return False
    answer = CAPTCHA_EMOTE_ANSWER_OFFSET
    choices = make_emote_choices(answer)
    return (
        len(choices) == CAPTCHA_CHOICE_COUNT
        and len(set(choices)) == CAPTCHA_CHOICE_COUNT
        and answer in choices
        and all(captcha_emote_name(choice) in CAPTCHA_EMOTES for choice in choices)
        and all((CAPTCHA_EMOTE_DIR / f"{name}.gif").is_file() for name in CAPTCHA_EMOTES)
    )


async def _test_captcha_event_and_private_token():
    target_id = "QQBot|Group|captcha_test"
    sender_id = "QQBot|captcha_user"
    target = await TargetUnionInfo.get_by_target_id(target_id)
    await target.edit_target_data("command_prefix", ["!"])
    group_session = await SessionInfo.assign(
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
        features=Features(support_button=True, read_all_messages=True),
    )
    event = await EventInfo.assign(
        event_name="member_joined",
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
    )
    restrict = AsyncMock(return_value={"success": True})
    sent_messages = []

    async def send_message(_self, message, **_kwargs):
        sent_messages.append(message)
        return SimpleNamespace(message_id=["verification-message"])

    with (
        patch("modules.captcha.CoreConfig", new=SimpleNamespace(use_emote=False)),
        patch("core.builtins.bot.Bot.fetch_target", new=AsyncMock(return_value=group_session)),
        patch.object(MessageSession, "restrict_member", new=restrict),
        patch.object(MessageSession, "send_message", new=send_message),
    ):
        await member_joined(event)
        await member_joined(event)

    challenge_id = verification_id(group_session.target_union_id, group_session.sender_union_id)
    challenge = await CaptchaChallenge.get(challenge_id=challenge_id)
    frame = next((element for element in sent_messages[0] if isinstance(element, ButtonFrameElement)), None)
    prompt = next((element for element in sent_messages[0] if isinstance(element, I18NContextElement)), None)
    button_values = [button.value for row in frame.rows for button in row.buttons] if frame else []
    rendered_prompt = group_session.locale.t(prompt.key, **prompt.kwargs) if prompt else ""
    if (
        challenge.status != "pending"
        or len(challenge.choices) != CAPTCHA_CHOICE_COUNT
        or challenge.answer not in challenge.choices
        or restrict.await_count != 1
        or frame is None
        or len(button_values) != CAPTCHA_CHOICE_COUNT
        or len(frame.rows) != CAPTCHA_BUTTON_ROWS
        or any(len(row.buttons) != CAPTCHA_BUTTONS_PER_ROW for row in frame.rows)
        or any(not value.startswith(f"!token {challenge.token} ") for value in button_values)
        or prompt is None
        or prompt.kwargs["command"] != f"{command_prefix[0]}token {challenge.token}"
        or f"```\n{command_prefix[0]}token {challenge.token}\n```" not in rendered_prompt
        or event.prefixes[0] != "!"
    ):
        return False

    private_session = await SessionInfo.assign(
        target_id="QQBot|C2C|captcha_user",
        target_from="QQBot|C2C",
        client_name="QQBot",
        sender_id=group_session.sender_id,
        sender_from="QQBot",
        is_private=True,
    )
    msg = MessageSession(session_info=private_session)
    origin = AsyncMock()
    origin.unrestrict_member.return_value = {"success": True}
    responses = []

    async def finish(_self, message=None, **_kwargs):
        responses.append(message)
        raise SessionFinished

    with (
        patch("modules.captcha.get_origin_session", new=AsyncMock(return_value=origin)),
        patch("modules.captcha.notify_origin", new=AsyncMock()),
        patch.object(MessageSession, "finish", new=finish),
    ):
        try:
            await process_token(msg, challenge.token)
        except SessionFinished:
            pass

    await challenge.refresh_from_db()
    return (
        challenge.status == "verified"
        and await CaptchaTrust.exists(trust_id=challenge_id)
        and origin.unrestrict_member.await_count == 1
        and bool(responses)
    )


async def _test_wrong_button_marks_challenge_failed():
    target_id = "QQBot|Group|captcha_wrong_answer"
    sender_id = "QQBot|captcha_wrong_answer_user"
    group_session = await SessionInfo.assign(
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
        features=Features(support_button=True, read_all_messages=True),
    )
    event = await EventInfo.assign(
        event_name="member_joined",
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
    )

    async def send_message(_self, _message, **_kwargs):
        return SimpleNamespace(message_id=["verification-message"])

    with (
        patch("modules.captcha.CoreConfig", new=SimpleNamespace(use_emote=False)),
        patch("core.builtins.bot.Bot.fetch_target", new=AsyncMock(return_value=group_session)),
        patch.object(MessageSession, "restrict_member", new=AsyncMock(return_value={"success": True})),
        patch.object(MessageSession, "send_message", new=send_message),
    ):
        await member_joined(event)

    challenge_id = verification_id(group_session.target_union_id, group_session.sender_union_id)
    challenge = await CaptchaChallenge.get(challenge_id=challenge_id)
    msg = MessageSession(session_info=group_session)
    notify = AsyncMock()
    origin = AsyncMock()

    async def finish(_self, _message=None, **_kwargs):
        raise SessionFinished

    wrong_answer = next(value for value in range(1, 101) if value != challenge.answer)
    with (
        patch("modules.captcha.get_origin_session", new=AsyncMock(return_value=origin)),
        patch("modules.captcha.notify_origin", new=notify),
        patch.object(MessageSession, "finish", new=finish),
    ):
        try:
            await process_token(msg, challenge.token, wrong_answer)
        except SessionFinished:
            pass

    await challenge.refresh_from_db()
    return challenge.status == "failed" and notify.await_count == 1 and origin.unrestrict_member.await_count == 0


async def _test_preparing_challenge_resumes_after_restart():
    target_id = "QQBot|Group|captcha_resume"
    sender_id = "QQBot|captcha_resume_user"
    session = await SessionInfo.assign(
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
        features=Features(support_button=True, read_all_messages=True),
    )
    event = await EventInfo.assign(
        event_name="member_joined",
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
    )
    challenge_id = verification_id(session.target_union_id, session.sender_union_id)
    challenge = await CaptchaChallenge.create(
        challenge_id=challenge_id,
        target_union_id=session.target_union_id,
        sender_union_id=session.sender_union_id,
        target_id=target_id,
        sender_id=sender_id,
        token="resume-token",
        answer=42,
        choices=[1, 21, 42, 63, 84],
        status="preparing",
    )

    async def send_message(_self, _message, **_kwargs):
        return SimpleNamespace(message_id=["verification-message"])

    restrict = AsyncMock(return_value={"success": True})
    with (
        patch("modules.captcha.CoreConfig", new=SimpleNamespace(use_emote=False)),
        patch("core.builtins.bot.Bot.fetch_target", new=AsyncMock(return_value=session)),
        patch.object(MessageSession, "restrict_member", new=restrict),
        patch.object(MessageSession, "send_message", new=send_message),
    ):
        await member_joined(event)

    await challenge.refresh_from_db()
    return (
        challenge.status == "pending"
        and challenge.token == "resume-token"
        and len(challenge.choices) == CAPTCHA_CHOICE_COUNT
        and challenge.answer in challenge.choices
        and restrict.await_count == 1
    )


async def _test_delivery_failure_marks_error_after_successful_unrestrict():
    target_id = "QQBot|Group|captcha-delivery-cleanup-success"
    sender_id = "QQBot|captcha-delivery-cleanup-success-user"
    session = await SessionInfo.assign(
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
        features=Features(support_button=True, read_all_messages=True),
    )
    event = await EventInfo.assign(
        event_name="member_joined",
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
    )
    unrestrict = AsyncMock(return_value={"success": True})

    async def send_message(_self, _message, **_kwargs):
        return SimpleNamespace(message_id=[])

    with (
        patch("modules.captcha.CoreConfig", new=SimpleNamespace(use_emote=False)),
        patch("core.builtins.bot.Bot.fetch_target", new=AsyncMock(return_value=session)),
        patch.object(MessageSession, "restrict_member", new=AsyncMock(return_value={"success": True})),
        patch.object(MessageSession, "unrestrict_member", new=unrestrict),
        patch.object(MessageSession, "send_message", new=send_message),
    ):
        await member_joined(event)

    challenge = await CaptchaChallenge.get(
        challenge_id=verification_id(session.target_union_id, session.sender_union_id)
    )
    return challenge.status == "error" and unrestrict.await_count == 1


async def _test_delivery_failure_keeps_active_status_when_unrestrict_fails():
    target_id = "QQBot|Group|captcha-delivery-cleanup-failed"
    sender_id = "QQBot|captcha-delivery-cleanup-failed-user"
    session = await SessionInfo.assign(
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
        features=Features(support_button=True, read_all_messages=True),
    )
    event = await EventInfo.assign(
        event_name="member_joined",
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
    )
    unrestrict = AsyncMock(return_value={"success": False})

    async def send_message(_self, _message, **_kwargs):
        return SimpleNamespace(message_id=[])

    with (
        patch("modules.captcha.CoreConfig", new=SimpleNamespace(use_emote=False)),
        patch("core.builtins.bot.Bot.fetch_target", new=AsyncMock(return_value=session)),
        patch.object(MessageSession, "restrict_member", new=AsyncMock(return_value={"success": True})),
        patch.object(MessageSession, "unrestrict_member", new=unrestrict),
        patch.object(MessageSession, "send_message", new=send_message),
    ):
        await member_joined(event)

    challenge = await CaptchaChallenge.get(
        challenge_id=verification_id(session.target_union_id, session.sender_union_id)
    )
    return challenge.status == "failed" and unrestrict.await_count == 1


async def _test_emote_captcha_uses_localized_buttons():
    target_id = "QQBot|Group|captcha_emote"
    sender_id = "QQBot|captcha_emote_user"
    session = await SessionInfo.assign(
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
        features=Features(
            support_button=True,
            support_image=True,
            support_markdown=True,
            read_all_messages=True,
        ),
    )
    session.bot_name = "测试机器人"
    event = await EventInfo.assign(
        event_name="member_joined",
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
    )
    sent_messages = []

    async def send_message(_self, message, **_kwargs):
        sent_messages.append((_self.session_info.support_markdown, message if isinstance(message, list) else [message]))
        return SimpleNamespace(message_id=["emote-verification-message"])

    with (
        patch("modules.captcha.CoreConfig", new=SimpleNamespace(use_emote=True)),
        patch("core.builtins.bot.Bot.fetch_target", new=AsyncMock(return_value=session)),
        patch.object(MessageSession, "restrict_member", new=AsyncMock(return_value={"success": True})),
        patch.object(MessageSession, "send_message", new=send_message),
    ):
        await member_joined(event)

    challenge_id = verification_id(session.target_union_id, session.sender_union_id)
    challenge = await CaptchaChallenge.get(challenge_id=challenge_id)
    image_markdown, image_message = sent_messages[0]
    prompt_markdown, message = sent_messages[1]
    welcome = next(
        (
            element
            for element in message
            if isinstance(element, I18NContextElement) and element.key == "captcha.message.emote_welcome"
        ),
        None,
    )
    prompt = next(
        (
            element
            for element in message
            if isinstance(element, I18NContextElement) and element.key == "captcha.message.emote_challenge"
        ),
        None,
    )
    image = next((element for element in image_message if isinstance(element, ImageElement)), None)
    frame = next((element for element in message if isinstance(element, ButtonFrameElement)), None)
    emote_name = captcha_emote_name(challenge.answer)
    buttons = [button for row in frame.rows for button in row.buttons] if frame else []
    expected_labels = [session.locale.t(f"captcha.emote.{captcha_emote_name(choice)}") for choice in challenge.choices]
    rendered_prompt = session.locale.t(prompt.key, **prompt.kwargs) if prompt else ""

    return (
        challenge.status == "pending"
        and len(sent_messages) == 2
        and emote_name in CAPTCHA_EMOTES
        and not image_markdown
        and prompt_markdown
        and session.support_markdown
        and welcome is not None
        and session.locale.t(welcome.key) == "欢迎加入，正在验证你是否为人类！"
        and prompt is not None
        and prompt.kwargs["bot_name"] == "测试机器人"
        and f"```\n{command_prefix[0]}token {challenge.token}\n```" in rendered_prompt
        and image is not None
        and image.path == str(CAPTCHA_EMOTE_DIR / f"{emote_name}.gif")
        and [button.show for button in buttons] == expected_labels
        and [int(button.value.rsplit(maxsplit=1)[1]) for button in buttons] == challenge.choices
        and len(frame.rows) == CAPTCHA_BUTTON_ROWS
        and all(len(row.buttons) == CAPTCHA_BUTTONS_PER_ROW for row in frame.rows)
    )


async def _test_emote_captcha_restores_markdown_after_send_error():
    """表情图片发送抛错时，也必须恢复会话原有的 Markdown 能力。"""
    target_id = "QQBot|Group|captcha-emote-markdown-error"
    sender_id = "QQBot|captcha-emote-markdown-error-user"
    session = await SessionInfo.assign(
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
        features=Features(
            support_button=True,
            support_image=True,
            support_markdown=False,
            read_all_messages=True,
        ),
    )
    event = await EventInfo.assign(
        event_name="member_joined",
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
    )

    with (
        patch("modules.captcha.CoreConfig", new=SimpleNamespace(use_emote=True)),
        patch("core.builtins.bot.Bot.fetch_target", new=AsyncMock(return_value=session)),
        patch.object(MessageSession, "restrict_member", new=AsyncMock(return_value={"success": True})),
        patch.object(MessageSession, "send_message", new=AsyncMock(side_effect=RuntimeError("send failed"))),
    ):
        try:
            await member_joined(event)
        except RuntimeError:
            pass
        else:
            return False

    return session.support_markdown is False


async def _test_member_left_removes_verification_records():
    target_id = "QQBot|Group|captcha_member_left"
    sender_id = "QQBot|captcha_member_left_user"
    event = await EventInfo.assign(
        event_name="member_left",
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
    )
    challenge_id = "opaque-migrated-captcha-member-left"
    await CaptchaChallenge.create(
        challenge_id=challenge_id,
        target_union_id=event.target_union_id,
        sender_union_id=event.sender_union_id,
        target_id=target_id,
        sender_id=sender_id,
        token="member-left-token",
        answer=42,
        choices=[1, 21, 42, 63, 84],
        status="pending",
    )
    await CaptchaTrust.create(
        trust_id=challenge_id,
        target_union_id=event.target_union_id,
        sender_union_id=event.sender_union_id,
    )

    await member_left(event)
    await member_left(event)

    return not await CaptchaChallenge.exists(challenge_id=challenge_id) and not await CaptchaTrust.exists(
        target_union_id=event.target_union_id,
        sender_union_id=event.sender_union_id,
    )


async def _test_sender_union_merge_migrates_captcha_references():
    target = await TargetUnionInfo.resolve_union("QQBot|Group|captcha-merge-sender-target")
    keep = await SenderUnionInfo.resolve_union("QQBot|captcha-merge-sender-keep")
    other = await SenderUnionInfo.resolve_union("QQBot|captcha-merge-sender-other")
    old_trust_id = verification_id(target.union_id, other.union_id)
    challenge = await CaptchaChallenge.create(
        challenge_id=old_trust_id,
        target_union_id=target.union_id,
        sender_union_id=other.union_id,
        target_id="QQBot|Group|captcha-merge-sender-target",
        sender_id="QQBot|captcha-merge-sender-other",
        token="captcha-merge-sender-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    await CaptchaTrust.create(
        trust_id=old_trust_id,
        target_union_id=target.union_id,
        sender_union_id=other.union_id,
    )

    merged = await keep.merge_union(other)
    await challenge.refresh_from_db()
    new_trust_id = verification_id(target.union_id, merged.union_id)
    return (
        challenge.sender_union_id == merged.union_id
        and challenge.challenge_id == old_trust_id
        and await CaptchaTrust.exists(
            trust_id=new_trust_id,
            target_union_id=target.union_id,
            sender_union_id=merged.union_id,
        )
        and not await CaptchaTrust.exists(trust_id=old_trust_id)
    )


async def _test_target_union_merge_migrates_captcha_references():
    sender = await SenderUnionInfo.resolve_union("QQBot|captcha-merge-target-sender")
    keep = await TargetUnionInfo.resolve_union("QQBot|Group|captcha-merge-target-keep")
    other = await TargetUnionInfo.resolve_union("QQBot|Group|captcha-merge-target-other")
    old_trust_id = verification_id(other.union_id, sender.union_id)
    challenge = await CaptchaChallenge.create(
        challenge_id=old_trust_id,
        target_union_id=other.union_id,
        sender_union_id=sender.union_id,
        target_id="QQBot|Group|captcha-merge-target-other",
        sender_id="QQBot|captcha-merge-target-sender",
        token="captcha-merge-target-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    await CaptchaTrust.create(
        trust_id=old_trust_id,
        target_union_id=other.union_id,
        sender_union_id=sender.union_id,
    )

    merged = await keep.merge_union(other)
    await challenge.refresh_from_db()
    new_trust_id = verification_id(merged.union_id, sender.union_id)
    return (
        challenge.target_union_id == merged.union_id
        and challenge.challenge_id == old_trust_id
        and await CaptchaTrust.exists(
            trust_id=new_trust_id,
            target_union_id=merged.union_id,
            sender_union_id=sender.union_id,
        )
        and not await CaptchaTrust.exists(trust_id=old_trust_id)
    )


async def _test_sender_unbind_moves_active_challenge_only():
    target = await TargetUnionInfo.resolve_union("QQBot|Group|captcha-unbind-sender-target")
    kept_id = "QQBot|captcha-unbind-sender-kept"
    split_id = "QQBot|captcha-unbind-sender-split"
    sender = await SenderUnionInfo.resolve_union(kept_id)
    if not await sender.bind_id(split_id):
        return False

    old_trust_id = verification_id(target.union_id, sender.union_id)
    active = await CaptchaChallenge.create(
        challenge_id="captcha-unbind-sender-active",
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        target_id="QQBot|Group|captcha-unbind-sender-target",
        sender_id=split_id,
        token="captcha-unbind-sender-active-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    sibling = await CaptchaChallenge.create(
        challenge_id="captcha-unbind-sender-sibling",
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        target_id="QQBot|Group|captcha-unbind-sender-target",
        sender_id=kept_id,
        token="captcha-unbind-sender-sibling-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    verified = await CaptchaChallenge.create(
        challenge_id="captcha-unbind-sender-verified",
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        target_id="QQBot|Group|captcha-unbind-sender-target",
        sender_id=split_id,
        token="captcha-unbind-sender-verified-token",
        answer=42,
        choices=[42],
        status="verified",
    )
    await CaptchaTrust.create(
        trust_id=old_trust_id,
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
    )

    split = await sender.unbind_id(split_id)
    if not split:
        return False
    await active.refresh_from_db()
    await sibling.refresh_from_db()
    await verified.refresh_from_db()
    return (
        active.sender_union_id == split.union_id
        and sibling.sender_union_id == sender.union_id
        and verified.sender_union_id == sender.union_id
        and await CaptchaTrust.exists(trust_id=old_trust_id, sender_union_id=sender.union_id)
        and not await CaptchaTrust.exists(sender_union_id=split.union_id)
    )


async def _test_target_unbind_moves_active_challenge_only():
    sender = await SenderUnionInfo.resolve_union("QQBot|captcha-unbind-target-sender")
    kept_id = "QQBot|Group|captcha-unbind-target-kept"
    split_id = "QQBot|Group|captcha-unbind-target-split"
    target = await TargetUnionInfo.resolve_union(kept_id)
    if not await target.bind_id(split_id):
        return False

    old_trust_id = verification_id(target.union_id, sender.union_id)
    active = await CaptchaChallenge.create(
        challenge_id="captcha-unbind-target-active",
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        target_id=split_id,
        sender_id="QQBot|captcha-unbind-target-sender",
        token="captcha-unbind-target-active-token",
        answer=42,
        choices=[42],
        status="failed",
    )
    sibling = await CaptchaChallenge.create(
        challenge_id="captcha-unbind-target-sibling",
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        target_id=kept_id,
        sender_id="QQBot|captcha-unbind-target-sender",
        token="captcha-unbind-target-sibling-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    verified = await CaptchaChallenge.create(
        challenge_id="captcha-unbind-target-verified",
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        target_id=split_id,
        sender_id="QQBot|captcha-unbind-target-sender",
        token="captcha-unbind-target-verified-token",
        answer=42,
        choices=[42],
        status="verified",
    )
    await CaptchaTrust.create(
        trust_id=old_trust_id,
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
    )

    split = await target.unbind_id(split_id)
    if not split:
        return False
    await active.refresh_from_db()
    await sibling.refresh_from_db()
    await verified.refresh_from_db()
    return (
        active.target_union_id == split.union_id
        and sibling.target_union_id == target.union_id
        and verified.target_union_id == target.union_id
        and await CaptchaTrust.exists(trust_id=old_trust_id, target_union_id=target.union_id)
        and not await CaptchaTrust.exists(target_union_id=split.union_id)
    )


async def _test_sender_unbind_during_member_join_preserves_challenge_migration():
    target_id = "QQBot|Group|captcha-concurrent-unbind-sender-target"
    kept_id = "QQBot|captcha-concurrent-unbind-sender-kept"
    split_id = "QQBot|captcha-concurrent-unbind-sender-split"
    sender = await SenderUnionInfo.resolve_union(kept_id)
    if not await sender.bind_id(split_id):
        return False
    session = await SessionInfo.assign(
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=split_id,
        sender_from="QQBot",
        features=Features(support_button=True, read_all_messages=True),
    )
    event = await EventInfo.assign(
        event_name="member_joined",
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=split_id,
        sender_from="QQBot",
    )
    result = {}

    async def restrict_member(_self, _user_id, _duration=None, **_kwargs):
        result["split"] = await sender.unbind_id(split_id)
        return {"success": True}

    async def send_message(_self, _message, **_kwargs):
        return SimpleNamespace(message_id=["verification-message"])

    with (
        patch("modules.captcha.CoreConfig", new=SimpleNamespace(use_emote=False)),
        patch("core.builtins.bot.Bot.fetch_target", new=AsyncMock(return_value=session)),
        patch.object(MessageSession, "restrict_member", new=restrict_member),
        patch.object(MessageSession, "send_message", new=send_message),
    ):
        await member_joined(event)

    split = result.get("split")
    challenge = await CaptchaChallenge.get_or_none(sender_id=split_id)
    return bool(split and challenge and challenge.status == "pending" and challenge.sender_union_id == split.union_id)


async def _test_target_unbind_during_member_join_preserves_challenge_migration():
    kept_id = "QQBot|Group|captcha-concurrent-unbind-target-kept"
    split_id = "QQBot|Group|captcha-concurrent-unbind-target-split"
    sender_id = "QQBot|captcha-concurrent-unbind-target-sender"
    target = await TargetUnionInfo.resolve_union(kept_id)
    if not await target.bind_id(split_id):
        return False
    session = await SessionInfo.assign(
        target_id=split_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
        features=Features(support_button=True, read_all_messages=True),
    )
    event = await EventInfo.assign(
        event_name="member_joined",
        target_id=split_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
    )
    result = {}

    async def restrict_member(_self, _user_id, _duration=None, **_kwargs):
        result["split"] = await target.unbind_id(split_id)
        return {"success": True}

    async def send_message(_self, _message, **_kwargs):
        return SimpleNamespace(message_id=["verification-message"])

    with (
        patch("modules.captcha.CoreConfig", new=SimpleNamespace(use_emote=False)),
        patch("core.builtins.bot.Bot.fetch_target", new=AsyncMock(return_value=session)),
        patch.object(MessageSession, "restrict_member", new=restrict_member),
        patch.object(MessageSession, "send_message", new=send_message),
    ):
        await member_joined(event)

    split = result.get("split")
    challenge = await CaptchaChallenge.get_or_none(target_id=split_id)
    return bool(split and challenge and challenge.status == "pending" and challenge.target_union_id == split.union_id)


async def _test_sender_unbind_during_token_moves_trust_to_current_union():
    """平台解禁等待期间用户解绑时，原 token 应在新用户 Union 上完成验证。"""
    target_id = "QQBot|Group|captcha-token-unbind-sender-target"
    kept_id = "QQBot|captcha-token-unbind-sender-kept"
    split_id = "QQBot|captcha-token-unbind-sender-split"
    target = await TargetUnionInfo.resolve_union(target_id)
    sender = await SenderUnionInfo.resolve_union(kept_id)
    if not await sender.bind_id(split_id):
        return False
    challenge = await CaptchaChallenge.create(
        challenge_id="captcha-token-unbind-sender-challenge",
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        target_id=target_id,
        sender_id=split_id,
        token="captcha-token-unbind-sender-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    token_session = await SessionInfo.assign(
        target_id="QQBot|C2C|captcha-token-unbind-sender",
        target_from="QQBot|C2C",
        client_name="QQBot",
        sender_id=split_id,
        sender_from="QQBot",
        is_private=True,
    )
    msg = MessageSession(session_info=token_session)
    origin = AsyncMock()
    result = {}

    async def unrestrict_member(_user_id, **_kwargs):
        result["split"] = await sender.unbind_id(split_id)
        return {"success": True}

    async def finish(_self, message=None, **_kwargs):
        result["finish"] = message.key if isinstance(message, I18NContextElement) else None
        raise SessionFinished

    origin.unrestrict_member.side_effect = unrestrict_member
    notify = AsyncMock()
    with (
        patch("modules.captcha.get_origin_session", new=AsyncMock(return_value=origin)),
        patch("modules.captcha.notify_origin", new=notify),
        patch.object(MessageSession, "finish", new=finish),
    ):
        try:
            await process_token(msg, challenge.token)
        except SessionFinished:
            pass

    split = result.get("split")
    await challenge.refresh_from_db()
    return bool(
        split
        and challenge.status == "verified"
        and challenge.sender_union_id == split.union_id
        and await CaptchaTrust.exists(
            trust_id=verification_id(target.union_id, split.union_id),
            target_union_id=target.union_id,
            sender_union_id=split.union_id,
        )
        and not await CaptchaTrust.exists(sender_union_id=sender.union_id)
        and result.get("finish") == "token.message.success"
        and notify.await_count == 1
    )


async def _test_target_unbind_during_token_moves_trust_to_current_union():
    """平台解禁等待期间场景解绑时，原 token 应在新场景 Union 上完成验证。"""
    kept_id = "QQBot|Group|captcha-token-unbind-target-kept"
    split_id = "QQBot|Group|captcha-token-unbind-target-split"
    sender_id = "QQBot|captcha-token-unbind-target-sender"
    target = await TargetUnionInfo.resolve_union(kept_id)
    if not await target.bind_id(split_id):
        return False
    sender = await SenderUnionInfo.resolve_union(sender_id)
    challenge = await CaptchaChallenge.create(
        challenge_id="captcha-token-unbind-target-challenge",
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        target_id=split_id,
        sender_id=sender_id,
        token="captcha-token-unbind-target-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    token_session = await SessionInfo.assign(
        target_id="QQBot|C2C|captcha-token-unbind-target",
        target_from="QQBot|C2C",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
        is_private=True,
    )
    msg = MessageSession(session_info=token_session)
    origin = AsyncMock()
    result = {}

    async def unrestrict_member(_user_id, **_kwargs):
        result["split"] = await target.unbind_id(split_id)
        return {"success": True}

    async def finish(_self, message=None, **_kwargs):
        result["finish"] = message.key if isinstance(message, I18NContextElement) else None
        raise SessionFinished

    origin.unrestrict_member.side_effect = unrestrict_member
    notify = AsyncMock()
    with (
        patch("modules.captcha.get_origin_session", new=AsyncMock(return_value=origin)),
        patch("modules.captcha.notify_origin", new=notify),
        patch.object(MessageSession, "finish", new=finish),
    ):
        try:
            await process_token(msg, challenge.token)
        except SessionFinished:
            pass

    split = result.get("split")
    await challenge.refresh_from_db()
    return bool(
        split
        and challenge.status == "verified"
        and challenge.target_union_id == split.union_id
        and await CaptchaTrust.exists(
            trust_id=verification_id(split.union_id, sender.union_id),
            target_union_id=split.union_id,
            sender_union_id=sender.union_id,
        )
        and not await CaptchaTrust.exists(target_union_id=target.union_id)
        and result.get("finish") == "token.message.success"
        and notify.await_count == 1
    )


async def _test_token_does_not_report_success_when_trust_fails():
    """平台已解禁但信任落库失败时，不得向两端发送完整成功提示。"""
    target_id = "QQBot|Group|captcha-token-trust-failed-target"
    sender_id = "QQBot|captcha-token-trust-failed-sender"
    session = await SessionInfo.assign(
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
    )
    challenge = await CaptchaChallenge.create(
        challenge_id="captcha-token-trust-failed-challenge",
        target_union_id=session.target_union_id,
        sender_union_id=session.sender_union_id,
        target_id=target_id,
        sender_id=sender_id,
        token="captcha-token-trust-failed-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    msg = MessageSession(session_info=session)
    origin = AsyncMock()
    origin.unrestrict_member.return_value = {"success": True}
    result = {}

    async def finish(_self, message=None, **_kwargs):
        result["finish"] = message.key if isinstance(message, I18NContextElement) else None
        raise SessionFinished

    notify = AsyncMock()
    with (
        patch("modules.captcha.get_origin_session", new=AsyncMock(return_value=origin)),
        patch("modules.captcha.trust_challenge", new=AsyncMock(return_value=False)),
        patch("modules.captcha.notify_origin", new=notify),
        patch.object(MessageSession, "finish", new=finish),
    ):
        try:
            await process_token(msg, challenge.token)
        except SessionFinished:
            pass

    await challenge.refresh_from_db()
    return (
        challenge.status == "pending"
        and result.get("finish") == "token.message.unavailable"
        and notify.await_count == 0
    )


async def _test_trust_challenge_rolls_back_partial_persistence():
    """Trust 已写入后 Challenge 更新失败时，两者必须一起回滚并返回明确失败。"""
    target = await TargetUnionInfo.resolve_union("QQBot|Group|captcha-trust-rollback-target")
    sender = await SenderUnionInfo.resolve_union("QQBot|captcha-trust-rollback-sender")
    challenge = await CaptchaChallenge.create(
        challenge_id="captcha-trust-rollback-challenge",
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        target_id="QQBot|Group|captcha-trust-rollback-target",
        sender_id="QQBot|captcha-trust-rollback-sender",
        token="captcha-trust-rollback-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    trust_id = verification_id(target.union_id, sender.union_id)

    with (
        patch.object(CaptchaChallenge, "save", new=AsyncMock(side_effect=RuntimeError("save failed"))),
        patch("modules.captcha.service.Logger.exception"),
    ):
        succeeded = await trust_challenge(challenge)

    fresh = await CaptchaChallenge.get(challenge_id=challenge.challenge_id)
    return (
        not succeeded
        and challenge.status == "pending"
        and fresh.status == "pending"
        and fresh.verified_at is None
        and not await CaptchaTrust.exists(trust_id=trust_id)
    )


async def _test_member_left_rolls_back_partial_cleanup():
    """Trust 删除异常时，先删掉的 Challenge 也必须回滚，便于之后安全重试。"""
    target_id = "QQBot|Group|captcha-member-left-rollback-target"
    sender_id = "QQBot|captcha-member-left-rollback-sender"
    event = await EventInfo.assign(
        event_name="member_left",
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
    )
    challenge = await CaptchaChallenge.create(
        challenge_id="captcha-member-left-rollback-challenge",
        target_union_id=event.target_union_id,
        sender_union_id=event.sender_union_id,
        target_id=target_id,
        sender_id=sender_id,
        token="captcha-member-left-rollback-token",
        answer=42,
        choices=[42],
        status="verified",
    )
    trust = await CaptchaTrust.create(
        trust_id=verification_id(event.target_union_id, event.sender_union_id),
        target_union_id=event.target_union_id,
        sender_union_id=event.sender_union_id,
    )

    class FailingDelete:
        def using_db(self, _connection):
            return self

        async def delete(self):
            raise RuntimeError("delete failed")

    with patch.object(CaptchaTrust, "filter", return_value=FailingDelete()):
        try:
            await member_left(event)
        except RuntimeError:
            pass
        else:
            return False

    return await CaptchaChallenge.exists(challenge_id=challenge.challenge_id) and await CaptchaTrust.exists(
        trust_id=trust.trust_id
    )


async def _test_member_left_waits_for_sender_unbind_and_cleans_current_challenge():
    """退群与用户解绑交错时，应等待迁移完成并清理新 Union 下的活跃挑战。"""
    target_id = "QQBot|Group|captcha-member-left-unbind-target"
    kept_id = "QQBot|captcha-member-left-unbind-kept"
    split_id = "QQBot|captcha-member-left-unbind-split"
    sender = await SenderUnionInfo.resolve_union(kept_id)
    if not await sender.bind_id(split_id):
        return False
    event = await EventInfo.assign(
        event_name="member_left",
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=split_id,
        sender_from="QQBot",
    )
    challenge = await CaptchaChallenge.create(
        challenge_id="captcha-member-left-unbind-challenge",
        target_union_id=event.target_union_id,
        sender_union_id=event.sender_union_id,
        target_id=target_id,
        sender_id=split_id,
        token="captcha-member-left-unbind-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    old_trust_id = verification_id(event.target_union_id, event.sender_union_id)
    await CaptchaTrust.create(
        trust_id=old_trust_id,
        target_union_id=event.target_union_id,
        sender_union_id=event.sender_union_id,
    )
    entered = asyncio.Event()
    release = asyncio.Event()
    original_handler = CaptchaChallenge.migrate_unbound_union_reference

    async def blocking_handler(cls, scope, platform_id, from_union, to_union):
        await original_handler(scope, platform_id, from_union, to_union)
        entered.set()
        await release.wait()

    with patch.object(
        CaptchaChallenge,
        "migrate_unbound_union_reference",
        new=classmethod(blocking_handler),
    ):
        unbind_task = asyncio.create_task(sender.unbind_id(split_id))
        await asyncio.wait_for(entered.wait(), timeout=2)
        left_task = asyncio.create_task(member_left(event))
        await asyncio.sleep(0)
        waited_for_unbind = not left_task.done()
        release.set()
        split, _ = await asyncio.gather(unbind_task, left_task)

    return bool(
        waited_for_unbind
        and split
        and event.sender_union_id == split.union_id
        and not await CaptchaChallenge.exists(challenge_id=challenge.challenge_id)
        and await CaptchaTrust.exists(trust_id=old_trust_id, sender_union_id=sender.union_id)
        and not await CaptchaTrust.exists(sender_union_id=split.union_id)
    )


@func_case
async def test_captcha(tester: Tester):
    """captcha：验证码生成、场景前缀、事件幂等及私聊解禁。"""
    await tester.test(_test_captcha_indexes_fit_mysql_limit, "验证码数据库索引兼容 MySQL 长度限制")
    await tester.test(_test_choices_are_valid, "验证码按钮选项范围与唯一性")
    await tester.test(_test_emote_choices_are_valid, "表情验证码选项与资源映射")
    await tester.test(_test_captcha_event_and_private_token, "入群事件、场景前缀与私聊 token 验证")
    await tester.test(_test_wrong_button_marks_challenge_failed, "错误按钮使验证失败")
    await tester.test(_test_preparing_challenge_resumes_after_restart, "重启后继续未完成的验证挑战")
    await tester.test(
        _test_delivery_failure_marks_error_after_successful_unrestrict,
        "验证码投递失败且解禁成功后标记普通错误",
    )
    await tester.test(
        _test_delivery_failure_keeps_active_status_when_unrestrict_fails,
        "验证码投递失败且解禁失败时保留活跃状态",
    )
    await tester.test(_test_emote_captcha_uses_localized_buttons, "表情验证码图片、机器人名称及按钮本地化")
    await tester.test(
        _test_emote_captcha_restores_markdown_after_send_error,
        "表情验证码发送异常恢复 Markdown 能力",
    )
    await tester.test(_test_member_left_removes_verification_records, "退群事件清除对应的验证记录")
    await tester.test(_test_sender_union_merge_migrates_captcha_references, "用户 Union 合并迁移验证码引用")
    await tester.test(_test_target_union_merge_migrates_captcha_references, "场景 Union 合并迁移验证码引用")
    await tester.test(_test_sender_unbind_moves_active_challenge_only, "用户 Union 解绑迁移活跃验证码引用")
    await tester.test(_test_target_unbind_moves_active_challenge_only, "场景 Union 解绑迁移活跃验证码引用")
    await tester.test(
        _test_sender_unbind_during_member_join_preserves_challenge_migration,
        "入群处理中用户解绑不回写旧 Union",
    )
    await tester.test(
        _test_target_unbind_during_member_join_preserves_challenge_migration,
        "入群处理中场景解绑不回写旧 Union",
    )
    await tester.test(
        _test_sender_unbind_during_token_moves_trust_to_current_union,
        "token 解禁期间用户解绑后信任写入新 Union",
    )
    await tester.test(
        _test_target_unbind_during_token_moves_trust_to_current_union,
        "token 解禁期间场景解绑后信任写入新 Union",
    )
    await tester.test(
        _test_token_does_not_report_success_when_trust_fails,
        "信任落库失败时 token 不伪报成功",
    )
    await tester.test(_test_trust_challenge_rolls_back_partial_persistence, "信任与挑战状态原子落库测试")
    await tester.test(_test_member_left_rolls_back_partial_cleanup, "退群验证记录原子清理测试")
    await tester.test(
        _test_member_left_waits_for_sender_unbind_and_cleans_current_challenge,
        "退群与用户解绑并发时清理当前挑战",
    )
    return tester
