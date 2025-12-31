from unittest.mock import AsyncMock, patch

import pytest

from core.utils.petal import gained_petal, lost_petal, cost_petal, sign_get_petal


class FakeSenderInfo:
    def __init__(self):
        self.modify_petal = AsyncMock()


class MockSessionInfo:
    def __init__(self, sender_id="TEST|0", petal=10):
        self.sender_id = sender_id
        self.petal = petal
        self.client_name = "TEST"
        self.sender_info = FakeSenderInfo()


class MockMessageSession:
    def __init__(self, sender_id="TEST|0", petal=10):
        self.session_info = MockSessionInfo(sender_id, petal)
        self.send_message = AsyncMock()


@pytest.fixture(autouse=True)
def mock_config():
    with patch("core.utils.petal.Config") as mock_conf:
        mock_conf.side_effect = lambda key, default=None: {
            "enable_petal": True,
            "enable_get_petal": True,
            "petal_gained_limit": 5,
            "petal_lost_limit": 5,
            "petal_sign_limit": 5,
            "petal_sign_rate": 0.5,
        }.get(key, default)
        yield mock_conf


@pytest.fixture(autouse=True)
def mock_storage():
    initial_storage = {"TEST|0": {"time": 0, "expired": 0, "amount": 0}}
    with patch("core.utils.petal.get_stored_list", AsyncMock(return_value=[initial_storage])) as gsl, \
            patch("core.utils.petal.update_stored_list", AsyncMock()) as usl:
        yield gsl, usl


@pytest.mark.asyncio
async def test_gained_petal_new_user(mock_storage):
    msg = MockMessageSession()
    result = await gained_petal(msg, 3)
    assert result is not None
    assert "success" in result.key
    msg.session_info.sender_info.modify_petal.assert_awaited_with(3)


@pytest.mark.asyncio
async def test_gained_petal_limit(mock_storage):
    msg = MockMessageSession()
    result = await gained_petal(msg, 10)
    assert result is not None
    assert "success" in result.key
    msg.session_info.sender_info.modify_petal.assert_awaited_with(5)


@pytest.mark.asyncio
async def test_lost_petal_new_user(mock_storage):
    msg = MockMessageSession()
    result = await lost_petal(msg, 3)
    assert result is not None
    assert "success" in result.key
    msg.session_info.sender_info.modify_petal.assert_awaited_with(-3)


@pytest.mark.asyncio
async def test_cost_petal_success():
    msg = MockMessageSession(petal=10)
    success = await cost_petal(msg, 5)
    assert success is True
    msg.session_info.sender_info.modify_petal.assert_awaited_with(-5)


@pytest.mark.asyncio
async def test_cost_petal_fail():
    msg = MockMessageSession(petal=3)
    success = await cost_petal(msg, 5)
    assert success is False
    msg.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_sign_get_petal(mock_storage):
    msg = MockMessageSession()
    amount = await sign_get_petal(msg)
    assert isinstance(amount, int)
    if amount > 0:
        msg.session_info.sender_info.modify_petal.assert_awaited_with(amount)
