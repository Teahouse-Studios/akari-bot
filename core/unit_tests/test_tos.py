import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from core.tos import (
    check_temp_ban,
    remove_temp_ban,
    abuse_warn_target,
    temp_ban_counter,
    TOS_TEMPBAN_TIME,
    tos_report,
)


@pytest.mark.asyncio
async def test_check_temp_ban_no_ban():
    target = "TEST|0"
    if target in temp_ban_counter:
        del temp_ban_counter[target]
    result = await check_temp_ban(target)
    assert result is False


@pytest.mark.asyncio
async def test_check_temp_ban_with_ban():
    target = "TEST|1"

    class Dummy:
        ts = time.time()
    temp_ban_counter[target] = Dummy()
    result = await check_temp_ban(target)
    assert 0 <= result <= TOS_TEMPBAN_TIME


@pytest.mark.asyncio
async def test_remove_temp_ban_removes_entry():
    target = "TEST|2"

    class Dummy:
        ts = time.time()
    temp_ban_counter[target] = Dummy()
    await remove_temp_ban(target)
    assert target not in temp_ban_counter


@pytest.mark.asyncio
@patch("core.tos.Bot")
@patch("core.tos.Logger")
@patch("core.tos.tos_report", new_callable=AsyncMock)
async def test_abuse_warn_target_warns_user(mock_tos_report, mock_logger, mock_bot):
    mock_sender_info = MagicMock()
    mock_sender_info.warns = 1
    mock_sender_info.trusted = False
    mock_sender_info.switch_identity = AsyncMock()
    mock_sender_info.warn_user = AsyncMock()

    mock_session_info = MagicMock()
    mock_session_info.sender_info = mock_sender_info
    mock_session_info.sender_id = "TEST|0"
    mock_session_info.target_id = "TEST|Console|0"

    mock_msg = MagicMock()
    mock_msg.session_info = mock_session_info
    mock_msg.send_message = AsyncMock()
    mock_msg.check_super_user.return_value = False

    await abuse_warn_target(mock_msg, reason="test reason")

    mock_sender_info.warn_user.assert_awaited()
    mock_msg.send_message.assert_awaited()
    mock_tos_report.assert_awaited()


@pytest.mark.asyncio
@patch("core.tos.Bot.fetch_target", new_callable=AsyncMock)
@patch("core.tos.Bot.send_direct_message", new_callable=AsyncMock)
async def test_tos_report_sends_messages(mock_send, mock_fetch):
    with patch("core.tos.report_targets", ["TEST|Console|0"]):
        mock_fetch.return_value = "target_object"
        await tos_report("TEST|0", "TEST|Console|0", "test reason", banned=True)
        mock_send.assert_awaited()
