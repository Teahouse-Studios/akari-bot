import pytest
from core.i18n import LocaleNode, Locale


@pytest.fixture
def setup_locale_node():
    root = LocaleNode()
    root.update_node("en_us.hello", "Hello")
    root.update_node("en_us.world", "World")
    root.update_node("zh_cn.hello", "你好")
    root.update_node("zh_cn.world", "世界")
    return root


def test_query_existing_node(setup_locale_node):
    root = setup_locale_node
    node = root.query_node("en_us.hello")
    assert node.value == "Hello"


def test_query_nonexistent_node(setup_locale_node):
    root = setup_locale_node
    node = root.query_node("en_us.not_exist")
    assert node is None


def test_update_new_node(setup_locale_node):
    root = setup_locale_node
    root.update_node("en_us.new", "New Value")
    node = root.query_node("en_us.new")
    assert node.value == "New Value"


def test_update_nested_node(setup_locale_node):
    root = setup_locale_node
    root.update_node("en_us.level1.level2", "Nested")
    node = root.query_node("en_us.level1.level2")
    assert node.value == "Nested"


@pytest.fixture
def locale_zh():
    return Locale("zh_cn", fallback_lng=["en_us"])


def test_get_string_with_fallback_existing(locale_zh):
    locale_zh.data.update_node("hello", "你好")
    assert locale_zh.get_string_with_fallback("hello") == "你好"


def test_get_string_with_fallback_fallback(locale_zh):
    Locale("en_us").data.update_node("world", "World")
    locale_zh.data.children.pop("world", None)
    assert locale_zh.get_string_with_fallback("world") == "World"


def test_get_string_with_fallback_missing(locale_zh):
    assert locale_zh.get_string_with_fallback("nonexistent", fallback_failed_prompt=False) == "{I18N:nonexistent}"


def test_t_template_substitution(locale_zh):
    locale_zh.data.update_node("greet", "你好，${name}！")
    assert locale_zh.t("greet", name="Alice") == "你好，Alice！"


def test_t_dict_key_fallback(locale_zh):
    key_dict = {"en_us": "Yes", "zh_cn": "是", "fallback": "Fallback"}
    assert locale_zh.t(key_dict) == "是"
    locale_zh.locale = "ja_jp"
    assert locale_zh.t(key_dict) == "Fallback"


def test_t_str_replacement(locale_zh):
    locale_zh.data.update_node("welcome", "欢迎，${user}！")
    text = "问候：{I18N:welcome,user=Bob}"
    result = locale_zh.t_str(text)
    assert result == "问候：欢迎，Bob！"
