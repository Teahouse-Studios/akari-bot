from core.exceptions import AbuseWarning
from modules.wiki.wikilib_v2 import WikiLib, WhatAreUDoingError, PageInfo, InvalidWikiError

async def moegirl(term: str):
    try:
        result = await WikiLib('https://zh.moegirl.org.cn/api.php').parse_page_info(term)
        r: PageInfo = result
        display_title = None
        display_before_title = None
        if r.title is not None:
            display_title = r.title
        if r.before_title is not None:
            display_before_title = r.before_title
        if r.status:
            plain_slice = []
            if display_before_title is not None and display_before_title != display_title:
                if r.before_page_property == 'template' and r.page_property == 'page':
                    plain_slice.append(f'（[{display_before_title}]不存在，已自动重定向至[{display_title}]）')
                else:
                    plain_slice.append(f'（重定向[{display_before_title}] -> [{display_title}]）')
            if r.link is not None:
                plain_slice.append(r.link)
            if r.desc is not None and r.desc != '':
                plain_slice.append(r.desc)
        else:
            plain_slice = []
            wait_plain_slice = []
            if display_title is not None and display_before_title is not None:
                wait_plain_slice.append(f'提示：[{display_before_title}]不存在，您是否想要找的是[{display_title}]？')
            elif r.before_title is not None:
                plain_slice.append(f'提示：找不到[{display_before_title}]。')
            if r.desc is not None and r.desc != '':
                plain_slice.append(r.desc)
            if r.invalid_namespace and r.before_title is not None:
                s = r.before_title.split(":")
                if len(s) > 1:
                    plain_slice.append(f'此Wiki上没有名为{s[0]}的命名空间，请检查拼写后再试。')
            if wait_plain_slice:
                page = '\n'.join(wait_plain_slice)
    except WhatAreUDoingError:
        raise AbuseWarning('使机器人重定向页面的次数过多。')
    return '[萌娘百科]' + page
