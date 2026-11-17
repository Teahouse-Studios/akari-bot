import hashlib
from datetime import UTC, datetime

from tortoise.transactions import in_transaction

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Mention
from core.database.models import SenderUnionInfo, TargetUnionInfo, union_mutation
from core.logger import Logger
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


async def trust_challenge(challenge: CaptchaChallenge) -> bool:
    try:
        async with union_mutation():
            # 平台解禁等待期间账号或场景可能解绑。锁内按平台 ID 重解析并重新读取挑战，
            # 避免旧 ORM 实例把信任写给旧 Union，或用整行 save 撤销解绑 hook 的改挂。
            # Trust 与 Challenge 状态必须属于同一事务；否则后一步失败会留下“已信任但仍待验证”的半状态。
            async with in_transaction("default"):
                fresh = await CaptchaChallenge.get_or_none(challenge_id=challenge.challenge_id)
                if not fresh or fresh.status != "pending":
                    return False
                # 事务内复用的是同一数据库连接，查询必须串行执行，不能用 gather 并发占用连接。
                target = await TargetUnionInfo.resolve_union(fresh.target_id, create=False)
                sender = await SenderUnionInfo.resolve_union(fresh.sender_id, create=False)
                if not target or not sender:
                    return False

                fresh.target_union_id = target.union_id
                fresh.sender_union_id = sender.union_id
                await CaptchaTrust.get_or_create(
                    trust_id=verification_id(target.union_id, sender.union_id),
                    defaults={
                        "target_union_id": target.union_id,
                        "sender_union_id": sender.union_id,
                    },
                )
                fresh.status = "verified"
                fresh.verified_at = datetime.now(UTC)
                await fresh.save(update_fields=["target_union_id", "sender_union_id", "status", "verified_at"])

        # 只在事务成功提交后更新调用方持有的旧实例；提交失败时它仍应反映可重试的原状态。
        challenge.target_union_id = fresh.target_union_id
        challenge.sender_union_id = fresh.sender_union_id
        challenge.status = fresh.status
        challenge.verified_at = fresh.verified_at
        return True
    except Exception:
        Logger.exception(f"Failed to persist captcha trust for {challenge.challenge_id}: ")
        return False


def new_token() -> str:
    return SecureRandom.token_urlsafe(18)


__all__ = [
    "get_origin_session",
    "new_token",
    "notify_origin",
    "trust_challenge",
    "verification_id",
]
