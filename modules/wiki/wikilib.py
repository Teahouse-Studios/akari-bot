import asyncio
import datetime
import re
import traceback
import urllib.parse

import aiohttp
import html2text
import ujson as json

from core import dirty_check
from core.logger import Logger
from modules.wiki.dbutils import WikiSiteInfo


class wikilib:
    async def get_data(self, url: str, fmt: str, headers=None, ignore_err=False):
        print(url)
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                if req.status == 200 or ignore_err:
                    if fmt == 'json':
                        try:
                            return json.loads(await req.text())
                        except UnicodeDecodeError:
                            traceback.print_exc()
                            return json.loads(await req.text(encoding='unicode-escape'))
                    else:
                        try:
                            return await req.text()
                        except UnicodeDecodeError:
                            traceback.print_exc()
                            return await req.text(encoding='unicode-escape')
                else:
                    raise ValueError(req.status)

    def encode_query_string(self, kwargs: dict):
        return '?' + urllib.parse.urlencode(kwargs)

    async def check_wiki_available(self, link, headers=None):
        query_string = {'action': 'query', 'meta': 'siteinfo',
                        'siprop': 'general|namespaces|namespacealiases|interwikimap|extensions', 'format': 'json'}
        query = self.encode_query_string(query_string)
        try:
            api = re.match(r'(https?://.*?/api.php$)', link)
            wlink = api.group(1)
            json1 = json.loads(await self.get_data(api.group(1) + query, 'json', headers=headers))
            getcacheinfo = WikiSiteInfo(wlink).get()
            if getcacheinfo and datetime.datetime.now().timestamp() - getcacheinfo[1].timestamp() < 43200:
                return wlink, json.loads(getcacheinfo[0])['query']['general']['sitename']
        except:
            try:
                getpage = await self.get_data(link, 'text', headers=headers, ignore_err=True)
                if getpage.find('<title>Attention Required! | Cloudflare</title>') != -1:
                    return False, 'CloudFlare拦截了机器人的请求，请联系站点管理员解决此问题。'
                m = re.findall(
                    r'(?im)<\s*link\s*rel="EditURI"\s*type="application/rsd\+xml"\s*href="([^>]+?)\?action=rsd"\s*/\s*>',
                    getpage)
                api = m[0]
                if api.startswith('//'):
                    api = link.split('//')[0] + api
                Logger.info(api)
                getcacheinfo = WikiSiteInfo(api).get()
                if getcacheinfo and datetime.datetime.now().timestamp() - getcacheinfo[1].timestamp() < 43200:
                    return api, json.loads(getcacheinfo[0])['query']['general']['sitename']
                json1 = await self.get_data(api + query, 'json', headers=headers)
                wlink = api
            except TimeoutError:
                traceback.print_exc()
                return False, '错误：尝试建立连接超时。'
            except Exception as e:
                traceback.print_exc()
                if e.args == (403,):
                    return False, '服务器拒绝了机器人的请求。'
                elif not re.match(r'^(https?://).*', link):
                    return False, '所给的链接没有指明协议头（链接应以http://或https://开头）。'
                else:
                    return False, '此站点也许不是一个有效的Mediawiki：' + str(e)
        WikiSiteInfo(wlink).update(json1)
        wikiname = json1['query']['general']['sitename']
        extensions = json1['query']['extensions']
        extlist = []
        for ext in extensions:
            extlist.append(ext['name'])
        if 'TextExtracts' not in extlist:
            wikiname = wikiname + '\n警告：此wiki没有启用TextExtracts扩展，返回的页面预览内容将为未处理的原始Wikitext文本。'

        return wlink, wikiname

    def danger_wiki_check(self):
        if self.wiki_api_endpoint.upper().find('WIKIPEDIA') != -1:
            return True
        if self.wiki_api_endpoint.upper().find('UNCYCLOPEDIA') != -1:
            return True
        if self.wiki_api_endpoint.upper().find('HMOEGIRL') != -1:
            return True
        if self.wiki_api_endpoint.upper().find('EVCHK') != -1:
            return True
        if self.wiki_api_endpoint.upper().find('HONGKONG.FANDOM') != -1:
            return True
        if self.wiki_api_endpoint.upper().find('WIKILEAKS') != -1:
            return True
        if self.wiki_api_endpoint.upper().find('NANFANGGONGYUAN') != -1:
            return True
        return False

    async def danger_text_check(self, text):
        if not self.danger_wiki_check():
            return False
        check = await dirty_check.check(text)
        for x in check:
            if not x['status']:
                return True
        return False

    async def random_page(self, url, iw=None, headers=None):
        query_string = {'action': 'query',
                        'list': 'random',
                        'format': 'json'}
        random_url = url + self.encode_query_string(query_string)
        json = await self.get_data(random_url, 'json')
        randompage = json['query']['random'][0]['title']
        return await self.main(url, randompage, interwiki=iw, headers=headers)

    async def get_wiki_info(self, url=None):
        url = url if url is not None else self.wiki_api_endpoint
        getcacheinfo = WikiSiteInfo(url).get()
        if getcacheinfo and datetime.datetime.now().timestamp() - getcacheinfo[1].timestamp() < 43200:
            return json.loads(getcacheinfo[0])
        query_string = {'action': 'query', 'meta': 'siteinfo',
                        'siprop': 'general|namespaces|namespacealiases|interwikimap|extensions', 'format': 'json'}
        wiki_info_url = url + self.encode_query_string(query_string)
        j = await self.get_data(wiki_info_url, 'json')
        WikiSiteInfo(url).update(j)
        return j

    async def get_interwiki(self, url=None, iw=None):
        print(url)
        if url is None:
            json = self.wiki_info
        else:
            json = await self.get_wiki_info(url)
        interwikimap = json['query']['interwikimap']
        interwiki_dict = {}
        if iw is None:
            for interwiki in interwikimap:
                interwiki_dict[interwiki['prefix']] = re.sub(r'\$1$', '', interwiki['url'])
        else:
            if iw in interwikimap:
                interwiki_dict[iw] = interwikimap[iw]['url']
        return interwiki_dict

    async def get_namespace(self, url=None):
        if url is None:
            j = self.wiki_info
        else:
            j = await self.get_wiki_info(url)
        d = {}
        for x in j['query']['namespaces']:
            try:
                d[j['query']['namespaces'][x]['*']] = j['query']['namespaces'][x]['canonical']
            except KeyError:
                pass
            except:
                traceback.print_exc()
        for x in j['query']['namespacealiases']:
            try:
                d[x['*']] = 'aliases'
            except KeyError:
                pass
            except:
                traceback.print_exc()
        return d

    async def get_article_path(self, url=None):
        if url is None:
            wiki_info = self.wiki_info
            url = self.wiki_api_endpoint
        else:
            wiki_info = await self.get_wiki_info(url)
            if not wiki_info:
                return False
        article_path = wiki_info['query']['general']['articlepath']
        article_path = re.sub(r'\$1$', '', article_path)
        print(url)
        base_url = re.match(r'(https?://.*?)/.*', url)
        return base_url.group(1) + article_path

    async def get_enabled_extensions(self, url=None):
        if url is None:
            wiki_info = self.wiki_info
        else:
            wiki_info = await self.get_wiki_info(url)
        extensions = wiki_info['query']['extensions']
        ext_list = []
        for ext in extensions:
            ext_list.append(ext['name'])
        return ext_list

    async def get_real_address(self, url=None):
        if url is None:
            wiki_info = self.wiki_info
        else:
            wiki_info = await self.get_wiki_info(url)
        real_url = wiki_info['query']['general']['server']
        if real_url.startswith('//'):
            real_url = self.wiki_api_endpoint.split('//')[0] + real_url
        return real_url

    async def get_image(self, page_name, wiki_api_endpoint=None):
        try:
            query_string = {'action': 'query', 'titles': page_name, 'prop': 'imageinfo', 'iiprop': 'url',
                            'format': 'json'}
            url = (
                      wiki_api_endpoint if wiki_api_endpoint is not None else self.wiki_api_endpoint) + self.encode_query_string(
                query_string)
            json_ = await self.get_data(url, 'json')
            parse_page_id = self.parse_page_id(json_)
            image_link = json_['query']['pages'][parse_page_id]['imageinfo'][0]['url']
            return image_link
        except:
            traceback.print_exc()
            return False

    async def get_page_link(self, page_name=None):
        page_name = page_name if page_name is not None else self.page_name
        page_name = re.sub('(.*)\?.*$', '\\1', page_name)
        query_string = {'action': 'query', 'format': 'json', 'prop': 'info', 'inprop': 'url', 'redirects': 'True',
                        'titles': page_name}
        get_link_url = self.wiki_api_endpoint + self.encode_query_string(query_string)
        get_page = await self.get_data(get_link_url, "json")
        return get_page

    def parse_page_id(self, page_raw):
        page_raw = page_raw['query']['pages']
        page_list = iter(page_raw)
        page_id = page_list.__next__()
        return page_id

    async def research_page(self):
        try:
            query_string = {'action': 'query', 'list': 'search', 'srsearch': self.page_name, 'srwhat': 'text',
                            'srlimit': '1', 'srenablerewrites': '', 'format': 'json'}
            search_url = self.wiki_api_endpoint + self.encode_query_string(query_string)
            get_sec_json = await self.get_data(search_url, "json", self.headers)
            sec_title = get_sec_json['query']['search'][0]['title']
            if self.interwiki == '':
                target = ''
            else:
                target = f'{self.interwiki}:'
            prompt = f'找不到{target}{self.page_name}，您是否要找的是：[{target}{sec_title}]？'
            title_split = self.page_name.split(':')
            if len(title_split) > 1:
                try:
                    get_namespace = await self.get_namespace()
                    if title_split[0] not in get_namespace:
                        prompt += f'\n提示：此Wiki上找不到“{title_split[0]}”命名空间，请检查是否设置了对应的Interwiki（使用~wiki iw list命令可以查询当前已设置的Interwiki）。'
                except:
                    traceback.print_exc()
            if self.template_prompt:
                prompt = self.template_prompt + prompt
            if await self.danger_text_check(prompt):
                return {'status': 'done', 'text': 'https://wdf.ink/6OUp'}
            return {'status': 'wait', 'title': f'{target}{sec_title}', 'text': prompt}
        except Exception:
            traceback.print_exc()
            return {'status': 'done', 'text': '找不到条目。'}

    async def page_not_found(self):
        if 'invalid' in self.psepgraw:
            rs1 = re.sub('The requested page title contains invalid characters:', '请求的页面标题包含非法字符：',
                         self.psepgraw['invalidreason'])
            rs = '发生错误：“' + rs1 + '”。'
            rs = re.sub('".”', '"”', rs)
            return {'status': 'done', 'text': rs}
        if 'missing' in self.psepgraw:
            self.rspt = await self.research_page()
            return self.rspt
        msg = await self.get_article_path(self.wiki_api_endpoint) + urllib.parse.quote(self.page_name.encode('UTF-8'))
        return {'status': 'done', 'text': msg}

    async def get_desc(self):
        try:
            query_string = {'action': 'query', 'prop': 'info|pageprops|extracts',
                            'ppprop': 'description|displaytitle|disambiguation|infoboxes', 'explaintext': 'true',
                            'exsectionformat': 'plain', 'exchars': '200', 'format': 'json',
                            'titles': self.query_text_name}
            desc_url = self.wiki_api_endpoint + self.encode_query_string(query_string)
            load_text = await self.get_data(desc_url, "json", self.headers)
            page_id = self.parse_page_id(load_text)
            desc = load_text['query']['pages'][page_id]['extract'].split('\n')
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
        return desc

    async def get_first_line(self):
        try:
            query_string = {'action': 'parse', 'page': self.query_text_name, 'prop': 'text',
                            'format': 'json'}
            desc_url = self.wiki_api_endpoint + self.encode_query_string(query_string)
            load_desc = await self.get_data(desc_url, 'json', self.headers)
            h = html2text.HTML2Text()
            h.ignore_links = True
            h.ignore_images = True
            h.ignore_tables = True
            desc_raw = h.handle(load_desc['parse']['text']['*']).split('\n')
            desc_list = []
            for x in desc_raw:
                if x != '':
                    if x not in desc_list:
                        desc_list.append(x)
            desc_raw = '\n'.join(desc_list)
            cut_desc = re.findall(r'(.*?(?:!\s|\?\s|\.\s|！|？|。)).*', desc_raw, re.S | re.M)
            if cut_desc:
                desc = cut_desc[0]
            else:
                desc = desc_raw
        except Exception:
            traceback.print_exc()
            desc = ''
        return desc

    async def get_all_wikitext(self):
        try:
            query_string = {'action': 'parse', 'page': self.query_text_name, 'prop': 'wikitext', 'format': 'json'}
            desc_url = self.wiki_api_endpoint + self.encode_query_string(query_string)
            load_desc = await self.get_data(desc_url, 'json', self.headers)
            desc = load_desc['parse']['wikitext']['*']
        except Exception:
            traceback.print_exc()
            desc = ''
        return desc

    async def step1(self):
        try:
            self.page_id = self.parse_page_id(self.page_raw)
        except:
            return {'status': 'done', 'text': '发生错误：无法获取到页面，请检查是否设置了对应Interwiki。'}
        self.psepgraw = self.page_raw['query']['pages'][self.page_id]

        if self.page_id == '-1':
            if self.template == True:
                self.page_name = self.orginpagename = re.sub(r'^Template:', '', self.page_name)
                self.template = False
                if self.interwiki == '':
                    target = ''
                else:
                    target = self.interwiki + ':'
                self.template_prompt = f'提示：[{target}Template:{self.page_name}]不存在，已自动回滚搜索页面。\n'
                return await self.step1()
            return await self.page_not_found()
        else:
            return await self.step2()

    async def step2(self):
        try:
            full_url = self.psepgraw['fullurl']
            try:
                geturl_pagename = full_url.split(self.wiki_articlepath)
                geturl_pagename = geturl_pagename[1]
            except:
                geturl_pagename = full_url
            self.query_text_name = urllib.parse.unquote(geturl_pagename)
            query_text_name_split = self.query_text_name.split(':')
            if len(query_text_name_split) > 1:
                namespaces = await self.get_namespace()
                if query_text_name_split[0] in namespaces:
                    if namespaces[query_text_name_split[0]] == 'Template':
                        get_all_text = await self.get_all_wikitext()
                        try:
                            match_doc = re.match(r'.*{{documentation\|?(.*?)}}.*', get_all_text, re.I | re.S)
                            match_link = re.match(r'link=(.*)', match_doc.group(1), re.I | re.S)
                            if match_link:
                                get_doc = match_link.group(1)
                                get_doc_raw = await self.get_page_link(get_doc)
                                get_doc_id = self.parse_page_id(get_doc_raw)
                                get_doc_link = get_doc_raw['query']['pages'][get_doc_id]['fullurl']
                                get_doc_pagename = get_doc_link.split(self.wiki_articlepath)[1]
                                self.query_text_name = get_doc_pagename
                            else:
                                self.query_text_name = geturl_pagename + '/doc'
                        except AttributeError:
                            self.query_text_name = geturl_pagename + '/doc'
            enabled_extensions = await self.get_enabled_extensions()
            if 'TextExtracts' in enabled_extensions:
                desc = await self.get_desc()
            else:
                desc = await self.get_first_line()
            print(desc)
            fin_page_name = geturl_pagename
            try:
                section = re.match(r'.*(#.*)', self.page_name)
                if section:
                    fin_page_name = geturl_pagename + urllib.parse.quote(section.group(1).encode('UTF-8'))
                    full_url = self.psepgraw['fullurl'] + urllib.parse.quote(section.group(1).encode('UTF-8'))
            except Exception:
                traceback.print_exc()
            try:
                pgstr = re.match(r'.*(\?.*)', self.page_name)
                if pgstr:
                    fin_page_name = geturl_pagename + pgstr.group(1)
                    full_url = full_url + pgstr.group(1)
            except Exception:
                traceback.print_exc()
            fin_page_name = urllib.parse.unquote(fin_page_name)
            fin_page_name = re.sub('_', ' ', fin_page_name)
            if fin_page_name == self.orginpagename:
                rmlstlb = re.sub('\n$', '', desc)
            else:
                if self.interwiki == '':
                    target = ''
                else:
                    target = f'{self.interwiki}:'
                rmlstlb = re.sub('\n$', '',
                                 f'（重定向[{target}{self.orginpagename}] -> [{target}{fin_page_name}]）' + (
                                     '\n' if desc != '' else '') + f'{desc}')
            rmlstlb = re.sub('\n\n', '\n', rmlstlb)
            if len(rmlstlb) > 250:
                rmlstlb = rmlstlb[0:250] + '...'
            try:
                rm5lline = re.findall(r'.*\n.*\n.*\n.*\n.*\n', rmlstlb)
                result = rm5lline[0] + '...'
            except Exception:
                result = rmlstlb
            msgs = {'status': 'done', 'url': full_url, 'text': result, 'apilink': self.wiki_api_endpoint}
            match_img = re.match(r'File:.*?\.(?:png|gif|jpg|jpeg|webp|bmp|ico)', self.page_name, re.I)
            if match_img:
                getimg = await self.get_image(self.page_name)
                if getimg:
                    msgs['net_image'] = getimg
            match_aud = re.match(r'File:.*?\.(?:oga|ogg|flac|mp3|wav)', self.page_name, re.I)
            if match_aud:
                getaud = await self.get_image(self.page_name)
                if getaud:
                    msgs['net_audio'] = getaud
            if result != '' and await self.danger_text_check(result):
                return {'status': 'done', 'text': 'https://wdf.ink/6OUp'}
            return msgs
        except Exception as e:
            traceback.print_exc()
            return {'status': 'done', 'text': '发生错误：' + str(
                e) + '\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=report_bug.yaml&title=%5BBUG%5D%3A+'}

    async def main(self, api_endpoint_link, page_name, interwiki=None, template=False, headers=None, tryiw=0):
        print(api_endpoint_link)
        print(page_name)
        print(interwiki)
        try:
            if page_name == '':
                article_path = await self.get_article_path(api_endpoint_link)
                if not article_path:
                    article_path = '发生错误：此站点或许不是有效的Mediawiki网站。' + api_endpoint_link
                return {'status': 'done', 'text': article_path}
            page_name = re.sub('_', ' ', page_name)
            page_name = page_name.split('|')[0]
            self.wiki_api_endpoint = api_endpoint_link
            danger_check = self.danger_wiki_check()
            if danger_check:
                if await self.danger_text_check(page_name):
                    return {'status': 'done', 'text': 'https://wdf.ink/6OUp'}
            self.orginpagename = page_name
            self.page_name = page_name
            if interwiki == None:
                self.interwiki = ''
            else:
                self.interwiki = interwiki
            self.wiki_info = await self.get_wiki_info()
            self.wiki_namespace = await self.get_namespace()
            real_wiki_url = await self.get_real_address()
            api_endpoint = re.match(r'^https?://.*?/(.*)', api_endpoint_link)
            self.wiki_api_endpoint = real_wiki_url + '/' + api_endpoint.group(1)
            self.wiki_articlepath = await self.get_article_path()
            self.template = template
            self.template_prompt = None
            self.headers = headers
            if self.template:
                if not re.match('^Template:', self.page_name, re.I):
                    self.page_name = 'Template:' + self.page_name
            self.page_raw = await self.get_page_link()
        except asyncio.exceptions.TimeoutError:
            return {'status': 'done',
                    'text': '发生错误：请求页面超时。\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=report_bug.yaml&title=%5BBUG%5D%3A+'}
        except Exception as e:
            traceback.print_exc()
            return {'status': 'done',
                    'text': f'发生错误：{str(e)}\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=report_bug.yaml&title=%5BBUG%5D%3A+'}
        if 'interwiki' in self.page_raw['query']:
            iwp = self.page_raw['query']['interwiki'][0]
            match_interwiki = re.match(r'^' + iwp['iw'] + r':(.*)', iwp['title'])
            if tryiw <= 10:
                iw_list = await self.get_interwiki(self.wiki_api_endpoint)
                interwiki_link = iw_list[iwp['iw']]
                check = await self.check_wiki_available(interwiki_link)
                if check[0]:
                    return await self.main(check[0], match_interwiki.group(1),
                                           ((interwiki + ':') if interwiki is not None else '') + iwp['iw'],
                                           self.template, headers, tryiw + 1)
                else:
                    return {'status': 'done',
                            'text': f'发生错误：指向的interwiki或许不是一个有效的MediaWiki。{interwiki_link}{match_interwiki.group(1)}'}
            else:
                return {'status': 'warn', 'text': '警告：尝试重定向已超过10次，继续尝试将有可能导致你被机器人加入黑名单。'}
        if 'redirects' in self.page_raw['query']:
            self.page_name = self.page_raw['query']['redirects'][0]['to']
        try:
            return await self.step1()
        except Exception as e:
            traceback.print_exc()
            return f'发生错误：{str(e)}' + '\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=report_bug.yaml&title=%5BBUG%5D%3A+\n'
