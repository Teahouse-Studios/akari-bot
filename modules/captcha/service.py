import hashlib
from datetime import UTC, datetime

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Mention
from core.utils.random import SecureRandom
from modules.captcha.database.models import CaptchaChallenge, CaptchaTrust


def verification_id(target_union_id: str, sender_union_id: str) -> str:
    """为一个场景与用户组合生成稳定主键。"""
    return hashlib.sha256(f"{target_union_id}\0{sender_union_id}".encode()).hexdigest()


async def get_origin_session(challenge: CaptchaChallenge):
    fetched = await Bot.fetch_target(challenge.target_id, sender_id=challenge.sender_id, create=False)
    if not fetched:
        return None
    return await Bot.FetchedMessageSession.from_session_info(fetched)


async def notify_origin(challenge: CaptchaChallenge, message_key: str) -> None:
    session = await get_origin_session(challenge)
    if session:
        await session.send_message([Mention(challenge.sender_id), I18NContext(message_key)], quote=False)


async def trust_challenge(challenge: CaptchaChallenge) -> None:
    await CaptchaTrust.get_or_create(
        trust_id=verification_id(challenge.target_union_id, challenge.sender_union_id),
        defaults={
            "target_union_id": challenge.target_union_id,
            "sender_union_id": challenge.sender_union_id,
        },
    )
    challenge.status = "verified"
    challenge.verified_at = datetime.now(UTC)
    await challenge.save()


def new_token() -> str:
    return SecureRandom.token_urlsafe(18)


__all__ = [
    "get_origin_session",
    "new_token",
    "notify_origin",
    "trust_challenge",
    "verification_id",
]
