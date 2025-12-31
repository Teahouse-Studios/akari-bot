import time
import pytest

from core.cooldown import CoolDown


class MockSessionInfo:
    def __init__(self, target_id, sender_id):
        self.target_id = target_id
        self.sender_id = sender_id


class MockMessageSession:
    def __init__(self, target_id, sender_id):
        self.session_info = MockSessionInfo(target_id, sender_id)


@pytest.fixture
def fake_msg():
    return MockMessageSession(target_id="TEST|Console|0", sender_id="TEST|0")


def test_cooldown_reset(fake_msg):
    cd = CoolDown("test_reset", fake_msg, delay=0.1)
    time.sleep(0.1)
    remaining_before = cd.check()
    assert remaining_before == 0

    cd.reset()
    remaining_after = cd.check()
    assert remaining_after > remaining_before


def test_cooldown_whole_target():
    msg1 = MockMessageSession(target_id="TEST|Console|0", sender_id="TEST|0")
    msg2 = MockMessageSession(target_id="TEST|Console|0", sender_id="TEST|1")

    cd1 = CoolDown("whole_test", msg1, delay=1, whole_target=True)
    cd2 = CoolDown("whole_test", msg2, delay=1, whole_target=True)

    cd1.reset()
    remaining_cd2 = cd2.check()
    assert remaining_cd2 > 0


def test_cooldown_independent_senders():
    msg1 = MockMessageSession(target_id="TEST|Console|0", sender_id="TEST|0")
    msg2 = MockMessageSession(target_id="TEST|Console|0", sender_id="TEST|1")

    cd1 = CoolDown("indep_test", msg1, delay=1)
    cd2 = CoolDown("indep_test", msg2, delay=1)

    cd1.reset()
    remaining_cd2 = cd2.check()

    assert remaining_cd2 <= 1
