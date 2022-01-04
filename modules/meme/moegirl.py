from core.exceptions import AbuseWarning
from modules.wiki import query_pages
from modules.wiki.wikilib_v2 import QueryInfo


async def moegirl(term: str):
    result = await query_pages(QueryInfo('https://zh.moegirl.org.cn/api.php'), term)
    msg = ''
    if result['msg_list']:
        for msg_item in result['msg_list']:
            msg += msg_item.text
    if result['wait_msg_list']:
        for msg_item in result['wait_msg_list']:
            msg += msg_item.text
    return '[萌娘百科]' + msg
