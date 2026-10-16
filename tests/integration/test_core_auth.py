"""modules/core 模块授权命令集成测试。"""

from unittest.mock import patch

from core.tester import (
    func_case,
    Tester,
    ActionContains,
    All,
    Contains,
    Not,
)

STRICT_CONFIRM_TOKEN = "A1B2C3"


@func_case
async def test_auth_add_strict_confirmation(tester: Tester):
    """auth add 的高危操作严格确认流程测试"""
    with (
        patch("core.builtins.session.internal.generate_strict_confirm_token", return_value=STRICT_CONFIRM_TOKEN),
        # 测试进程没有平台 Peer，ID 归属校验由 mock 提供
        patch("modules.core.su_tools.auth.Alive.determine_sender_from", return_value="TEST"),
    ):
        await tester.integrate(
            ["~auth add TEST|999 auth", "是", STRICT_CONFIRM_TOKEN],
            All(Contains("成功授权"), ActionContains(STRICT_CONFIRM_TOKEN)),
            "auth add 应展示口令并提示授权结果",
        )
        await tester.integrate("~auth list TEST|999", Contains("授权使用模块"), "auth list 应包含新授权")
        await tester.integrate(["~auth remove TEST|999 auth"], Contains("已取消"), "auth remove 应提示取消结果")
    return tester


@func_case
async def test_auth_add_rejects_wrong_confirmation(tester: Tester):
    """auth add 未完全回复口令时不应授权"""
    with (
        patch("core.builtins.session.internal.generate_strict_confirm_token", return_value=STRICT_CONFIRM_TOKEN),
        patch("modules.core.su_tools.auth.Alive.determine_sender_from", return_value="TEST"),
    ):
        await tester.integrate(
            ["~auth add TEST|998 auth", "是", "确认"],
            All(ActionContains(STRICT_CONFIRM_TOKEN), Not(Contains("成功授权"))),
            "口令不符时不应提示授权结果",
        )
        await tester.integrate("~auth list TEST|998", Contains("暂无任何授权记录"), "auth list 应无授权记录")
    return tester
