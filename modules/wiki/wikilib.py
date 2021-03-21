import re
import traceback
import urllib

import aiohttp

from core import dirty_check
from .helper import check_wiki_available


class wikilib:
    async def get_data(self, url: str, fmt: str, headers=None):
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                    if hasattr(req, fmt):
                        return await getattr(req, fmt)()
                    else:
                        raise ValueError(f"NoSuchMethod: {fmt}")
            except Exception:
                traceback.print_exc()
                return False

    def danger_wiki_check(self):
        if self.wikilink.upper().find('WIKIPEDIA') != -1:
            return True
        if self.wikilink.upper().find('UNCYCLOPEDIA') != -1:
            return True
        if self.wikilink.upper().find('HMOEGIRL') != -1:
            return True
        if self.wikilink.upper().find('EVCHK') != -1:
            return True
        if self.wikilink.upper().find('HONGKONG.FANDOM') != -1:
            return True
        if self.wikilink.upper().find('WIKILEAKS') != -1:
            return True
        if self.wikilink.upper().find('NANFANGGONGYUAN') != -1:
            return True
        return False

    async def danger_text_check(self, text):
        if not self.danger_wiki_check():
            return False
        check = await dirty_check.check(text)
        print(check)
        if check.find('<吃掉了>') != -1 or check.find('<全部吃掉了>') != -1:
            return True
        return False

    async def random_page(self, url, iw=None, headers=None):
        random_url = url + '?action=query&list=random&format=json'
        json = await self.get_data(random_url, 'json')
        randompage = json['query']['random'][0]['title']
        return await self.main(url, randompage, interwiki=iw, headers=headers)

    async def get_interwiki(self, url):
        interwiki_list = url + '?action=query&meta=siteinfo&siprop=interwikimap&format=json'
        json = await self.get_data(interwiki_list, 'json')
        interwikimap = json['query']['interwikimap']
        interwiki_dict = {}
        for interwiki in interwikimap:
            interwiki_dict[interwiki['prefix']] = re.sub(r'(?:wiki/|)\$1', '', interwiki['url'])
        return interwiki_dict

    async def get_siteinfo(self, url=None):
        url = url if url is not None else self.wikilink
        siteinfo_url = url + '?action=query&meta=siteinfo&siprop=general&format=json'
        j = await self.get_data(siteinfo_url, 'json')
        return j

    async def get_namespace(self, url=None):
        url = url if url is not None else self.wikilink
        namespace_url = url + '?action=query&meta=siteinfo&siprop=namespaces&format=json'
        j = await self.get_data(namespace_url, 'json')
        d = {}
        for x in j['query']['namespaces']:
            try:
                d[j['query']['namespaces'][x]['*']] = j['query']['namespaces'][x]['canonical']
            except:
                traceback.print_exc()
        return d

    async def get_article_path(self, url):
        siteinfo = await self.get_siteinfo(url)
        article_path = siteinfo['query']['general']['articlepath']
        article_path = re.sub(r'\$1', '', article_path)
        baseurl = re.match(r'(https?://.*?)/.*', url)
        return baseurl.group(1) + article_path

    async def get_image(self, pagename, wikilink=None):
        try:
            url = (
                      wikilink if wikilink is not None else self.wikilink) + f'?action=query&titles={pagename}&prop=imageinfo&iiprop=url&format=json'
            json = await self.get_data(url, 'json')
            parsepageid = self.parsepageid(json)
            imagelink = json['query']['pages'][parsepageid]['imageinfo'][0]['url']
            return imagelink
        except:
            traceback.print_exc()
            return False

    async def getpage(self, pagename=None):
        pagename = pagename if pagename is not None else self.pagename
        pagename = re.sub('(.*)\?.*$', '\\1', pagename)
        getlinkurl = self.wikilink + '?action=query&format=json&prop=info&inprop=url&redirects&titles=' + pagename
        getpage = await self.get_data(getlinkurl, "json")
        return getpage

    def parsepageid(self, pageraw):
        pageraw = pageraw['query']['pages']
        pagelist = iter(pageraw)
        pageid = pagelist.__next__()
        return pageid

    async def researchpage(self):
        try:
            try:
                searchurl = self.wikilink + '?action=query&generator=search&gsrsearch=' + self.pagename + '&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
                getsecjson = await self.get_data(searchurl, "json", self.headers)
                secpageid = self.parsepageid(getsecjson)
                sectitle = getsecjson['query']['pages'][secpageid]['title']
            except:
                traceback.print_exc()
                searchurl = self.wikilink + '?action=query&list=search&srsearch=' + self.pagename + '&srwhat=text&srlimit=1&srenablerewrites=&format=json'
                getsecjson = await self.get_data(searchurl, "json", self.headers)
                sectitle = getsecjson['query']['search'][0]['title']
            if self.interwiki == '':
                target = ''
            else:
                target = f'{self.interwiki}:'
            prompt = f'找不到{target}{self.pagename}，您是否要找的是：[[{target}{sectitle}]]？'
            titlesplit = self.pagename.split(':')
            if len(titlesplit) > 1:
                try:
                    get_namespace = await self.get_namespace()
                    print(get_namespace)
                    if titlesplit[0] not in get_namespace:
                        prompt += f'\n提示：此Wiki上找不到“{titlesplit[0]}”名字空间，请检查是否设置了对应的Interwiki（使用~wiki iw list命令可以查询当前已设置的Interwiki）。'
                except:
                    traceback.print_exc()
            if self.templateprompt:
                prompt = self.templateprompt + prompt
            if await self.danger_text_check(prompt):
                return {'status': 'done', 'text': 'https://wdf.ink/6OUp'}
            return {'status': 'wait', 'title': f'{target}{sectitle}', 'text': prompt}
        except Exception:
            traceback.print_exc()
            return {'status': 'done', 'text': '找不到条目。'}

    async def nullpage(self):
        if 'invalid' in self.psepgraw:
            rs1 = re.sub('The requested page title contains invalid characters:', '请求的页面标题包含非法字符：',
                         self.psepgraw['invalidreason'])
            rs = '发生错误：“' + rs1 + '”。'
            rs = re.sub('".”', '"”', rs)
            return {'status': 'done', 'text': rs}
        if 'missing' in self.psepgraw:
            self.rspt = await self.researchpage()
            return self.rspt
        msg = await self.get_article_path(self.wikilink) + urllib.parse.quote(self.pagename.encode('UTF-8'))
        return {'status': 'done', 'text': msg}

    async def getdesc(self):
        try:
            descurl = self.wikilink + '?action=query&prop=info|pageprops|extracts&ppprop=description|displaytitle|disambiguation|infoboxes&explaintext=true&exsectionformat=plain&exsentences=1&format=json&titles=' + self.querytextname
            loadtext = await self.get_data(descurl, "json", self.headers)
            pageid = self.parsepageid(loadtext)
            desc = loadtext['query']['pages'][pageid]['extract']
        except Exception:
            traceback.print_exc()
            desc = ''
        return desc

    async def getfirstline(self):
        try:
            descurl = self.wikilink + f'?action=parse&page={self.querytextname}&prop=wikitext&section=0&format=json'
            loaddesc = await self.get_data(descurl, 'json', self.headers)
            descraw = loaddesc['parse']['wikitext']['*']
            try:
                cutdesc = re.findall(r'(.*(?:!|\?|\.|;|！|？|。|；))', descraw, re.S | re.M)
                desc = cutdesc[0]
            except IndexError:
                desc = descraw
        except Exception:
            traceback.print_exc()
            desc = ''
        return desc

    async def getalltext(self):
        try:
            descurl = self.wikilink + f'?action=parse&page={self.querytextname}&prop=wikitext&format=json'
            loaddesc = await self.get_data(descurl, 'json', self.headers)
            desc = loaddesc['parse']['wikitext']['*']
        except Exception:
            traceback.print_exc()
            desc = ''
        return desc

    async def step1(self):
        if self.template:
            self.pagename = 'Template:' + self.pagename
        self.pageraw = await self.getpage()
        if not self.pageraw:
            return {'status': 'done', 'text': '发生错误：无法获取到页面。'}
        if 'redirects' in self.pageraw['query']:
            self.pagename = self.pageraw['query']['redirects'][0]['to']
        try:
            self.pageid = self.parsepageid(self.pageraw)
        except:
            return {'status': 'done', 'text': '发生错误：无法获取到页面，请检查是否设置了对应Interwiki。'}
        self.psepgraw = self.pageraw['query']['pages'][self.pageid]

        if self.pageid == '-1':
            if self.igmessage == False:
                if self.template == True:
                    self.pagename = self.orginpagename = re.sub(r'^Template:', '', self.pagename)
                    self.template = False
                    self.templateprompt = f'提示：[Template:{self.pagename}]不存在，已自动回滚搜索页面。\n'
                    return await self.step1()
                return await self.nullpage()
        else:
            return await self.step2()

    async def step2(self):
        try:
            fullurl = self.psepgraw['fullurl']
            print(fullurl)
            artpath = await self.get_article_path(self.wikilink)
            artpath = re.sub(r'https?://', '', artpath)
            geturlpagename = re.sub(r'.*' + artpath, '', fullurl)
            self.querytextname = urllib.parse.unquote(geturlpagename)
            querytextnamesplit = self.querytextname.split(':')
            if len(querytextnamesplit) > 1:
                namespaces = await self.get_namespace()
                if querytextnamesplit[0] in namespaces:
                    if namespaces[querytextnamesplit[0]] == 'Template':
                        getalltext = await self.getalltext()
                        try:
                            matchdoc = re.match(r'.*{{documentation\|?(.*?)}}.*', getalltext, re.I | re.S)
                            matchlink = re.match(r'link=(.*)', matchdoc.group(1), re.I | re.S)
                            if matchlink:
                                getdoc = matchlink.group(1)
                                getdocraw = await self.getpage(getdoc)
                                getdocid = self.parsepageid(getdocraw)
                                getdoclink = getdocraw['query']['pages'][getdocid]['fullurl']
                                getdocpagename = re.sub(r'.*' + artpath, '', getdoclink)
                                self.querytextname = getdocpagename
                            else:
                                self.querytextname = geturlpagename + '/doc'
                        except AttributeError:
                            self.querytextname = geturlpagename + '/doc'
            print(self.querytextname)
            desc = await self.getdesc()
            if desc == '':
                desc = await self.getfirstline()
            print(desc)
            finpgname = geturlpagename
            try:
                section = re.match(r'.*(\#.*)', self.pagename)
                if section:
                    finpgname = geturlpagename + urllib.parse.quote(section.group(1).encode('UTF-8'))
                    fullurl = self.psepgraw['fullurl'] + urllib.parse.quote(section.group(1).encode('UTF-8'))
            except Exception:
                traceback.print_exc()
            try:
                pgtag = re.match(r'.*(\?.*)', self.pagename)
                if pgtag:
                    finpgname = geturlpagename + pgtag.group(1)
                    fullurl = fullurl + pgtag.group(1)
            except Exception:
                traceback.print_exc()
            finpgname = urllib.parse.unquote(finpgname)
            finpgname = re.sub('_', ' ', finpgname)
            if finpgname == self.orginpagename:
                rmlstlb = re.sub('\n$', '', desc)
            else:
                if self.interwiki == '':
                    target = ''
                else:
                    target = f'{self.interwiki}:'
                rmlstlb = re.sub('\n$', '',
                                 f'（重定向[{target}{self.orginpagename}] -> [{target}{finpgname}]）' + (
                                     '\n' if desc != '' else '') + f'{desc}')
            rmlstlb = re.sub('\n\n', '\n', rmlstlb)
            rmlstlb = re.sub('\n\n', '\n', rmlstlb)
            if len(rmlstlb) > 250:
                rmlstlb = rmlstlb[0:250] + '\n...字数过多已截断。'
            try:
                rm5lline = re.findall(r'.*\n.*\n.*\n.*\n.*\n', rmlstlb)
                result = rm5lline[0] + '...行数过多已截断。'
            except Exception:
                result = rmlstlb
            msgs = {'status': 'done', 'url': fullurl, 'text': result, 'apilink': self.wikilink}
            matchimg = re.match(r'File:.*?\.(?:png|gif|jpg|jpeg|webp|bmp|ico)', self.pagename, re.I)
            if matchimg:
                getimg = await self.get_image(self.pagename)
                if getimg:
                    msgs['net_image'] = getimg
            print(result)
            if result != '' and await self.danger_text_check(result):
                return {'status': 'done', 'text': 'https://wdf.ink/6OUp'}
            return msgs
        except Exception as e:
            traceback.print_exc()
            return {'status': 'done', 'text': '发生错误：' + str(e)}

    async def main(self, wikilink, pagename, interwiki=None, igmessage=False, template=False, headers=None, tryiw=0):
        print(wikilink)
        print(pagename)
        print(interwiki)
        if pagename == '':
            return {'status': 'done', 'text': await self.get_article_path(wikilink)}
        pagename = re.sub('_', ' ', pagename)
        pagename = pagename.split('|')[0]
        self.orginwikilink = wikilink
        self.wikilink = re.sub('index.php/', '', self.orginwikilink)  # fxxk
        danger_check = self.danger_wiki_check()
        if danger_check:
            if await self.danger_text_check(pagename):
                return {'status': 'done', 'text': 'https://wdf.ink/6OUp'}
        self.orginpagename = pagename
        self.pagename = pagename
        if interwiki == None:
            self.interwiki = ''
        else:
            self.interwiki = interwiki
        self.igmessage = igmessage
        self.template = template
        self.templateprompt = None
        self.headers = headers
        try:
            matchinterwiki = re.match(r'(.*?):(.*)', self.pagename)
            if matchinterwiki:
                iwlist = await self.get_interwiki(self.wikilink)
                if matchinterwiki.group(1) in iwlist:
                    if tryiw <= 5:
                        interwiki_link = iwlist[matchinterwiki.group(1)]
                        check = await check_wiki_available(interwiki_link)
                        print(check)
                        if check:
                            return await self.main(check[0], matchinterwiki.group(2),
                                                   ((
                                                            interwiki + ':') if interwiki is not None else '') + matchinterwiki.group(
                                                       1),
                                                   self.igmessage, self.template, headers, tryiw + 1)
                        else:
                            return {'status': 'done',
                                    'text': f'发生错误：指向的interwiki不是一个有效的MediaWiki。{interwiki_link}{matchinterwiki.group(2)}'}
                    else:
                        return {'status': 'warn', 'text': '警告：尝试重定向已超过5次，继续尝试将有可能导致你被机器人加入黑名单。'}
            return await self.step1()

        except Exception as e:
            traceback.print_exc()
            if igmessage == False:
                return f'发生错误：{str(e)}' + '\n'
