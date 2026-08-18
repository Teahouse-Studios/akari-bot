from secrets import SystemRandom

from core.builtins.bot import Bot
from core.builtins.message.internal import ButtonFrame, I18NContext, Image, Mention
from core.builtins.session.info import EventInfo
from core.builtins.utils import command_prefix
from core.component import module
from core.config.base import CoreConfig
from core.constants.path import assets_path
from core.logger import Logger
from core.utils.button import arrange_buttons
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
_random = SystemRandom()

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
        choices.add(_random.randint(1, 100))
    values = list(choices)
    _random.shuffle(values)
    return values


def make_emote_choices(answer: int) -> list[int]:
    """生成包含答案的 20 个不重复表情资源编号。"""
    if len(CAPTCHA_EMOTES) < CAPTCHA_CHOICE_COUNT:
        raise ValueError(f"At least {CAPTCHA_CHOICE_COUNT} captcha emotes are required.")
    choices = {answer}
    maximum = CAPTCHA_EMOTE_ANSWER_OFFSET + len(CAPTCHA_EMOTES) - 1
    while len(choices) < CAPTCHA_CHOICE_COUNT:
        choices.add(_random.randint(CAPTCHA_EMOTE_ANSWER_OFFSET, maximum))
    values = list(choices)
    _random.shuffle(values)
    return values


def captcha_emote_name(answer: int) -> str | None:
    index = answer - CAPTCHA_EMOTE_ANSWER_OFFSET
    if 0 <= index < len(CAPTCHA_EMOTES):
        return CAPTCHA_EMOTES[index]
    return None


@captcha.event("member_left", available_for="QQBot|Group")
async def member_left(event: EventInfo):
    challenge_id = verification_id(event.target_union_id, event.sender_union_id)
    await CaptchaChallenge.filter(challenge_id=challenge_id).delete()
    await CaptchaTrust.filter(trust_id=challenge_id).delete()


@captcha.event("member_joined", available_for="QQBot|Group")
async def member_joined(event: EventInfo):
    challenge_id = verification_id(event.target_union_id, event.sender_union_id)

    if await CaptchaTrust.exists(trust_id=challenge_id):
        return

    existing = await CaptchaChallenge.get_or_none(challenge_id=challenge_id)
    if existing and existing.status in {"pending", "failed", "verified"}:
        return

    if CoreConfig.use_emote and len(CAPTCHA_EMOTES) >= CAPTCHA_CHOICE_COUNT:
        answer = CAPTCHA_EMOTE_ANSWER_OFFSET + _random.randint(0, len(CAPTCHA_EMOTES) - 1)
        choices = make_emote_choices(answer)
    else:
        if CoreConfig.use_emote:
            Logger.warning(
                f"Captcha emote mode requires at least {CAPTCHA_CHOICE_COUNT} GIF resources in {CAPTCHA_EMOTE_DIR}."
            )
        answer = _random.randint(1, 100)
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
    }
    if existing and existing.status == "preparing":
        challenge = existing
        if len(challenge.choices) != CAPTCHA_CHOICE_COUNT:
            if captcha_emote_name(challenge.answer) and len(CAPTCHA_EMOTES) >= CAPTCHA_CHOICE_COUNT:
                challenge.choices = make_emote_choices(challenge.answer)
            else:
                if captcha_emote_name(challenge.answer):
                    challenge.answer = _random.randint(1, 100)
                challenge.choices = make_choices(challenge.answer)
            await challenge.save()
    elif existing:
        for key, value in defaults.items():
            setattr(existing, key, value)
        challenge = existing
        await challenge.save()
    else:
        challenge, created = await CaptchaChallenge.get_or_create(challenge_id=challenge_id, defaults=defaults)
        if not created:
            return

    fetched = await Bot.fetch_target(event.target_id, sender_id=event.sender_id, create=False)
    if not fetched:
        challenge.status = "error"
        await challenge.save()
        return

    session = await Bot.FetchedMessageSession.from_session_info(fetched)
    restrict_result = await session.restrict_member(event.sender_id, CAPTCHA_MUTE_SECONDS, wait=True)
    if not restrict_result or not restrict_result.get("success"):
        challenge.status = "error"
        await challenge.save()
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
        session.session_info.support_markdown = False
        image_sent = await session.send_message(Image(CAPTCHA_EMOTE_DIR / f"{emote_name}.gif"), quote=False)
        session.session_info.support_markdown = True
        if not image_sent.message_id:
            Logger.warning(f"Failed to send verification emote in {event.target_id}.")
            challenge.status = "error"
            await challenge.save()
            await session.unrestrict_member(event.sender_id, wait=True)
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
        await challenge.save()
        return

    Logger.warning(f"Failed to send verification challenge in {event.target_id}.")
    challenge.status = "error"
    await challenge.save()
    await session.unrestrict_member(event.sender_id, wait=True)


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
        challenge.status = "failed"
        await challenge.save()
        await notify_origin(challenge, "captcha.message.failed")
        await msg.finish(I18NContext("token.message.incorrect"))

    origin = await get_origin_session(challenge)
    if not origin:
        await msg.finish(I18NContext("token.message.unavailable"))
    unrestrict_result = await origin.unrestrict_member(challenge.sender_id, wait=True)
    if not unrestrict_result or not unrestrict_result.get("success"):
        await msg.finish(I18NContext("token.message.unrestrict_failed"))

    await trust_challenge(challenge)
    if msg.session_info.target_id != challenge.target_id:
        await notify_origin(challenge, "captcha.message.success")
    await msg.finish(I18NContext("token.message.success"))
