import re

from core.logger import Logger
from core.utils.i18n import Locale
from modules.wiki import query_pages
from modules.wiki.utils.wikilib import QueryInfo


async def moegirl(term: str, locale: Locale):
    result = await query_pages(QueryInfo('https://zh.moegirl.org.cn/api.php', headers={'accept': '*/*',
                                                                                       'accept-encoding': 'gzip, deflate',
                                                                                       'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,en-GB;q=0.6',
                                                                                       'content-type': 'application/json',
                                                                                       'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62'},
                                         locale=locale.locale),
                               term)
    msg = ''
    if result['msg_list']:
        for msg_item in result['msg_list']:
            msg += msg_item.text
    if result['wait_msg_list']:
        for msg_item in result['wait_msg_list']:
            Logger.debug('msg_item.text: ', msg_item.text)
            redirect = re.search(
                r'(?<=是：\[)(.*?)(?=\]。)', msg_item.text).group(0)
            Logger.debug(redirect)
            if redirect:
                wait = await query_pages(QueryInfo('https://zh.moegirl.org.cn/api.php', headers={'accept': '*/*',
                                                                                                 'accept-encoding': 'gzip, deflate',
                                                                                                 'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,en-GB;q=0.6',
                                                                                                 'content-type': 'application/json',
                                                                                                 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62'
                                                                                                 },
                                                   locale=locale.locale), redirect)
                msg += wait['msg_list'][0].text

    return f'[{locale.t("meme.message.moegirl")}] {msg}'
