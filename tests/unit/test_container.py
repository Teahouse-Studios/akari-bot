"""core.utils.container 纯函数单元测试 - TokenBucket / ExpiringTempDict。"""

import time

from core.tester import func_case, Tester
from core.utils.container import TokenBucket, ExpiringTempDict


def _test_token_bucket_basic():
    """测试 TokenBucket 基本功能"""
    try:
        bucket = TokenBucket(capacity=10, refill_interval=10)
        if bucket.capacity != 10:
            return False
        if abs(bucket.peek() - 10.0) > 0.1:
            return False
        if bucket.consume(5) is not True:
            return False
        if abs(bucket.peek() - 5.0) > 0.1:
            return False
        if bucket.consume(6) is not False:
            return False
        if bucket.consume(5) is not True:
            return False
        if abs(bucket.peek() - 0.0) > 0.1:
            return False
        if bucket.consume(1) is not False:
            return False
        return True
    except Exception:
        return False


def _test_token_bucket_refill():
    """测试 TokenBucket 补充功能"""
    try:
        bucket = TokenBucket(capacity=10, refill_interval=10)
        bucket.consume(10)
        bucket.refill(5)
        if abs(bucket.peek() - 5.0) > 0.1:
            return False
        bucket.refill(100)
        if abs(bucket.peek() - 10.0) > 0.1:
            return False
        return True
    except Exception:
        return False


def _test_token_bucket_wait_time():
    """测试 TokenBucket 等待时间"""
    try:
        bucket = TokenBucket(capacity=10, refill_interval=10)
        if bucket.wait_time(5) != 0.0:
            return False
        bucket.consume(10)
        if bucket.wait_time(1) <= 0:
            return False
        return True
    except Exception:
        return False


def _test_token_bucket_bool():
    """测试 TokenBucket bool 转换"""
    try:
        bucket = TokenBucket(capacity=10, refill_interval=10)
        if bool(bucket) is not True:
            return False
        bucket.consume(10)
        if bool(bucket) is not False:
            return False
        return True
    except Exception:
        return False


def _test_expiring_dict_basic():
    """测试 ExpiringTempDict 基本 CRUD"""
    try:
        d = ExpiringTempDict(exp=3600)
        d["key1"] = "value1"
        if d["key1"] != "value1":
            return False
        d["key1"] = "value2"
        if d["key1"] != "value2":
            return False
        if "key1" not in d:
            return False
        if "key2" in d:
            return False
        del d["key1"]
        if "key1" in d:
            return False
        d["a"] = 1
        d["b"] = 2
        if len(d) != 2:
            return False
        return True
    except Exception:
        return False


def _test_expiring_dict_expiry():
    """测试 ExpiringTempDict 过期检查"""
    try:
        d = ExpiringTempDict(exp=0, ts=time.time() - 10)
        if d.is_expired() is not True:
            return False
        d2 = ExpiringTempDict(exp=3600)
        if d2.is_expired() is not False:
            return False
        return True
    except Exception:
        return False


def _test_expiring_dict_nested():
    """测试 ExpiringTempDict 嵌套访问"""
    try:
        d = ExpiringTempDict(exp=3600)
        nested = d["sub"]
        if not isinstance(nested, ExpiringTempDict):
            return False
        d["sub"]["key"] = "value"
        if d["sub"]["key"] != "value":
            return False
        return True
    except Exception:
        return False


def _test_expiring_dict_get():
    """测试 ExpiringTempDict get 方法"""
    try:
        d = ExpiringTempDict(exp=3600)
        d["key"] = "value"
        if d.get("key") != "value":
            return False
        if d.get("missing") is not None:
            return False
        if d.get("missing", "default") != "default":
            return False
        return True
    except Exception:
        return False


def _test_expiring_dict_copy():
    """测试 ExpiringTempDict copy 方法"""
    try:
        d = ExpiringTempDict(exp=3600)
        d["key"] = "value"
        d2 = d.copy()
        if d2["key"] != "value":
            return False
        d2["key"] = "modified"
        if d["key"] != "value":
            return False
        return True
    except Exception:
        return False


def _test_expiring_dict_operations():
    """测试 ExpiringTempDict 操作方法"""
    try:
        d = ExpiringTempDict(exp=3600)
        d["a"] = 1
        d["b"] = 2
        v = d.pop("a")
        if v != 1:
            return False
        if "a" in d:
            return False
        if set(d.keys()) != {"b"}:
            return False
        if list(d.values()) != [2]:
            return False
        if list(d.items()) != [("b", 2)]:
            return False
        d.update({"c": 3, "d": 4})
        if d["c"] != 3:
            return False
        d.clear()
        if len(d) != 0:
            return False
        return True
    except Exception:
        return False


def _test_expiring_dict_bool():
    """测试 ExpiringTempDict bool 转换"""
    try:
        d = ExpiringTempDict(exp=3600)
        if bool(d) is not False:
            return False
        d["key"] = "value"
        if bool(d) is not True:
            return False
        return True
    except Exception:
        return False


def _test_expiring_dict_serialization():
    """测试 ExpiringTempDict 序列化"""
    try:
        d = ExpiringTempDict(exp=3600)
        d["key"] = "value"
        d["nested"] = ExpiringTempDict(exp=3600)
        d["nested"]["inner"] = 42
        data = d.to_dict()
        if data["key"] != "value":
            return False
        if "_ts" not in data:
            return False
        if "_exp" not in data:
            return False
        d2 = ExpiringTempDict.from_dict(data)
        if d2["key"] != "value":
            return False
        return True
    except Exception:
        return False


@func_case
async def test_container(tester: Tester):
    """core.utils.container: TokenBucket 和 ExpiringTempDict 测试"""
    # TokenBucket 测试
    await tester.test(_test_token_bucket_basic, "TokenBucket 基本测试")
    await tester.test(_test_token_bucket_refill, "TokenBucket 补充测试")
    await tester.test(_test_token_bucket_wait_time, "TokenBucket 等待时间测试")
    await tester.test(_test_token_bucket_bool, "TokenBucket bool 测试")

    # ExpiringTempDict 测试
    await tester.test(_test_expiring_dict_basic, "ExpiringTempDict 基本 CRUD 测试")
    await tester.test(_test_expiring_dict_expiry, "ExpiringTempDict 过期测试")
    await tester.test(_test_expiring_dict_nested, "ExpiringTempDict 嵌套测试")
    await tester.test(_test_expiring_dict_get, "ExpiringTempDict get 测试")
    await tester.test(_test_expiring_dict_copy, "ExpiringTempDict copy 测试")
    await tester.test(_test_expiring_dict_operations, "ExpiringTempDict 操作测试")
    await tester.test(_test_expiring_dict_bool, "ExpiringTempDict bool 测试")
    await tester.test(_test_expiring_dict_serialization, "ExpiringTempDict 序列化测试")

    return tester
