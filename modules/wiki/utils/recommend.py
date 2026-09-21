from typing import NoReturn

from core.builtins.bot import Bot
from core.builtins.message.internal import ActionText, ButtonFrame, I18NContext
from core.builtins.message.elements import ButtonRows
from core.builtins.utils import command_prefix
from core.utils.button import arrange_buttons

# 未设置默认 Wiki 时向用户推荐的 Wiki，元素为（显示名称，API 端点地址）。
RECOMMENDED_WIKIS: list[tuple[str, str]] = [
    ("Minecraft Wiki", "https://zh.minecraft.wiki/api.php"),
]


def get_recommend_button_data() -> list[ButtonRows]:
    """构造推荐 Wiki 的按钮数据，每个元素为一行按钮。

    :return: 按钮数据，键为按钮文本，值为点击后发出的命令。
    """
    return arrange_buttons([(name, f"{command_prefix[0]}wiki set {url}") for name, url in RECOMMENDED_WIKIS])


async def finish_with_start_wiki_not_set(msg: Bot.MessageSession) -> NoReturn:
    """提示当前场景尚未设置默认 Wiki 并终结会话。

    :param msg: 消息会话对象。
    """
    prompts = [
        I18NContext(
            "wiki.message.set.not_set",
            cmd=ActionText(f"{msg.session_info.prefixes[0]}wiki set"),
        )
    ]
    button_data = []
    if RECOMMENDED_WIKIS and msg.session_info.support_button and await msg.check_permission():
        prompts.append(I18NContext("wiki.message.set.not_set.recommend"))
        button_data = get_recommend_button_data()
    if button_data:
        prompts.append(ButtonFrame(button_data))
    await msg.finish(prompts)
