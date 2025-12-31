from unittest.mock import patch

from core.joke import check_apr_fools, shuffle_joke


@patch("core.joke.time.localtime")
@patch("core.joke.Config")
def test_check_apr_fools_true(mock_config, mock_localtime):
    mock_config.return_value = True
    mock_localtime.return_value = type("Time", (), {"tm_mon": 4, "tm_mday": 1})()
    assert check_apr_fools() is True


@patch("core.joke.time.localtime")
@patch("core.joke.Config")
def test_check_apr_fools_false_date(mock_config, mock_localtime):
    mock_config.return_value = True
    mock_localtime.return_value = type("Time", (), {"tm_mon": 5, "tm_mday": 2})()
    assert check_apr_fools() is False


@patch("core.joke.time.localtime")
@patch("core.joke.Config")
def test_check_apr_fools_disabled(mock_config, mock_localtime):
    mock_config.return_value = False
    mock_localtime.return_value = type("Time", (), {"tm_mon": 4, "tm_mday": 1})()
    assert check_apr_fools() is False


@patch("core.joke.check_apr_fools")
def test_shuffle_joke_not_april(mock_check):
    mock_check.return_value = False
    text = "Hello world"
    assert shuffle_joke(text) == text


@patch("core.joke.check_apr_fools")
def test_shuffle_joke_url(mock_check):
    mock_check.return_value = True
    text = "Visit https://example.com now"
    result = shuffle_joke(text)
    assert "https://example.com" in result


@patch("core.joke.check_apr_fools")
@patch("core.joke.Config")
@patch("core.joke.random.random")
def test_shuffle_joke_shuffle(mock_random, mock_config, mock_check):
    mock_check.return_value = True
    mock_config.return_value = 1.0
    mock_random.return_value = 0.05

    text = "abcd efgh"
    shuffled_text = shuffle_joke(text)
    assert shuffled_text != text
    assert "abcd" not in shuffled_text or "efgh" not in shuffled_text
