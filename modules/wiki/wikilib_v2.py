import datetime
import traceback
from typing import Union, Dict, List

import html2text
import ujson as json
import re
import urllib.parse

from core.logger import Logger
from core.utils import get_url
from core.dirty_check import check

from .dbutils import WikiSiteInfo as DBSiteInfo
from .audit import check_whitelist


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
                 namespaces_local: dict,
                 in_whitelist: bool):
        self.api = api
        self.articlepath = articlepath
        self.extensions = extensions
        self.interwiki = interwiki
        self.realurl = realurl
        self.name = name
        self.namespaces = namespaces
        self.namespaces_local = namespaces_local
        self.in_whitelist = in_whitelist


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
                 status: bool = True,
                 before_page_property: str = 'page',
                 page_property: str = 'page',
                 invalid_namespace: bool = False
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
        self.before_page_property = before_page_property
        self.page_property = page_property
        self.invalid_namespace = invalid_namespace


class WikiLib:
    def __init__(self, url: str, headers=None):
        self.url = url
        self.wiki_info = WikiInfo(api='', articlepath='', extensions=[], interwiki={}, realurl='', name='',
                                  namespaces=[], namespaces_local={}, in_whitelist=False)
        self.headers = headers

    async def get_json(self, api, **kwargs) -> dict:
        if kwargs is not None:
            api = api + '?' + urllib.parse.urlencode(kwargs)
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
        api_url = real_url + info['query']['general']['scriptpath'] + '/api.php'
        return WikiInfo(articlepath=real_url + info['query']['general']['articlepath'],
                        extensions=ext_list,
                        name=info['query']['general']['sitename'],
                        realurl=real_url,
                        api=api_url,
                        namespaces=namespaces,
                        namespaces_local=namespaces_local,
                        interwiki=interwiki_dict,
                        in_whitelist=check_whitelist(api_url))

    async def check_wiki_available(self):
        try:
            api_match = re.match(r'(https?://.*?/api.php$)', self.url)
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
                    message = '服务器拒绝了机器人的请求。'
                elif not re.match(r'^(https?://).*', self.url):
                    message = '所给的链接没有指明协议头（链接应以http://或https://开头）。'
                else:
                    message = '此站点也许不是一个有效的Mediawiki：' + str(e)
                if self.url.find('moegirl.org.cn') != -1:
                    message += '\n萌娘百科的api接口不稳定，请稍后再试或直接访问站点。'
                return WikiStatus(available=False, value=False, message=message)
        get_cache_info = DBSiteInfo(wiki_api_link).get()
        if get_cache_info and datetime.datetime.now().timestamp() - get_cache_info[1].timestamp() < 43200:
            return WikiStatus(available=True,
                              value=self.rearrange_siteinfo(get_cache_info[0]),
                              message='')
        try:
            get_json = await self.get_json(wiki_api_link,
                                           action='query',
                                           meta='siteinfo',
                                           siprop='general|namespaces|namespacealiases|interwikimap|extensions',
                                           format='json')
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
        get_parse = await self.get_json(self.wiki_info.api,
                                        action='parse',
                                        page=page_name,
                                        prop='text',
                                        format='json')
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        h.ignore_tables = True
        return h.handle(get_parse['parse']['text']['*'])

    async def get_wikitext(self, page_name):
        await self.fixup_wiki_info()
        try:
            load_desc = await self.get_json(self.wiki_info.api,
                                            action='parse',
                                            page=page_name,
                                            prop='wikitext',
                                            format='json')
            desc = load_desc['parse']['wikitext']['*']
        except Exception:
            traceback.print_exc()
            desc = ''
        return desc

    async def research_page(self, page_name: str):
        await self.fixup_wiki_info()
        get_page = await self.get_json(self.wiki_info.api,
                                       action='query',
                                       list='search',
                                       srsearch=page_name,
                                       srwhat='text',
                                       srlimit='1',
                                       srenablerewrites=True,
                                       format='json')
        new_page_name = get_page['query']['search'][0]['title'] if len(get_page['query']['search']) > 0 else None
        title_split = page_name.split(':')
        print(title_split, len(title_split))
        is_invalid_namespace = False
        if len(title_split) > 1 and title_split[0] not in self.wiki_info.namespaces:
            is_invalid_namespace = True
        return new_page_name, is_invalid_namespace

    async def parse_page_info(self, title: str, doc_mode=False,
                              tried_iw=0, iw_prefix='') -> PageInfo:
        await self.fixup_wiki_info()
        if tried_iw > 5:
            raise WhatAreUDoingError
        split_name = re.split(r'([#?])', title)
        title = re.sub('_', ' ', split_name[0])
        arg_list = []
        quote_code = False
        for a in split_name[1:]:
            if a[0] == '#':
                quote_code = True
            if a[0] == '?':
                quote_code = False
            if quote_code:
                arg_list.append(urllib.parse.quote(a))
            else:
                arg_list.append(a)
        page_info = PageInfo(info=self.wiki_info, title=title, args=''.join(arg_list), interwiki_prefix=iw_prefix)
        query_string = {'action': 'query', 'format': 'json', 'prop': 'info|imageinfo', 'inprop': 'url', 'iiprop': 'url',
                        'redirects': 'True', 'titles': title}
        use_textextracts = True if 'TextExtracts' in self.wiki_info.extensions else False
        if use_textextracts:
            query_string.update({'prop': 'info|imageinfo|extracts',
                                 'ppprop': 'description|displaytitle|disambiguation|infoboxes', 'explaintext': 'true',
                                 'exsectionformat': 'plain', 'exchars': '200'})
        get_page = await self.get_json(self.wiki_info.api, **query_string)
        query = get_page.get('query')
        redirects_: List[Dict[str, str]] = query.get('redirects')
        if redirects_ is not None:
            for r in redirects_:
                if r['from'] == title:
                    page_info.before_title = r['from']
                    page_info.title = r['to']
        normalized_: List[Dict[str, str]] = query.get('normalized')
        if normalized_ is not None:
            for n in normalized_:
                if n['from'] == title:
                    page_info.before_title = n['from']
                    page_info.title = n['to']
        pages: Dict[str, dict] = query.get('pages')
        if pages is not None:
            for page_id in pages:
                page_raw = pages[page_id]
                title = page_raw['title']
                if int(page_id) < 0:
                    if 'missing' not in page_raw or 'known' in page_raw:
                        full_url = re.sub(r'\$1', urllib.parse.quote(title.encode('UTF-8')), self.wiki_info.articlepath) \
                                   + page_info.args
                        page_info.link = full_url
                    else:
                        split_title = title.split(':')
                        if len(split_title) > 1 and split_title[0] in self.wiki_info.namespaces_local \
                                and self.wiki_info.namespaces_local[split_title[0]] == 'Template':
                            rstitle = ':'.join(split_title[1:]) + page_info.args
                            research = await self.parse_page_info(rstitle)
                            page_info.title = research.title
                            page_info.link = research.link
                            page_info.desc = research.desc
                            page_info.file = research.file
                            page_info.before_title = title
                            page_info.before_page_property = 'template'
                            page_info.status = research.status
                        else:
                            research = await self.research_page(title)
                            page_info.title = research[0]
                            page_info.before_title = title
                            page_info.invalid_namespace = research[1]
                            page_info.status = False
                else:
                    page_desc = ''
                    split_title = title.split(':')
                    get_desc = True
                    if not doc_mode and len(split_title) > 1 and split_title[0] in self.wiki_info.namespaces_local \
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
                            page_desc = get_doc_desc.desc
                            page_info.before_page_property = page_info.page_property = 'template'
                    if get_desc:
                        if use_textextracts:
                            raw_desc = page_raw.get('extract')
                            if raw_desc is not None:
                                page_desc = self.parse_text(raw_desc)
                        else:
                            page_desc = self.parse_text(await self.get_html_to_text(title))
                    full_url = page_raw['fullurl'] + page_info.args
                    file = None
                    if 'imageinfo' in page_raw:
                        file = page_raw['imageinfo'][0]['url']
                    page_info.title = title
                    page_info.link = full_url
                    page_info.file = file
                    page_info.desc = page_desc
        interwiki_: List[Dict[str, str]] = query.get('interwiki')
        if interwiki_ is not None:
            for i in interwiki_:
                if i['title'] == title:
                    iw_title = re.match(r'^' + i['iw'] + ':(.*)', i['title'])
                    iw_title = iw_title.group(1) + page_info.args
                    iw_prefix += i['iw'] + ':'
                    iw_query = await WikiLib(url=self.wiki_info.interwiki[i['iw']]).parse_page_info(iw_title,
                                                                                                    tried_iw=tried_iw + 1,
                                                                                                    iw_prefix=iw_prefix)
                    page_info = iw_query
                    page_info.before_title = title

                    t = page_info.title
                    if tried_iw == 0:
                        page_info.title = page_info.interwiki_prefix + t
        if not self.wiki_info.in_whitelist:
            checklist = []
            if page_info.title is not None:
                checklist.append(page_info.title)
            if page_info.before_title is not None:
                checklist.append(page_info.before_title)
            if page_info.desc is not None:
                checklist.append(page_info.desc)
            chk = await check(*checklist)
            for x in chk:
                print(x)
                if x.find("<吃掉了>") != -1 or x.find("<全部吃掉了>") != -1:
                    page_info.status = True
                    page_info.before_title = '?'
                    page_info.title = '¿'
                    page_info.link = 'https://wdf.ink/6OUp'
        return page_info
