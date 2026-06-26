from core.builtins.bot import Bot
from core.builtins.message.internal import Plain, I18NContext, Url
from core.dirty_check import rickroll
from core.utils.http import get_url
from modules.github.utils import dirty_check, dark_check

SEARCH_LIMIT = 5


async def search(msg: Bot.MessageSession, keyword: str, pat: str):
    result = await get_url(
        f"https://api.github.com/search/repositories?q={keyword}",
        200,
        fmt="json",
        headers={"Authorization": f"Bearer {pat}"} if pat else {},
    )
    if result.get("total_count", 0) == 0:
        message = str(I18NContext("github.message.search.not_found"))
    else:
        items = result.get("items", [])
        items_out = []
        for item in items:
            try:
                items_out.append(str(item.get("full_name", "") + ": " + str(Url(item.get("html_url", "")))))
            except TypeError:
                continue
        message = str(I18NContext("github.message.search")) + "\n" + "\n".join(items_out[0:SEARCH_LIMIT])
        if result.get("total_count", 0) > 5:
            message += "\n" + str(I18NContext("message.collapse", amount=SEARCH_LIMIT))

    is_dirty = await dirty_check(msg, message) or dark_check(message)
    if is_dirty:
        await msg.finish(rickroll())

    await msg.finish(Plain(message))
