import traceback

from core.elements import MessageSession
from modules.github.utils import query, dirty_check, darkCheck


async def search(msg: MessageSession):
    try:
        result = await query('https://api.github.com/search/repositories?q=' + msg.parsed_msg['<query>'], 'json')
        items = result['items']
        item_count_expected = int(result['total_count']) if result['total_count'] < 5 else 5
        items_out = []
        for item in items:
            try:
                items_out.append(str(item['full_name'] + ': ' + item['html_url']))
            except TypeError:
                continue
        footnotes = f"另有 {result['total_count'] - 5} 个结果未显示。" if item_count_expected == 5 else ''
        message = f"搜索成功：共 {result['total_count']} 个结果。\n" + '\n'.join(
            items_out[0:item_count_expected]) + f'\n{footnotes}'

        is_dirty = await dirty_check(message) or await darkCheck(message)
        if is_dirty:
            message = 'https://wdf.ink/6OUp'

        await msg.sendMessage(message)
    except Exception as error:
        await msg.sendMessage('发生错误：' + str(
            error) + '\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title=')
        traceback.print_exc()
