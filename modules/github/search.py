import traceback

from core.builtins import Bot, Url
from core.dirty_check import rickroll
from core.utils.http import get_url
from modules.github.utils import dirty_check, darkCheck


async def search(msg: Bot.MessageSession, keyword: str):
    try:
        result = await get_url('https://api.github.com/search/repositories?q=' + keyword, 200,
                               fmt='json')
        if result['total_count'] == 0:
            message = msg.locale.t("github.message.search.none")
        else:
            items = result['items']
            item_count_expected = int(result['total_count']) if result['total_count'] < 5 else 5
            items_out = []
            for item in items:
                try:
                    items_out.append(str(item['full_name'] + ': ' + str(Url(item['html_url']))))
                except TypeError:
                    continue
            footnotes = msg.locale.t(
                "github.message.search.more_information",
                more_result=result['total_count'] -
                5) if item_count_expected == 5 else ''
            message = msg.locale.t("github.message.search", result=result['total_count']) + '\n' + '\n'.join(
                items_out[0:item_count_expected]) + f'\n{footnotes}'

        is_dirty = await dirty_check(message) or darkCheck(message)
        if is_dirty:
            await msg.finish(rickroll(msg))

        await msg.finish(message)
    except BaseException:
        traceback.print_exc()
