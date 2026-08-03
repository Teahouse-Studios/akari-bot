from typing import NoReturn

from core.builtins.bot import Bot
from core.builtins.message.internal import ActionText, I18NContext
from core.builtins.utils import command_prefix
from core.utils.button import arrange_buttons

# 未设置起始 Wiki 时向用户推荐的 Wiki，元素为（显示名称，API 端点地址）。
RECOMMENDED_WIKIS: list[tuple[str, str]] = [
    ("Minecraft Wiki", "https://zh.minecraft.wiki/api.php"),
]


def get_recommend_button_data() -> list[dict[str, str]]:
    """
    构造推荐 Wiki 的按钮数据，每个元素为一行按钮。

    按钮点击后经 interaction 事件另行建立会话，该会话的可用前缀取自全局配置，
    并不包含 QQ 平台在常规消息入口所用的斜杠前缀，故此处须使用 command_prefix，
    若改用当前会话的前缀，回流的命令将匹配不到前缀而被丢弃。

    :return: 按钮数据，键为按钮文本，值为点击后发出的命令。
    """
    return arrange_buttons([(name, f"{command_prefix[0]}wiki set {url}") for name, url in RECOMMENDED_WIKIS])


async def finish_with_start_wiki_not_set(msg: Bot.MessageSession) -> NoReturn:
    """
    提示当前场景尚未设置起始 Wiki 并终结会话。

    在支持按钮的平台上，额外为具备设置权限的用户附上推荐 Wiki 的按钮。
    按钮回流后走完整的命令解析流程，权限由 wiki set 命令自身再次校验。

    :param msg: 消息会话对象。
    """
    prompts = [
        I18NContext(
            "wiki.message.set.not_set",
            prefix=msg.session_info.prefixes[0],
            cmd=ActionText(f"{msg.session_info.prefixes[0]}wiki set"),
        )
    ]
    button_data = []
    if RECOMMENDED_WIKIS and msg.session_info.support_button and await msg.check_permission():
        prompts.append(I18NContext("wiki.message.set.not_set.recommend"))
        button_data = get_recommend_button_data()
    await msg.finish(prompts, button_data=button_data)
