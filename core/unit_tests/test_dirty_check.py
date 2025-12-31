from unittest.mock import AsyncMock

import pytest

from core.dirty_check import parse_data, check, check_bool


class DummyI18N:
    def __init__(self, key, reason=None):
        self.key = key
        self.reason = reason

    def __str__(self):
        return f"<REDACTED:{self.reason}>"


@pytest.mark.parametrize("confidence,expected_status", [
    (50, False),
    (100, True),
])
def test_parse_data_textscan_v1(monkeypatch, confidence, expected_status):
    monkeypatch.setattr("core.dirty_check.use_textscan_v1", True)
    monkeypatch.setattr("core.dirty_check.I18NContext", DummyI18N)

    original_content = "There is bad word"
    result = {
        "results": [
            {
                "rate": 80,
                "suggestion": "block",
                "details": [
                    {
                        "label": "abuse",
                        "contexts": [
                            {
                                "positions": [{"startPos": 8, "endPos": 11}]
                            }
                        ]
                    }
                ]
            }
        ]
    }

    output = parse_data(original_content, result, confidence)
    assert "content" in output
    assert "status" in output
    assert output["status"] == expected_status
    if not expected_status:
        assert "<REDACTED:abuse>" in output["content"]


@pytest.mark.parametrize("confidence,expected_status", [
    (50, False),
    (100, True),
])
def test_parse_data_textscan_v2(monkeypatch, confidence, expected_status):
    monkeypatch.setattr("core.dirty_check.use_textscan_v1", False)
    monkeypatch.setattr("core.dirty_check.I18NContext", DummyI18N)

    original_content = "There is bad word"
    result = {
        "RiskLevel": "high",
        "Result": [
            {
                "Confidence": 80,
                "Label": "abuse",
                "RiskWords": "bad"
            }
        ]
    }

    output = parse_data(original_content, result, confidence)
    assert output["status"] == expected_status
    if not expected_status:
        assert "<REDACTED:abuse>" in output["content"]


def test_parse_data_preserve_i18n(monkeypatch):
    monkeypatch.setattr("core.dirty_check.use_textscan_v1", False)
    monkeypatch.setattr("core.dirty_check.I18NContext", DummyI18N)

    original_content = "There is {I18N:bad} word"
    result = {
        "RiskLevel": "high",
        "Result": [
            {
                "Confidence": 80,
                "Label": "abuse",
                "RiskWords": "bad"
            }
        ]
    }

    output = parse_data(original_content, result, confidence=50)
    assert "{I18N:bad}" in output["content"]


def test_parse_data_additional_text(monkeypatch):
    monkeypatch.setattr("core.dirty_check.use_textscan_v1", False)

    original_content = "safe content"
    additional = " additional"
    result = {"RiskLevel": "low", "Result": []}

    output = parse_data(original_content, result, confidence=50, additional_text=additional)
    assert additional in output["content"]


@pytest.mark.asyncio
async def test_check_with_empty_text():
    result = await check("")
    assert result == [{"content": "", "status": True, "original": ""}]


@pytest.mark.asyncio
async def test_check_with_str_and_disabled_filter():
    mock_session = AsyncMock()
    mock_session.session_info.require_check_dirty_words = False

    result = await check("hello world", session=mock_session)
    assert result[0]["content"] == "hello world"
    assert result[0]["status"] is True


@pytest.mark.asyncio
async def test_check_bool_returns_true_on_dirty(monkeypatch):
    async def fake_check(*args, **kwargs):
        return [{"content": "bad", "status": False, "original": "bad"}]

    monkeypatch.setattr("core.dirty_check.check", fake_check)
    result = await check_bool("bad")
    assert result is True


@pytest.mark.asyncio
async def test_check_bool_returns_false_on_clean(monkeypatch):
    async def fake_check(*args, **kwargs):
        return [{"content": "good", "status": True, "original": "good"}]

    monkeypatch.setattr("core.dirty_check.check", fake_check)
    result = await check_bool("good")
    assert result is False


@pytest.mark.asyncio
async def test_parse_data_replaces_risky_words(monkeypatch):
    monkeypatch.setattr("core.dirty_check.I18NContext", DummyI18N)

    result = parse_data("some bad word", {
        "Result": [{"Confidence": 80, "Label": "abuse", "RiskWords": "bad"}],
        "RiskLevel": "high"
    }, confidence=50)

    assert "<REDACTED:abuse>" in result["content"]
    assert result["status"] is False
