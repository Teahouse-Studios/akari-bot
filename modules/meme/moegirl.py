from modules.wiki import query_pages
from modules.wiki.wikilib_v2 import QueryInfo


async def moegirl(term: str):
    result = await query_pages(QueryInfo('https://zh.moegirl.org.cn/api.php', headers={'accept': '*/*',
            'accept-encoding': 'gzip, deflate',
            'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,en-GB;q=0.6',
            'content-type': 'application/json',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62'}), term)
    msg = ''
    if result['msg_list']:
        for msg_item in result['msg_list']:
            msg += msg_item.text
    if result['wait_msg_list']:
        for msg_item in result['wait_msg_list']:
            msg += msg_item.text
    return '[萌娘百科]' + msg
