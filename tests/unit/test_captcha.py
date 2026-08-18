"""QQBot 入群验证码模块单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.message.elements import ButtonFrameElement, I18NContextElement, ImageElement
from core.builtins.session.features import Features
from core.builtins.session.info import EventInfo, SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.utils import command_prefix
from core.constants.exceptions import SessionFinished
from core.database.models import TargetUnionInfo
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
from modules.captcha.service import verification_id

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


async def _test_emote_captcha_uses_localized_buttons():
    target_id = "QQBot|Group|captcha_emote"
    sender_id = "QQBot|captcha_emote_user"
    session = await SessionInfo.assign(
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
        features=Features(support_button=True, support_image=True, read_all_messages=True),
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
    challenge_id = verification_id(event.target_union_id, event.sender_union_id)
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
        trust_id=challenge_id,
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
    await tester.test(_test_emote_captcha_uses_localized_buttons, "表情验证码图片、机器人名称及按钮本地化")
    await tester.test(_test_member_left_removes_verification_records, "退群事件清除对应的验证记录")
    return tester
