"""core.utils.random 纯函数单元测试 - Random 类。"""

from core.tester import func_case, Tester
from core.utils.random import Random


def _test_random_random():
    """测试 Random.random() - 返回 0-1 之间浮点数"""
    try:
        for _ in range(100):
            val = Random.random()
            if not (0 <= val < 1):
                return False
        return True
    except Exception:
        return False


def _test_random_randint():
    """测试 Random.randint() - 返回 [a,b] 范围内整数"""
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
    """测试 Random.uniform() - 返回 [a,b] 范围内浮点数"""
    try:
        for _ in range(100):
            val = Random.uniform(1.0, 10.0)
            if not (1.0 <= val <= 10.0):
                return False
        return True
    except Exception:
        return False


def _test_random_randrange():
    """测试 Random.randrange() - 类似 range 的随机整数"""
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
    """测试 Random.choice() - 从序列中随机选择"""
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
    """测试 Random.choices() - 从序列中选择 k 个（允许重复）"""
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
    """测试 Random.sample() - 从序列中选择 k 个（不重复）"""
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
    """测试 Random.shuffle() - 随机打乱序列"""
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

    return tester
