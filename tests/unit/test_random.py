"""core.utils.random 纯函数单元测试 - Random 类。"""

from core.tester import func_case, Tester
from core.utils.random import Random, SecureRandom


def _test_random_random():
    try:
        for _ in range(100):
            val = Random.random()
            if not (0 <= val < 1):
                return False
        return True
    except Exception:
        return False


def _test_random_randint():
    try:
        for _ in range(100):
            val = Random.randint(1, 10)
            if not (1 <= val <= 10):
                return False
        val = Random.randint(5, 5)
        if val != 5:
            return False
        val = Random.randint(-10, -1)
        if not (-10 <= val <= -1):
            return False
        return True
    except Exception:
        return False


def _test_random_uniform():
    try:
        for _ in range(100):
            val = Random.uniform(1.0, 10.0)
            if not (1.0 <= val <= 10.0):
                return False
        return True
    except Exception:
        return False


def _test_random_randrange():
    try:
        for _ in range(100):
            val = Random.randrange(10)
            if not (0 <= val < 10):
                return False
        for _ in range(100):
            val = Random.randrange(5, 15)
            if not (5 <= val < 15):
                return False
        for _ in range(100):
            val = Random.randrange(0, 20, 3)
            if val % 3 != 0 or not (0 <= val < 20):
                return False
        return True
    except Exception:
        return False


def _test_random_choice():
    try:
        seq = ["a", "b", "c", "d", "e"]
        for _ in range(100):
            val = Random.choice(seq)
            if val not in seq:
                return False
        return True
    except Exception:
        return False


def _test_random_choices():
    try:
        seq = ["a", "b", "c", "d", "e"]
        result = Random.choices(seq, k=10)
        if len(result) != 10:
            return False
        for val in result:
            if val not in seq:
                return False
        return True
    except Exception:
        return False


def _test_random_sample():
    try:
        seq = ["a", "b", "c", "d", "e"]
        result = Random.sample(seq, k=3)
        if len(result) != 3:
            return False
        if len(set(result)) != 3:
            return False
        for val in result:
            if val not in seq:
                return False
        return True
    except Exception:
        return False


def _test_random_shuffle():
    try:
        original = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        seq = original.copy()
        result = Random.shuffle(seq)
        if result is not seq:
            return False
        if sorted(seq) != sorted(original):
            return False
        return True
    except Exception:
        return False


def _test_random_token_urlsafe():
    try:
        tokens = [Random.token_urlsafe(9), SecureRandom.token_urlsafe(9)]
        return SecureRandom.use_secrets and all(
            len(token) == 12 and token.isascii() and all(char.isalnum() or char in "-_" for char in token)
            for token in tokens
        )
    except Exception:
        return False


@func_case
async def test_random(tester: Tester):
    """core.utils.random: Random 类全部方法测试"""
    await tester.test(_test_random_random, "Random.random() 测试")
    await tester.test(_test_random_randint, "Random.randint() 测试")
    await tester.test(_test_random_uniform, "Random.uniform() 测试")
    await tester.test(_test_random_randrange, "Random.randrange() 测试")
    await tester.test(_test_random_choice, "Random.choice() 测试")
    await tester.test(_test_random_choices, "Random.choices() 测试")
    await tester.test(_test_random_sample, "Random.sample() 测试")
    await tester.test(_test_random_shuffle, "Random.shuffle() 测试")
    await tester.test(_test_random_token_urlsafe, "Random.token_urlsafe() 测试")

    return tester
