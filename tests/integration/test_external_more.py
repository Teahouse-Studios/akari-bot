"""更多外部模块集成测试 - tweet。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_tweet_not_found(tester: Tester):
    """tweet 模块测试 - 不存在的推文"""
    await tester.expect("~tweet 1", Contains("推文"), "tweet 不存在的推文应提示")
    return tester
