from pathlib import Path

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ButtonRows
from core.builtins.message.internal import Button, ButtonFrame, Image, Plain, Url
from core.component import module
from core.config.base import CoreConfig
from core.constants.path import assets_path
from core.logger import Logger

about = module("about", base=True, doc=True)

CHARACTER_IMAGE_PATH = assets_path / "character_marked.png"
CREDITS_PATH = assets_path / "credits.txt"
CHARACTER_IMAGE_MAX_WIDTH = 512


def read_credits(path: Path = CREDITS_PATH) -> str | None:
    """读取制作人员名单；文件不存在、不可读或内容为空时不展示。"""
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except OSError as e:
        Logger.warning(f"Unable to read credits file {path}: {e}")
        return None


def build_about_message(msg: Bot.MessageSession) -> MessageChain:
    """根据平台能力构造关于菜单。"""
    locale = msg.session_info.locale
    support_markdown = msg.session_info.support_markdown
    result = MessageChain.create()
    result.append(Image(CHARACTER_IMAGE_PATH, max_h=CHARACTER_IMAGE_MAX_WIDTH))

    introduction = locale.t("core.message.about.introduction")
    result.append(Plain(introduction, disable_joke=True))

    if credits := read_credits():
        title = locale.t("core.message.about.credits")
        credits_text = f"```{title}\n{credits}\n```" if support_markdown else f"{title}\n{credits}"
        result.append(Plain(credits_text, disable_joke=True))

    license_ = locale.t("core.message.about.license")
    result.append(Plain(f"> {license_}" if support_markdown else license_, disable_joke=True))

    if CoreConfig.repo_url:
        repository_label = locale.t("core.message.about.button.repository")
        if support_markdown:
            result.append(Plain("\n"))
        result.append(Plain(f"{repository_label}：", disable_joke=True))
        result.append(
            Url(
                CoreConfig.repo_url,
                trusted=True,
                md_format=support_markdown,
            )
        )

    links = [
        ("core.message.about.button.issue", CoreConfig.issue_url),
    ]
    if msg.session_info.client_name == "QQBot" and CoreConfig.qq_test_group_url:
        links.append(("core.message.about.button.qq_group", CoreConfig.qq_test_group_url))
    links.append(("core.message.about.button.donate", CoreConfig.donate_url))
    links = [(label_key, value) for label_key, value in links if value]

    if msg.session_info.support_button:
        rows = []
        for label_key, value in links:
            rows.append(ButtonRows.assign([Button(locale.t(label_key), value)]))
        if rows:
            result.append(ButtonFrame(rows))
    else:
        for label_key, value in links:
            result.append(Plain(f"{locale.t(label_key)}：{value}", disable_joke=True))

    return result


@about.command("{{I18N:core.help.about}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(build_about_message(msg), force_markdown=msg.session_info.support_markdown)
