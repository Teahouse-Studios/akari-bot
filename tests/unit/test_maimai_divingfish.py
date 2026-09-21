"""水鱼（Diving-Fish）OAuth 的纯逻辑单元测试：客户端形态判定、绑定落盘、取令牌与撤销。"""

from unittest.mock import patch

from core.tester import Tester, func_case
from modules.maimai.database.models import DivingProberBindInfo
from modules.maimai.libraries import divingfish_oauth
from modules.maimai.libraries.divingfish_oauth import (
    DivingFishAuthorizationDenied,
    DivingFishConsentRequired,
    DivingFishDeviceCodeExpired,
    DivingFishOAuthError,
    DivingFishRateLimited,
    DivingFishSlowDown,
    DivingFishTokenRevoked,
    diving_fish_bind_usable,
    exchange_on_behalf_of,
    get_access_token,
    poll_device_token,
    refresh_access_token,
    store_binding,
    unbind_account,
)


class _SessionInfo:
    def __init__(self, union_id: str):
        self.sender_union_id = union_id


class _MessageSession:
    def __init__(self, union_id: str):
        self.session_info = _SessionInfo(union_id)
        self.finished = False

    async def send_message(self, *args, **kwargs):
        raise AssertionError("Pure logic should not send messages.")

    async def finish(self, *args, **kwargs):
        self.finished = True


def _recorder(*responses):
    calls = []

    async def fake_post(url, payload, *, attempt=3, expect_json=True):
        calls.append((url, payload, attempt, expect_json))
        return responses[min(len(calls), len(responses)) - 1]

    return fake_post, calls


async def _test_authenticated_follows_client_form():
    with patch.object(divingfish_oauth, "DF_CONFIDENTIAL_CLIENT", False):
        public = divingfish_oauth._authenticated({"client_id": "app-id"})
    with (
        patch.object(divingfish_oauth, "DF_CONFIDENTIAL_CLIENT", True),
        patch.object(divingfish_oauth, "DF_CLIENT_SECRET", "app-secret"),
    ):
        confidential = divingfish_oauth._authenticated({"client_id": "app-id"})
    return public == {"client_id": "app-id"} and confidential == {
        "client_id": "app-id",
        "client_secret": "app-secret",
    }


async def _test_bind_usable_follows_client_form():
    public_bind = DivingProberBindInfo(union_id="u", refresh_token="refresh-token", subject=None)
    confidential_bind = DivingProberBindInfo(union_id="u", refresh_token=None, subject="12345")
    legacy_bind = DivingProberBindInfo(union_id="u", refresh_token="refresh-token", subject="12345")
    return (
        diving_fish_bind_usable(public_bind, False)
        and not diving_fish_bind_usable(confidential_bind, False)
        and diving_fish_bind_usable(confidential_bind, True)
        and diving_fish_bind_usable(legacy_bind, False)
        and diving_fish_bind_usable(legacy_bind, True)
        and not diving_fish_bind_usable(None, False)
        and not diving_fish_bind_usable(None, True)
    )


async def _test_store_binding_follows_client_form():
    stored = []

    async def fake_set(**kwargs):
        stored.append(kwargs)
        return True

    with (
        patch.object(DivingProberBindInfo, "set_bind_info", fake_set),
        patch.object(divingfish_oauth, "DF_CONFIDENTIAL_CLIENT", True),
    ):
        confidential = await store_binding("union-a", {"access_token": "at", "sub": "12345"})
        confidential_missing = await store_binding("union-a", {"access_token": "at"})
    with (
        patch.object(DivingProberBindInfo, "set_bind_info", fake_set),
        patch.object(divingfish_oauth, "DF_CONFIDENTIAL_CLIENT", False),
    ):
        public = await store_binding("union-b", {"access_token": "at", "refresh_token": "rt", "sub": "12345"})
        public_missing = await store_binding("union-b", {"access_token": "at"})

    return (
        confidential
        and not confidential_missing
        and public
        and not public_missing
        and stored
        == [
            {"union_id": "union-a", "username": "", "refresh_token": "", "subject": "12345"},
            {"union_id": "union-b", "username": "", "refresh_token": "rt", "subject": "12345"},
        ]
    )


async def _test_device_poll_follows_client_form():
    with (
        patch.object(divingfish_oauth, "DF_CONFIDENTIAL_CLIENT", True),
        patch.object(divingfish_oauth, "DF_CLIENT_SECRET", "app-secret"),
    ):
        fake, confidential_calls = _recorder({"access_token": "at", "sub": "12345"})
        with patch.object(divingfish_oauth, "_post_form", fake):
            confidential = await poll_device_token("device-code")
        fake, _ = _recorder({"access_token": "at"})
        with patch.object(divingfish_oauth, "_post_form", fake):
            try:
                await poll_device_token("device-code")
            except DivingFishOAuthError:
                confidential_rejected = True
            else:
                confidential_rejected = False

    with (
        patch.object(divingfish_oauth, "DF_CONFIDENTIAL_CLIENT", False),
        patch.object(divingfish_oauth, "DF_CLIENT_SECRET", ""),
    ):
        fake, public_calls = _recorder({"access_token": "at", "refresh_token": "rt", "sub": "12345"})
        with patch.object(divingfish_oauth, "_post_form", fake):
            public = await poll_device_token("device-code")
        fake, _ = _recorder({"access_token": "at", "sub": "12345"})
        with patch.object(divingfish_oauth, "_post_form", fake):
            try:
                await poll_device_token("device-code")
            except DivingFishOAuthError:
                public_rejected = True
            else:
                public_rejected = False

    url, confidential_payload, attempt, _ = confidential_calls[0]
    return (
        confidential["sub"] == "12345"
        and confidential_rejected
        and public["refresh_token"] == "rt"
        and public_rejected
        and url == divingfish_oauth.DF_TOKEN_URL
        and confidential_payload["grant_type"] == "urn:ietf:params:oauth:grant-type:device_code"
        and confidential_payload["client_secret"] == "app-secret"
        and "client_secret" not in public_calls[0][1]
        # 设备码只能换取一次，重发可能把第一次已签发的令牌扫掉，故不重试。
        and attempt == 1
    )


async def _test_device_poll_error_mapping():
    results = {}
    for error in ("authorization_pending", "slow_down", "access_denied", "expired_token", "invalid_client"):
        fake, _ = _recorder({"error": error})
        with patch.object(divingfish_oauth, "_post_form", fake):
            try:
                results[error] = await poll_device_token("device-code")
            except Exception as e:
                results[error] = e
    return (
        results["authorization_pending"] is None
        and isinstance(results["slow_down"], DivingFishSlowDown)
        and isinstance(results["access_denied"], DivingFishAuthorizationDenied)
        and isinstance(results["expired_token"], DivingFishDeviceCodeExpired)
        and type(results["invalid_client"]) is DivingFishOAuthError
    )


async def _test_exchange_on_behalf_of_request():
    with (
        patch.object(divingfish_oauth, "DF_CONFIDENTIAL_CLIENT", True),
        patch.object(divingfish_oauth, "DF_CLIENT_SECRET", "app-secret"),
    ):
        fake, calls = _recorder({"access_token": "at", "expires_in": 300, "scope": "prober.records.read"})
        with patch.object(divingfish_oauth, "_post_form", fake):
            resp = await exchange_on_behalf_of("sub:12345")

    url, payload, attempt, _ = calls[0]
    return (
        resp["access_token"] == "at"
        and url == divingfish_oauth.DF_TOKEN_URL
        and payload["grant_type"] == "urn:diving-fish:params:oauth:grant-type:on-behalf-of"
        and payload["client_id"] == divingfish_oauth.DF_CLIENT_ID
        and payload["client_secret"] == "app-secret"
        and payload["subject"] == "sub:12345"
        and "scope" not in payload
        and attempt == 1
    )


async def _test_exchange_error_mapping():

    async def _exchange_with(response: dict):
        fake, _ = _recorder(response)
        with patch.object(divingfish_oauth, "_post_form", fake):
            try:
                await exchange_on_behalf_of("sub:12345")
            except Exception as e:
                return e
        return None

    with patch.object(divingfish_oauth, "DF_CONFIDENTIAL_CLIENT", True):
        consent = await _exchange_with({"error": "consent_required", "error_description": "scope not granted"})
        rate_limited = await _exchange_with({"error": "slow_down"})
        invalid = await _exchange_with({"error": "invalid_client", "error_description": "unknown client"})
        no_token = await _exchange_with({})
    return (
        isinstance(consent, DivingFishConsentRequired)
        and isinstance(consent, DivingFishTokenRevoked)
        and str(consent) == "Consent required: scope not granted"
        and isinstance(rate_limited, DivingFishRateLimited)
        and str(rate_limited).startswith("429")
        and type(invalid) is DivingFishOAuthError
        and type(no_token) is DivingFishOAuthError
    )


async def _test_get_access_token_confidential():
    bind = DivingProberBindInfo(union_id="confidential-union", refresh_token=None, subject="12345")
    subjectless = DivingProberBindInfo(union_id="confidential-union-empty", refresh_token=None, subject=None)
    exchanges = []
    persisted = []

    async def fake_exchange(subject):
        exchanges.append(subject)
        return {"access_token": f"token-{len(exchanges)}", "expires_in": 300}

    async def fake_update(union_id, refresh_token, subject=None):
        persisted.append((union_id, refresh_token, subject))

    divingfish_oauth.drop_access_token(bind.union_id)
    with (
        patch.object(divingfish_oauth, "DF_CONFIDENTIAL_CLIENT", True),
        patch.object(divingfish_oauth, "exchange_on_behalf_of", fake_exchange),
        patch.object(DivingProberBindInfo, "update_refresh_token", fake_update),
    ):
        first = await get_access_token(bind)
        second = await get_access_token(bind)
    divingfish_oauth.drop_access_token(bind.union_id)

    with patch.object(divingfish_oauth, "DF_CONFIDENTIAL_CLIENT", True):
        try:
            await get_access_token(subjectless)
        except DivingFishTokenRevoked:
            rejected = True
        else:
            rejected = False

    return first == "token-1" and second == "token-1" and exchanges == ["sub:12345"] and not persisted and rejected


async def _test_get_access_token_public_rotation():
    bind = DivingProberBindInfo(union_id="public-union", refresh_token="old-token", subject=None)
    tokenless = DivingProberBindInfo(union_id="public-union-empty", refresh_token=None, subject="12345")
    refreshed = []
    persisted = []

    async def fake_refresh(refresh_token):
        refreshed.append(refresh_token)
        return {"access_token": "access-1", "refresh_token": "new-token", "expires_in": 900, "sub": "12345"}

    async def fake_update(union_id, refresh_token, subject=None):
        persisted.append((union_id, refresh_token, subject))

    divingfish_oauth.drop_access_token(bind.union_id)
    with (
        patch.object(divingfish_oauth, "DF_CONFIDENTIAL_CLIENT", False),
        patch.object(divingfish_oauth, "refresh_access_token", fake_refresh),
        patch.object(DivingProberBindInfo, "update_refresh_token", fake_update),
    ):
        first = await get_access_token(bind)
        second = await get_access_token(bind)
    divingfish_oauth.drop_access_token(bind.union_id)

    with patch.object(divingfish_oauth, "DF_CONFIDENTIAL_CLIENT", False):
        try:
            await get_access_token(tokenless)
        except DivingFishTokenRevoked:
            rejected = True
        else:
            rejected = False

    return (
        first == "access-1"
        and second == "access-1"
        and refreshed == ["old-token"]
        and persisted == [("public-union", "new-token", "12345")]
        and bind.refresh_token == "new-token"
        and rejected
    )


async def _test_refresh_error_mapping():

    async def _refresh_with(response: dict):
        fake, calls = _recorder(response)
        with patch.object(divingfish_oauth, "_post_form", fake):
            try:
                await refresh_access_token("old-token")
            except Exception as e:
                return e, calls[0][1]
        return None, calls[0][1]

    revoked, revoked_payload = await _refresh_with({"error": "invalid_grant"})
    failed, _ = await _refresh_with({"error": "invalid_client"})
    return (
        type(revoked) is DivingFishTokenRevoked
        and revoked_payload["grant_type"] == "refresh_token"
        and revoked_payload["refresh_token"] == "old-token"
        and type(failed) is DivingFishOAuthError
    )


async def _test_unbind_revokes_available_token():
    holder = {}
    revoked = []
    removed = []

    async def fake_get(msg, create=True):
        return holder["bind"]

    async def fake_remove(union_id):
        removed.append(union_id)
        return True

    async def fake_revoke(token, token_type_hint="refresh_token"):
        revoked.append((token, token_type_hint))

    async def failing_revoke(token, token_type_hint="refresh_token"):
        raise DivingFishOAuthError("revoke failed")

    with (
        patch.object(DivingProberBindInfo, "get_by_sender_id", fake_get),
        patch.object(DivingProberBindInfo, "remove_bind_info", fake_remove),
        patch.object(divingfish_oauth, "revoke_token", fake_revoke),
    ):
        holder["bind"] = DivingProberBindInfo(union_id="public-union", refresh_token="rt", subject=None)
        public_msg = _MessageSession("public-union")
        await unbind_account(public_msg)

        holder["bind"] = DivingProberBindInfo(union_id="confidential-union", refresh_token=None, subject="12345")
        divingfish_oauth._cache_token("confidential-union", "cached-token", 600)
        confidential_msg = _MessageSession("confidential-union")
        await unbind_account(confidential_msg)
        confidential_cached = divingfish_oauth._cached_access_token("confidential-union")

        holder["bind"] = None
        stranger_msg = _MessageSession("stranger")
        await unbind_account(stranger_msg)

        # 撤销失败也要删掉本地记录：否则用户会卡在「已解绑却仍显示已绑定」的状态里。
        holder["bind"] = DivingProberBindInfo(union_id="failing-union", refresh_token="rt", subject=None)
        with patch.object(divingfish_oauth, "revoke_token", failing_revoke):
            failing_msg = _MessageSession("failing-union")
            await unbind_account(failing_msg)

    return (
        revoked == [("rt", "refresh_token"), ("cached-token", "access_token")]
        and removed == ["public-union", "confidential-union", "stranger", "failing-union"]
        and confidential_cached is None
        and public_msg.finished
        and confidential_msg.finished
        and stranger_msg.finished
        and failing_msg.finished
    )


@func_case
async def test_maimai_divingfish(tester: Tester):
    await tester.test(_test_authenticated_follows_client_form, "客户端凭据随登记形态增减")
    await tester.test(_test_bind_usable_follows_client_form, "绑定记录可用性判定")
    await tester.test(_test_store_binding_follows_client_form, "绑定落盘内容随形态变化")
    await tester.test(_test_device_poll_follows_client_form, "设备码轮询结果按形态校验")
    await tester.test(_test_device_poll_error_mapping, "设备码轮询错误分流")
    await tester.test(_test_exchange_on_behalf_of_request, "换票请求参数")
    await tester.test(_test_exchange_error_mapping, "换票错误分流")
    await tester.test(_test_get_access_token_confidential, "机密客户端换票与缓存")
    await tester.test(_test_get_access_token_public_rotation, "公开客户端刷新与令牌轮换落盘")
    await tester.test(_test_refresh_error_mapping, "刷新错误分流")
    await tester.test(_test_unbind_revokes_available_token, "解绑撤销与记录删除")
    return tester
