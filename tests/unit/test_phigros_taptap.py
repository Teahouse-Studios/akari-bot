"""Phigros TapTap 扫码登录单元测试。"""

from urllib.parse import parse_qs

import httpx

from core.tester import func_case, Tester
from modules.phigros.libraries.taptap import (
    TapTapLogin,
    build_mac_authorization,
)


def _test_mac_authorization_matches_official_vector():
    """MAC 签名应包含查询参数，并与 TapTap 官方固定向量一致。"""
    authorization = build_mac_authorization(
        {
            "kid": "demo_kid",
            "mac_key": "demo_mac_key",
            "mac_algorithm": "hmac-sha-1",
        },
        url="https://open.tapapis.cn/account/basic-info/v1?client_id=demo_client_id",
        timestamp=1618221750,
        nonce="adssd",
    )
    return authorization == ('MAC id="demo_kid",ts="1618221750",nonce="adssd",mac="oYWjWxKzPBbeK2xKY7+ADJKAlmE="')


async def _test_device_login_flow():
    """设备码、待授权、资料和 Phigros 登录请求应首尾衔接。"""
    token_attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_attempts
        if request.url.path == "/oauth2/v1/device/code":
            form = parse_qs(request.content.decode())
            if form.get("scope") != ["public_profile"] or "device_id" not in form.get("info", [""])[0]:
                return httpx.Response(422, json={"error": "bad_device_request"})
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "device_code": "device-code",
                        "qrcode_url": "https://example.test/authorize",
                        "expires_in": 300,
                        "interval": 2,
                    },
                },
            )
        if request.url.path == "/oauth2/v1/token":
            token_attempts += 1
            if token_attempts == 1:
                return httpx.Response(400, json={"success": False, "data": {"error": "authorization_pending"}})
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "kid": "kid",
                        "mac_key": "key",
                        "mac_algorithm": "hmac-sha-1",
                        "scope": ["public_profile"],
                    },
                },
            )
        if request.url.path == "/account/profile/v1":
            if not request.headers.get("Authorization", "").startswith('MAC id="kid"'):
                return httpx.Response(401, json={"error": "bad_signature"})
            return httpx.Response(200, json={"success": True, "data": {"name": "Test", "openid": "openid"}})
        if request.url.path == "/1.1/users":
            payload = request.read().decode()
            if "authData" not in payload or "openid" not in payload or not request.headers.get("X-LC-Sign"):
                return httpx.Response(422, json={"error": "bad_cloud_request"})
            return httpx.Response(200, json={"sessionToken": "a" * 25})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        login = TapTapLogin(client)
        qrcode_data = await login.request_login_qrcode()
        pending = await login.check_qrcode_result(qrcode_data)
        access_token = await login.check_qrcode_result(qrcode_data)
        profile = await login.get_profile(access_token)
        user_data = await login.get_user_data(access_token, profile)

    return (
        pending is None and token_attempts == 2 and profile["name"] == "Test" and user_data["sessionToken"] == "a" * 25
    )


@func_case
async def test_phigros_taptap(tester: Tester):
    """phigros: TapTap 扫码登录"""
    await tester.test(_test_mac_authorization_matches_official_vector, "TapTap MAC 官方向量")
    await tester.test(_test_device_login_flow, "TapTap 设备码登录请求链路")
    return tester
