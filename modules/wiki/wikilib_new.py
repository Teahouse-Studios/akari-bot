import datetime
import functools
import traceback
from typing import Union, Dict, List
from string import Template as StrTemplate

import html2text
import ujson as json
import re
import urllib.parse

from core.logger import Logger
from core.utils import get_url
from modules.wiki.dbutils import WikiSiteInfo as DBSiteInfo


class InvalidPageIDError(Exception):
    pass


class InvalidWikiError(Exception):
    pass


class DangerousContentError(Exception):
    pass


class PageNotFound(Exception):
    pass


class WhatAreUDoingError(Exception):
    pass


class WikiInfo:
    def __init__(self,
                 api: str,
                 articlepath: str,
                 extensions: list,
                 interwiki: dict,
                 realurl: str,
                 name: str,
                 namespaces: list,
                 namespaces_local: dict):
        self.api = api
        self.articlepath = articlepath
        self.extensions = extensions
        self.interwiki = interwiki
        self.realurl = realurl
        self.name = name
        self.namespaces = namespaces
        self.namespaces_local = namespaces_local


class WikiStatus:
    def __init__(self,
                 available: bool,
                 value: Union[WikiInfo, bool],
                 message: str):
        self.available = available
        self.value = value
        self.message = message


class PageInfo:
    def __init__(self,
                 info: WikiInfo,
                 title: str,
                 before_title: str = None,
                 link: str = None,
                 file: str = None,
                 desc: str = None,
                 args: str = None,
                 interwiki_prefix: str = '',
                 status: bool = True
                 ):
        self.info = info
        self.title = title
        self.before_title = before_title
        self.link = link
        self.file = file
        self.desc = desc
        self.args = args
        self.interwiki_prefix = interwiki_prefix
        self.status = status


class WikiLib:
    def __init__(self, url, headers=None):
        self.url = url
        self.wiki_info = WikiInfo(api='', articlepath='', extensions=[], interwiki={}, realurl='', name='',
                                  namespaces=[], namespaces_local={})
        self.headers = headers

    @staticmethod
    def encode_query_string(kwargs: dict):
        return urllib.parse.urlencode(kwargs)

    async def get_json(self, api, args: dict = None) -> dict:
        if args is not None:
            api = api + '?' + self.encode_query_string(args)
        return await get_url(api, status_code=200, headers=self.headers, fmt="json")

    def rearrange_siteinfo(self, info: Union[dict, str]) -> WikiInfo:
        if isinstance(info, str):
            info = json.loads(info)
        extensions = info['query']['extensions']
        ext_list = []
        for ext in extensions:
            ext_list.append(ext['name'])
        real_url = info['query']['general']['server']
        if real_url.startswith('//'):
            real_url = self.url.split('//')[0] + real_url
        namespaces = []
        namespaces_local = {}
        for x in info['query']['namespaces']:
            try:
                ns = info['query']['namespaces'][x]
                if '*' in ns:
                    namespaces.append(ns['*'])
                if 'canonical' in ns:
                    namespaces.append(ns['canonical'])
                if '*' in ns and 'canonical' in ns:
                    namespaces_local.update({ns['*']: ns['canonical']})
            except Exception:
                traceback.print_exc()
        for x in info['query']['namespacealiases']:
            if '*' in x:
                namespaces.append(x['*'])
        interwiki_map = info['query']['interwikimap']
        interwiki_dict = {}
        for interwiki in interwiki_map:
            interwiki_dict[interwiki['prefix']] = interwiki['url']

        return WikiInfo(articlepath=real_url + info['query']['general']['articlepath'],
                        extensions=ext_list,
                        name=info['query']['general']['sitename'],
                        realurl=real_url,
                        api=real_url + info['query']['general']['scriptpath'] + '/api.php',
                        namespaces=namespaces,
                        namespaces_local=namespaces_local,
                        interwiki=interwiki_dict)

    async def check_wiki_available(self):
        query_string = {'action': 'query', 'meta': 'siteinfo',
                        'siprop': 'general|namespaces|namespacealiases|interwikimap|extensions', 'format': 'json'}
        try:
            api_match = re.match(r'(https?://.*?/url.php$)', self.url)
            wiki_api_link = api_match.group(1)
        except Exception:
            try:
                get_page = await get_url(self.url, fmt='text', headers=self.headers)
                if get_page.find('<title>Attention Required! | Cloudflare</title>') != -1:
                    return WikiStatus(available=False, value=False, message='CloudFlare拦截了机器人的请求，请联系站点管理员解决此问题。')
                m = re.findall(
                    r'(?im)<\s*link\s*rel="EditURI"\s*type="application/rsd\+xml"\s*href="([^>]+?)\?action=rsd"\s*/\s*>',
                    get_page)
                api_match = m[0]
                if api_match.startswith('//'):
                    api_match = self.url.split('//')[0] + api_match
                Logger.info(api_match)
                wiki_api_link = api_match
            except TimeoutError:
                return WikiStatus(available=False, value=False, message='错误：尝试建立连接超时。')
            except Exception as e:
                traceback.print_exc()
                if e.args == (403,):
                    return WikiStatus(available=False, value=False, message='服务器拒绝了机器人的请求。')
                elif not re.match(r'^(https?://).*', self.url):
                    return WikiStatus(available=False, value=False, message='所给的链接没有指明协议头（链接应以http://或https://开头）。')
                else:
                    return WikiStatus(available=False, value=False, message='此站点也许不是一个有效的Mediawiki：' + str(e))
        get_cache_info = DBSiteInfo(wiki_api_link).get()
        if get_cache_info and datetime.datetime.now().timestamp() - get_cache_info[1].timestamp() < 43200:
            return WikiStatus(available=True,
                              value=self.rearrange_siteinfo(get_cache_info),
                              message='')
        try:
            get_json = await self.get_json(wiki_api_link, query_string)
        except Exception as e:
            return WikiStatus(available=False, value=False, message='从API获取信息时出错：' + str(e))
        DBSiteInfo(wiki_api_link).update(get_json)
        info = self.rearrange_siteinfo(get_json)
        return WikiStatus(available=True, value=info,
                          message='警告：此wiki没有启用TextExtracts扩展，返回的页面预览内容将为未处理的原始Wikitext文本。'
                          if 'TextExtracts' not in info.extensions else '')

    async def fixup_wiki_info(self):
        if self.wiki_info.api == '':
            wiki_info = await self.check_wiki_available()
            if wiki_info.available:
                self.wiki_info = wiki_info.value
            else:
                raise InvalidWikiError(wiki_info.message if wiki_info.message != '' else '')

    @staticmethod
    def parse_text(text):
        try:
            desc = text.split('\n')
            desc_list = []
            for x in desc:
                if x != '':
                    desc_list.append(x)
            desc = '\n'.join(desc_list)
            desc_end = re.findall(r'(.*?(?:!\s|\?\s|\.\s|！|？|。)).*', desc, re.S | re.M)
            if desc_end:
                desc = desc_end[0]
        except Exception:
            traceback.print_exc()
            desc = ''
        if desc in ['...', '…']:
            desc = ''
        ell = False
        if len(desc) > 250:
            desc = desc[0:250]
            ell = True
        split_desc = desc.split('\n')
        for d in split_desc:
            if d == '':
                split_desc.remove('')
        if len(split_desc) > 5:
            split_desc = split_desc[0:5]
            ell = True
        return '\n'.join(split_desc) + ('...' if ell else '')

    async def get_html_to_text(self, page_name):
        await self.fixup_wiki_info()
        query_string = {'action': 'parse', 'page': page_name, 'prop': 'text',
                        'format': 'json'}
        get_parse = await self.get_json(self.wiki_info.api, query_string)
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        h.ignore_tables = True
        return h.handle(get_parse['parse']['text']['*'])

    async def get_wikitext(self, page_name):
        await self.fixup_wiki_info()
        try:
            query_string = {'action': 'parse', 'page': page_name, 'prop': 'wikitext', 'format': 'json'}
            load_desc = await self.get_json(self.wiki_info.api, query_string)
            desc = load_desc['parse']['wikitext']['*']
        except Exception:
            traceback.print_exc()
            desc = ''
        return desc

    async def research_page(self, page_name: str):
        await self.fixup_wiki_info()
        query_string = {'action': 'query', 'list': 'search', 'srsearch': page_name, 'srwhat': 'text',
                        'srlimit': '1', 'srenablerewrites': '', 'format': 'json'}
        get_page = await self.get_json(self.wiki_info.api, query_string)
        new_page_name = get_page['query']['search'][0]['title'] if len(get_page['query']['search']) > 0 else None
        prompt = ''
        title_split = page_name.split(':')
        if title_split[0] not in self.wiki_info.namespaces:
            prompt += f'\n提示：此Wiki上找不到“{title_split[0]}”名字空间，请检查是否设置了对应的Interwiki（使用~wiki iw list命令可以查询当前已设置的Interwiki）。'
        return new_page_name, prompt

    async def parse_page_info(self, title: Union[str, list, tuple, dict], doc_mode=False,
                              tried_iw=0) -> Dict[str, PageInfo]:
        await self.fixup_wiki_info()
        if tried_iw > 5:
            raise WhatAreUDoingError
        if isinstance(title, (str, list, tuple)):
            if isinstance(title, str):
                title = [title]
            query_list: Dict[str, PageInfo] = {}
            for t in title:
                split_name = re.split(r'([#?])', t)
                title = re.sub('_', ' ', split_name[0])
                query_list.update({title: PageInfo(info=self.wiki_info, title=title,
                                                   args=''.join(split_name[1:]) if len(split_name) > 1 else None)})
        else:
            query_list = title
        query_string = {'action': 'query', 'format': 'json', 'prop': 'info|imageinfo', 'inprop': 'url', 'iiprop': 'url',
                        'redirects': 'True', 'titles': '|'.join(query_list[n].title for n in query_list)}
        use_textextracts = True if 'TextExtracts' in self.wiki_info.extensions else False
        if use_textextracts:
            query_string.update({'prop': 'info|imageinfo|extracts',
                                 'ppprop': 'description|displaytitle|disambiguation|infoboxes', 'explaintext': 'true',
                                 'exsectionformat': 'plain', 'exchars': '200'})
        get_page = await self.get_json(self.wiki_info.api, query_string)
        query = get_page.get('query')
        if query is None:
            return {}
        redirects_ = query.get('redirects')
        redirects = {}
        if redirects_ is not None:
            for r in redirects_:
                redirects[r['to']] = r['from']
        for x in query_list:
            if query_list[x].before_title is not None:
                redirects[query_list[x].title] = query_list[x].before_title
        normalized_ = query.get('normalized')
        if normalized_ is not None:
            for n in normalized_:
                redirects[n['to']] = n['from']
        interwiki_ = query.get('interwiki')
        interwiki = {}
        if interwiki_ is not None:
            for i in interwiki_:
                iw_title = re.match(r'^' + i['iw'] + ':(.*)', i['title'])
                query_iw = query_list[i['title']]
                query_iw.title = iw_title.group(1)
                query_iw.before_title = i['title']
                query_iw.interwiki_prefix += i['iw'] + ':'
                if i['iw'] not in interwiki:
                    interwiki[i['iw']] = {}
                interwiki[i['iw']].update({i['title']: query_iw})
        pages = query.get('pages')
        if pages is not None:
            for page_id in pages:
                page_raw = pages[page_id]
                title = page_raw['title']
                before_page_title = redirects.get(title)
                page_args = query_list.get(before_page_title).args if before_page_title is not None \
                    else query_list.get(title).args
                set_query = query_list[before_page_title if before_page_title is not None else title]
                if int(page_id) < 0:
                    if 'missing' not in page_raw:
                        full_url = re.sub(r'\$1', urllib.parse.quote(title.encode('UTF-8')), self.wiki_info.articlepath)\
                                   + (page_args if page_args is not None else '')
                        set_query.title = title
                        set_query.before_title = before_page_title
                        set_query.link = full_url
                    else:
                        research = await self.research_page(title)
                        set_query.title = research[0]
                        set_query.before_title = title
                        set_query.desc = research[1]
                        set_query.status = False
                else:
                    page_desc = ''
                    split_title = title.split(':')
                    get_desc = True
                    if not doc_mode and len(split_title) > 1 and split_title in self.wiki_info.namespaces_local \
                            and self.wiki_info.namespaces_local[split_title[0]] == 'Template':
                        get_all_text = await self.get_wikitext(title)
                        match_doc = re.match(r'.*{{documentation\|?(.*?)}}.*', get_all_text, re.I | re.S)
                        if match_doc:
                            match_link = re.match(r'link=(.*)', match_doc.group(1), re.I | re.S)
                            if match_link:
                                get_doc = match_link.group(1)
                            else:
                                get_doc = title + '/doc'
                            get_desc = False
                            get_doc_desc = await self.parse_page_info(get_doc, doc_mode=True)
                            page_desc = get_doc_desc[get_doc].desc
                    if get_desc:
                        if use_textextracts:
                            raw_desc = page_raw.get('extract')
                            if raw_desc is not None:
                                page_desc = self.parse_text(raw_desc)
                        else:
                            page_desc = self.parse_text(await self.get_html_to_text(title))
                    full_url = page_raw['fullurl'] + (page_args if page_args is not None else '')
                    file = ''
                    if 'imageinfo' in page_raw:
                        file = page_raw['imageinfo'][0]['url']
                    set_query.title = title
                    set_query.before_title = before_page_title
                    set_query.link = full_url
                    set_query.file = file
                    set_query.desc = page_desc
        if interwiki != {}:
            for i in interwiki:
                iw_url = re.sub(r'\$1', '', self.wiki_info.interwiki[i])
                parse_page = await WikiLib(url=iw_url, headers=self.headers).parse_page_info(interwiki[i],
                                                                                             tried_iw=tried_iw + 1)
                query_list.update(parse_page)
        return query_list
