import pytest

from core.game import PlayState, _ps_lst
from core.utils.temp import ExpiringTempDict


class MockSessionInfo:
    def __init__(self, target_id, sender_id):
        self.target_id = target_id
        self.sender_id = sender_id


class MockMessageSession:
    def __init__(self, target_id="TEST|Console|0", sender_id="TEST|0"):
        self.session_info = MockSessionInfo(target_id, sender_id)


@pytest.fixture
def playstate():
    _ps_lst.clear()
    target_id = "TEST|Console|0"
    game_name = "test_game"
    _ps_lst[target_id] = ExpiringTempDict()
    _ps_lst[target_id][game_name] = ExpiringTempDict()
    msg = MockMessageSession(target_id=target_id)
    return PlayState(game_name, msg)


def test_enable_and_disable(playstate):
    assert playstate.check() is False
    playstate.enable()
    assert playstate.check() is True
    playstate.disable()
    assert playstate.check() is False


def test_update_and_get(playstate):
    playstate.update(score=10, level=2)
    assert playstate.get("score") == 10
    assert playstate.get("level") == 2
    assert playstate.get("non_exist", "default") == "default"
