"""超级用户命令使用的 ToS 管理门面。"""

from core.builtins.bot import Bot

from modules.core.hooks.tos import check_temp_ban, remove_temp_ban


async def check_temp_ban_for_admin(user: str):
    """优先通过具名 hook 查询临时封禁，兼容未加载 hook 的本地调用。"""
    try:
        return await Bot.Hook.trigger("tos.check_temp_ban", args={"target": user})
    except ValueError:
        return await check_temp_ban(user)


async def remove_temp_ban_for_admin(user: str):
    """优先通过具名 hook 移除临时封禁，兼容未加载 hook 的本地调用。"""
    try:
        return await Bot.Hook.trigger("tos.remove_temp_ban", args={"target": user})
    except ValueError:
        return await remove_temp_ban(user)
