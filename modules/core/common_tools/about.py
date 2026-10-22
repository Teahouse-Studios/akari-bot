from pathlib import Path

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ButtonRows
from core.builtins.message.internal import ActionText, Button, ButtonFrame, I18NContext, Image, Markdown, Plain, Url
from core.builtins.utils import command_prefix
from core.component import module
from core.config.base import CoreConfig
from core.constants.path import assets_path
from core.logger import Logger
from core.utils.func import is_int

about = module(
    "about",
    base=True,
    doc=True,
    alias={
        "version": "about version",
        "ping": "about ping",
        "status": "about status",
    },
)

CHARACTER_IMAGE_PATH = assets_path / "character_marked.png"
CREDITS_PATH = assets_path / "credits.txt"
CHARACTER_IMAGE_MAX_WIDTH = 512
QQBOT_PERMISSIONS_URL_TEMPLATE = (
    "https://club.vip.qq.com/transfer?open_kuikly_info=%7B%22page_name%22%3A%20%22"
    "ai_group_service_agreement_pop_page%22%2C%22groupCode%22%3A{qq_group_id}%2C%22"
    "botUin%22%3A{bot_qq}%2C%22botUid%22%3A%22{bot_uid}%22%2C%22screen%22%3A1%7D"
)


def read_credits(path: Path = CREDITS_PATH) -> str | None:
    """读取制作人员名单；文件不存在、不可读或内容为空时不展示。"""
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except OSError as e:
        Logger.warning(f"Unable to read credits file {path}: {e}")
        return None


def build_credits_message(msg: Bot.MessageSession) -> MessageChain:
    """构造制作人员名单消息。"""
    result = MessageChain.create()
    if not (credits := read_credits()):
        result.append(I18NContext("core.message.about.credits.unavailable"))
        return result

    title = msg.session_info.locale.t("core.message.about.credits")
    result.append(Markdown(f"```{title}\n{credits}\n```", disable_joke=True))
    return result


def build_about_message(msg: Bot.MessageSession) -> MessageChain:
    """根据平台能力构造关于菜单。"""
    locale = msg.session_info.locale
    support_markdown = msg.session_info.support_markdown
    result = MessageChain.create()
    result.append(Image(CHARACTER_IMAGE_PATH, max_h=CHARACTER_IMAGE_MAX_WIDTH))

    introduction = locale.t("core.message.about.introduction")
    result.append(Plain(introduction, disable_joke=True))

    credits = read_credits()

    if CoreConfig.repo_url:
        repository_label = locale.t("core.message.about.button.repository")
        if support_markdown and msg.session_info.client_name == "QQBot":
            result.append(Plain("\n"))
        result.append(Plain(f"{repository_label}：", disable_joke=True))
        result.append(
            Url(
                CoreConfig.repo_url,
                trusted=True,
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
        if credits:
            rows.append(
                ButtonRows.assign([Button(locale.t("core.message.about.credits"), f"{command_prefix[0]}about credits")])
            )
        for label_key, value in links:
            rows.append(ButtonRows.assign([Button(locale.t(label_key), value)]))
        if rows:
            result.append(ButtonFrame(rows))
    else:
        for label_key, value in links:
            result.append(Plain(f"{locale.t(label_key)}：{value}", disable_joke=True))

    return result


def build_qqbot_permissions_url(msg: Bot.MessageSession, qq_group_id: str) -> str:
    tmp = msg.session_info.tmp or {}
    return QQBOT_PERMISSIONS_URL_TEMPLATE.format(
        qq_group_id=qq_group_id,
        bot_qq=tmp.get("qq_bot_qqnum", ""),
        bot_uid=tmp.get("qq_bot_uid", ""),
    )


@about.command("{{I18N:core.help.about}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(build_about_message(msg))


@about.command("credits {{I18N:core.help.about.credits}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(build_credits_message(msg))


@about.command("permissions [<qq_group_id>] {{I18N:core.help.about.permissions}}", available_for="QQBot")
async def qqbot_permissions(msg: Bot.MessageSession, qq_group_id: str | None = None):
    if qq_group_id:
        if not is_int(qq_group_id):
            await msg.finish(I18NContext("core.message.about.permissions.invalid"))
        url = build_qqbot_permissions_url(msg, qq_group_id)
        await msg.finish(
            [
                I18NContext("core.message.about.permissions.quick_config"),
                Button(msg.session_info.locale.t("core.message.about.permissions.quick_config.button"), url),
            ]
        )
    await msg.finish(
        I18NContext(
            "core.message.about.permissions",
            cmd=ActionText(
                f"{msg.session_info.prefixes[0]}about permissions ",
                show_on_fallback=False,
            ),
        )
    )
