import pytest

from core.utils.tools import (
    convert_list, is_iterable, is_json_serializable, chunk_list,
    unique_list, flatten_list, flatten_dict, unflatten_dict,
    is_int, is_float
)


def test_convert_list():
    assert convert_list(None) == []
    assert convert_list([1, 2]) == [1, 2]
    assert convert_list(5) == [5]
    assert convert_list((1, 2)) == [1, 2]


def test_is_iterable():
    assert is_iterable([1, 2, 3])
    assert is_iterable((1, 2))
    assert not is_iterable("abc")
    assert not is_iterable(b"bytes")
    assert not is_iterable(123)


def test_is_json_serializable():
    assert is_json_serializable({"a": 1})
    assert is_json_serializable([1, 2, 3])
    assert not is_json_serializable(set([1, 2]))
    assert not is_json_serializable(lambda x: x)


def test_chunk_list_basic():
    data = [1, 2, 3, 4, 5]
    result = list(chunk_list(data, 2))
    assert result == [[1, 2], [3, 4], [5]]


def test_chunk_list_reverse():
    data = [1, 2, 3, 4]
    result = list(chunk_list(data, 2, reverse=True))
    assert result == [[4, 3], [2, 1]]


def test_chunk_list_errors():
    with pytest.raises(ValueError):
        list(chunk_list([1, 2], 0))
    with pytest.raises(TypeError):
        list(chunk_list("abc", 2))


def test_unique_list_basic():
    data = [1, 2, 2, 3, 1]
    assert unique_list(data) == [1, 2, 3]


def test_unique_list_reverse():
    data = [1, 2, 2, 3, 1]
    assert unique_list(data, reverse=True) == [1, 3, 2]


def test_unique_list_error():
    with pytest.raises(TypeError):
        unique_list("abc")


def test_flatten_list_basic():
    nested = [1, [2, 3], [4, [5, 6]], 7]
    assert flatten_list(nested) == [1, 2, 3, 4, 5, 6, 7]


def test_flatten_list_error():
    with pytest.raises(TypeError):
        flatten_list({"a": 1})


def test_flatten_and_unflatten_dict():
    nested = {"a": {"b": 1, "c": {"d": 2}}, "e": 3}
    flat = flatten_dict(nested)
    expected_flat = {"a.b": 1, "a.c.d": 2, "e": 3}
    assert flat == expected_flat
    restored = unflatten_dict(flat)
    assert restored == nested


def test_is_int():
    assert is_int(1)
    assert is_int(1.0)
    assert is_int("2")
    assert is_int("-5")
    assert not is_int("3.14")
    assert not is_int("abc")
    assert not is_int("")
    assert not is_int(None)


def test_is_float():
    assert is_float(1)
    assert is_float(1.5)
    assert is_float("3.14")
    assert is_float("-2")
    assert not is_float("abc")
    assert not is_float("")
    assert not is_float(None)
