"""QQBot 指令操作标签的渲染测试。

标签构造与长度截断放在适配器侧而非核心层：100 字符是该平台的约束，日后其他平台
若具备等价能力，上限未必相同。此处单独成文件，是因为渲染须 import 依赖 botpy 的
适配器模块，混在核心层测试中会让后者平白背上这个依赖。
"""

from urllib.parse import quote

from bots.qqbot.context import ACTION_TEXT_MAX_LENGTH, _render_action_text
from core.builtins.message.elements import ActionTextElement, PlainElement
from core.tester import func_case, Tester


def _test_render_full_attributes():
    """测试标签属性完整且值经 urlencode"""
    try:
        elem = ActionTextElement.assign("~wiki 沙盒", show="沙盒", reference=True).resolve(None)
        tag = _render_action_text(elem)
        expected = (
            f'<qqbot-cmd-input text="{quote("~wiki 沙盒", safe="")}" '
            f'show="{quote("沙盒", safe="")}" reference="true" />'
        )
        return tag == expected
    except Exception:
        return False


def _test_render_omits_empty_show():
    """测试 show 为空时省略该属性，由平台默认取 text"""
    try:
        elem = ActionTextElement.assign("~wiki 沙盒").resolve(None)
        tag = _render_action_text(elem)
        if "show=" in tag:
            return False
        if 'reference="false"' not in tag:
            return False
        return True
    except Exception:
        return False


def _test_render_escapes_quotes():
    """测试属性值编码后不含会破坏标签的字符"""
    try:
        elem = ActionTextElement.assign('~echo "a" <b> &c', show="<标签>").resolve(None)
        tag = _render_action_text(elem)
        inner = tag[len("<qqbot-cmd-input ") : -len(" />")]
        for char in ('"a"', "<b>", "&c", "<标签>"):
            if char in inner:
                return False
        return True
    except Exception:
        return False


def _test_render_truncates_text():
    """测试超长 text 截断至平台上限"""
    try:
        long_text = "长" * 200
        elem = ActionTextElement.assign(long_text).resolve(None)
        tag = _render_action_text(elem)
        expected = quote("长" * ACTION_TEXT_MAX_LENGTH, safe="")
        if f'text="{expected}"' not in tag:
            return False
        return True
    except Exception:
        return False


def _test_render_truncates_show():
    """测试超长 show 独立截断，不受 text 影响"""
    try:
        elem = ActionTextElement.assign("~wiki 沙盒", show="标" * 150).resolve(None)
        tag = _render_action_text(elem)
        expected = quote("标" * ACTION_TEXT_MAX_LENGTH, safe="")
        if f'show="{expected}"' not in tag:
            return False
        if f'text="{quote("~wiki 沙盒", safe="")}"' not in tag:
            return False
        return True
    except Exception:
        return False


def _test_render_empty_text():
    """测试 text 为空时不产出标签"""
    try:
        elem = ActionTextElement.assign("").resolve(None)
        return _render_action_text(elem) == ""
    except Exception:
        return False


def _test_features_declared():
    """测试适配器按 markdown 开关声明该能力

    指令操作标签只在 markdown 消息中生效，故该标志须跟随 qq_use_markdown，
    恒为真会让模块侧构造出发不出去的可点击内容。
    """
    try:
        from bots.qqbot.config import QQBotConfig
        from bots.qqbot.features import features

        return features.support_action_text is QQBotConfig.qq_use_markdown
    except Exception:
        return False


def _test_send_msg_markdown_inline_join():
    """测试指令操作与其前后文本落在同一行

    句子经 KE 码切分后形如「（」、指令操作、「）」三段，适配器以换行拼接各项，
    不跟踪行内状态就会把一句话拆成三行。
    """
    try:
        # 复刻 send_msg_markdown() 的拼接逻辑，验证状态跟踪的取值
        elements = [
            PlainElement.assign("（"),
            ActionTextElement.assign("~wiki 沙盒").resolve(None),
            PlainElement.assign("）"),
        ]
        texts = []
        inline_pending = False
        for x in elements:
            if isinstance(x, ActionTextElement):
                tag = _render_action_text(x)
                if tag:
                    if texts:
                        texts[-1] += tag
                    else:
                        texts.append(tag)
                inline_pending = True
            else:
                if inline_pending and texts:
                    texts[-1] += x.text
                else:
                    texts.append(x.text)
                inline_pending = False
        if len(texts) != 1:
            return False
        if not texts[0].startswith("（<qqbot-cmd-input "):
            return False
        if not texts[0].endswith("/>）"):
            return False
        return True
    except Exception:
        return False


@func_case
async def test_qqbot_action_text(tester: Tester):
    """bots.qqbot.context: 指令操作标签渲染测试"""
    await tester.test(_test_render_full_attributes, "标签属性完整性测试")
    await tester.test(_test_render_omits_empty_show, "无 show 省略属性测试")
    await tester.test(_test_render_escapes_quotes, "属性值编码测试")
    await tester.test(_test_render_truncates_text, "text 截断测试")
    await tester.test(_test_render_truncates_show, "show 独立截断测试")
    await tester.test(_test_render_empty_text, "空 text 不产出标签测试")
    await tester.test(_test_features_declared, "适配器能力声明测试")
    await tester.test(_test_send_msg_markdown_inline_join, "行内拼接测试")

    return tester
