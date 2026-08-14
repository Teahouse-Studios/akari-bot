from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from core.builtins.message.elements import ButtonFrameElement, ImageElement, PlainElement, URLElement
from core.builtins.utils import command_prefix
from core.config.base import CoreConfig
from core.i18n import Locale
from core.tester import Contains, Tester, func_case
from modules.core.about import (
    CHARACTER_IMAGE_MAX_WIDTH,
    CHARACTER_IMAGE_PATH,
    build_about_message,
    build_credits_message,
    read_credits,
)


def _msg(client_name="TEST", support_markdown=True, support_button=True):
    return SimpleNamespace(
        session_info=SimpleNamespace(
            client_name=client_name,
            support_markdown=support_markdown,
            support_button=support_button,
            support_embed=False,
            support_action_text=False,
            use_url_manager=False,
            use_url_md_format=False,
            locale=Locale("zh_cn"),
        )
    )


def _plain_texts(chain) -> list[str]:
    return [element.text for element in chain.as_sendable(_msg().session_info) if isinstance(element, PlainElement)]


def _test_missing_or_empty_credits_are_hidden():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        missing = root / "missing.txt"
        empty = root / "empty.txt"
        empty.write_text(" \n", encoding="utf-8")
        return read_credits(missing) is None and read_credits(empty) is None


def _test_markdown_layout_without_credits():
    with patch("modules.core.about.read_credits", return_value=None):
        chain = build_about_message(_msg())
    texts = _plain_texts(chain)
    introduction = Locale("zh_cn").t("core.message.about.introduction")
    return (
        isinstance(chain.values[0], ImageElement)
        and chain.values[0].path == str(CHARACTER_IMAGE_PATH)
        and chain.values[0].max_h == CHARACTER_IMAGE_MAX_WIDTH
        and texts[0] == introduction
        and "AGPL-3.0" in texts[0]
        and all("制作人员名单" not in text for text in texts)
    )


def _test_credits_button_and_no_button_hidden():
    with patch("modules.core.about.read_credits", return_value="Alice\nBob"):
        markdown = build_about_message(_msg(support_markdown=True))
        no_button = build_about_message(_msg(support_markdown=False, support_button=False))
    locale = Locale("zh_cn")
    credits_title = locale.t("core.message.about.credits")
    repository_label = locale.t("core.message.about.button.repository")
    markdown_text = [element.text for element in markdown.values if isinstance(element, PlainElement)]
    no_button_text = [element.text for element in no_button.values if isinstance(element, PlainElement)]
    frame = next(element for element in markdown.values if isinstance(element, ButtonFrameElement))
    credits_button = frame.rows[0].buttons[0]
    return (
        not markdown_text[0].startswith("> ")
        and all("Alice" not in text and "Bob" not in text for text in markdown_text)
        and credits_button.show == credits_title
        and credits_button.value == f"{command_prefix[0]}about credits"
        and all(credits_title not in text and "Alice" not in text and "Bob" not in text for text in no_button_text)
        and f"{repository_label}：" in markdown_text
    )


def _test_credits_message_markdown_and_plain():
    with patch("modules.core.about.read_credits", return_value="Alice\nBob"):
        markdown = build_credits_message(_msg(support_markdown=True))
        plain = build_credits_message(_msg(support_markdown=False))
    title = Locale("zh_cn").t("core.message.about.credits")
    return markdown.values[0].text == f"```{title}\nAlice\nBob\n```" and plain.values[0].text == f"{title}\nAlice\nBob"


def _test_button_rows_and_qq_only_entry():
    config = {
        "repo_url": "https://example.com/repo",
        "issue_url": "https://example.com/issues",
        "qq_test_group_url": "https://example.com/qq-group",
        "donate_url": "https://example.com/donate",
    }
    patches = [patch.object(CoreConfig, key, value, create=True) for key, value in config.items()]
    for current in patches:
        current.start()
    try:
        normal = build_about_message(_msg(client_name="Discord"))
        qqbot = build_about_message(_msg(client_name="QQBot"))
    finally:
        for current in reversed(patches):
            current.stop()

    normal_frame = next(element for element in normal.values if isinstance(element, ButtonFrameElement))
    qqbot_frame = next(element for element in qqbot.values if isinstance(element, ButtonFrameElement))
    normal_repo = next(element for element in normal.values if isinstance(element, URLElement))
    qqbot_repo = next(element for element in qqbot.values if isinstance(element, URLElement))
    normal_values = [row.buttons[0].value for row in normal_frame.rows]
    qqbot_values = [row.buttons[0].value for row in qqbot_frame.rows]
    return (
        normal_repo.original_url == config["repo_url"]
        and not normal_repo.applied_md_format
        and normal_repo.url == config["repo_url"]
        and qqbot_repo.original_url == config["repo_url"]
        and normal_values == [f"{command_prefix[0]}about credits", config["issue_url"], config["donate_url"]]
        and qqbot_values
        == [
            f"{command_prefix[0]}about credits",
            config["issue_url"],
            config["qq_test_group_url"],
            config["donate_url"],
        ]
        and normal_frame.rows[-1].buttons[0].show == "💵 支持我们"
    )


def _test_no_button_support_has_no_frame():
    with patch("modules.core.about.read_credits", return_value=None):
        chain = build_about_message(_msg(support_button=False))
    texts = [element.text for element in chain.values if isinstance(element, PlainElement)]
    urls = [element.original_url for element in chain.values if isinstance(element, URLElement)]
    return (
        not chain.contains(ButtonFrameElement)
        and CoreConfig.repo_url in urls
        and any("issues/new/choose" in text for text in texts)
        and any("afdian.com" in text for text in texts)
    )


def _test_repository_url_plain_fallback():
    with patch("modules.core.about.read_credits", return_value=None):
        chain = build_about_message(_msg(support_markdown=False))
    repo = next(element for element in chain.values if isinstance(element, URLElement))
    texts = [element.text for element in chain.values if isinstance(element, PlainElement)]
    repository_label = Locale("zh_cn").t("core.message.about.button.repository")
    return repo.original_url == CoreConfig.repo_url and not repo.applied_md_format and f"{repository_label}：" in texts


@func_case
async def test_about(tester: Tester):
    """modules.core.about: 关于菜单。"""
    await tester.test(_test_missing_or_empty_credits_are_hidden, "制作人员文件缺失或为空时隐藏测试")
    await tester.test(_test_markdown_layout_without_credits, "Markdown 关于菜单布局测试")
    await tester.test(_test_credits_button_and_no_button_hidden, "制作人员按钮与无按钮隐藏测试")
    await tester.test(_test_credits_message_markdown_and_plain, "制作人员名单消息测试")
    await tester.test(_test_button_rows_and_qq_only_entry, "关于菜单按钮与 QQBot 专属入口测试")
    await tester.test(_test_no_button_support_has_no_frame, "无按钮能力时降级为文本链接测试")
    await tester.test(_test_repository_url_plain_fallback, "开源仓库 Url 普通文本降级测试")
    credits_title = Locale("zh_cn").t("core.message.about.credits")
    await tester.integrate("~about credits", Contains(credits_title), "开发人员名单子命令测试")
    return tester
