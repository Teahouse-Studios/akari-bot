import re
import traceback
import urllib

import aiohttp

from modules.interwikilist import iwlist, iwlink


class wiki:
    async def get_data(self, url: str, fmt: str):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                    if hasattr(req, fmt):
                        return await getattr(req, fmt)()
                    else:
                        raise ValueError(f"NoSuchMethod: {fmt}")
            except Exception:
                traceback.print_exc()

    async def getpage(self):
        getlinkurl = self.wikilink + 'api.php?action=query&format=json&prop=info&inprop=url&redirects&titles=' + self.pagename
        getpage = await self.get_data(getlinkurl, "json")
        return getpage

    def parsepageid(self, pageraw):
        pageraw = pageraw['query']['pages']
        pagelist = iter(pageraw)
        pageid = pagelist.__next__()
        return pageid

    async def researchpage(self):
        try:
            searchurl = self.wikilink + 'api.php?action=query&generator=search&gsrsearch=' + self.pagename + '&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
            getsecjson = await self.get_data(searchurl, "json")
            secpageid = self.parsepageid(getsecjson)
            sectitle = getsecjson['query']['pages'][secpageid]['title']
            if self.interwiki == '':
                target = ''
            else:
                target = f'{self.interwiki}:'
            return f'[wait]找不到条目，您是否要找的是：[[{target}{sectitle}]]？'
        except Exception:
            try:
                searchurl = self.wikilink + 'api.php?action=query&list=search&srsearch=' + self.pagename + '&srwhat=text&srlimit=1&srenablerewrites=&format=json'
                getsecjson = await self.get_data(searchurl, "json")
                sectitle = getsecjson['query']['search'][0]['title']
                if self.interwiki == '':
                    target = ''
                else:
                    target = f'{self.interwiki}:'
                return f'[wait]找不到条目，您是否要找的是：[[{target}{sectitle}]]？'
            except Exception:
                return '找不到条目。'

    async def nullpage(self):
        if 'invalid' in self.psepgraw:
            rs1 = re.sub('The requested page title contains invalid characters:', '请求的页面标题包含非法字符：',
                         self.psepgraw['invalidreason'])
            rs = '发生错误：“' + rs1 + '”。'
            rs = re.sub('".”', '"”', rs)
            return rs
        if 'missing' in self.psepgraw:
            self.rspt = await self.researchpage()
            self.interference()
            return self.rspt

        return self.wikilink + urllib.parse.quote(self.pagename.encode('UTF-8'))

    async def getdesc(self):
        try:
            descurl = self.wikilink + 'api.php?action=query&prop=extracts&exsentences=1&&explaintext&exsectionformat=wiki' \
                                 '&format=json&titles=' + self.pagename
            loadtext = await self.get_data(descurl, "json")
            pageid = self.parsepageid(loadtext)
            desc = loadtext['query']['pages'][pageid]['extract']
        except Exception:
            traceback.print_exc()
            desc = ''
        return desc

    async def getfirstline(self):
        try:
            descurl = self.wikilink + f'api.php?action=parse&page={self.gflpagename}&prop=wikitext&section=1&format=json'
            loaddesc = await self.get_data(descurl, 'json')
            descraw = loaddesc['parse']['wikitext']['*']
            cutdesc = re.findall(r'(.*(?:!|\?|\.|;|！|？|。|；))', descraw, re.S | re.M)
            desc = cutdesc[0]
        except Exception:
            desc = ''
        return desc

    async def step1(self):
        self.pageraw = await self.getpage()
        if 'redirects' in self.pageraw['query']:
            self.pagename = self.pageraw['query']['redirects'][0]['to']
        self.pageid = self.parsepageid(self.pageraw)
        self.psepgraw = self.pageraw['query']['pages'][self.pageid]

        if self.pageid == '-1':
            if self.igmessage == False:
                if self.template == True:
                    self.pagename = re.sub(r'^Template:', '', self.pagename)
                    self.template = False
                    self.interference()
                    return f'提示：[Template:{self.pagename}]不存在，已自动回滚搜索页面。\n' + await self.step1()
                return await self.nullpage()
        else:
            return await self.step2()

    async def step2(self):
        fullurl = self.psepgraw['fullurl']
        geturlpagename = re.match(r'(https?://.*?/(?:index.php/|wiki/|.*wiki/|))(.*)', fullurl, re.M | re.I)
        desc = await self.getdesc()
        if desc == '':
            self.gflpagename = geturlpagename.group(2)
            desc = await self.getfirstline()
        try:
            section = re.match(r'.*(\#.*)', self.pagename)
            finpgname = geturlpagename.group(2) + urllib.parse.quote(section.group(1).encode('UTF-8'))
            fullurl = self.psepgraw['fullurl'] + urllib.parse.quote(section.group(1).encode('UTF-8'))
        except Exception:
            finpgname = geturlpagename.group(2)
        finpgname = urllib.parse.unquote(finpgname)
        finpgname = re.sub('_', ' ', finpgname)
        if finpgname == self.orginpagename:
            rmlstlb = re.sub('\n$', '', fullurl + '\n' + desc)
        else:
            rmlstlb = re.sub('\n$', '',
                             f'\n（重定向[{self.orginpagename}] -> [{finpgname}]）\n{fullurl}\n{desc}')
        rmlstlb = re.sub('\n\n', '\n', rmlstlb)
        rmlstlb = re.sub('\n\n', '\n', rmlstlb)
        try:
            rm5lline = re.findall(r'.*\n.*\n.*\n.*\n.*\n', rmlstlb)
            result = rm5lline[0] + '...行数过多已截断。'
        except Exception:
            result = rmlstlb
        if self.interwiki != '':
            pagename = self.interwiki + ':' + self.pagename
        return f'您要的{self.pagename}：{result}'


    def interference(self):
        if self.pagename.find('色图来') != -1 or self.pagename.find('cu') != -1:#ftynmsl
            self.pagename = '你妈'
        if self.pagename == '你妈':
            self.rspt = '[wait] 提示：找不到[你妈]，请问你是否想找一个[[新妈]]？'
        if self.pagename == '新妈':
            self.rspt = '你没有妈。'

    async def main(self, wikilink, pagename, interwiki='', igmessage=False, template=False):
        print(wikilink)
        print(pagename)
        print(interwiki)
        self.wikilink = wikilink
        self.orginpagename = pagename
        self.pagename = pagename
        self.interwiki = interwiki
        self.igmessage = igmessage
        self.template = template
        try:
            matchinterwiki = re.match(r'(.*?):(.*)', self.pagename)
            if matchinterwiki:
                if matchinterwiki.group(1) in iwlist():
                    return await self.main(iwlink(matchinterwiki.group(1)), matchinterwiki.group(2),
                                           matchinterwiki.group(1),
                                           self.igmessage, self.template)
            return await self.step1()

        except Exception as e:
            traceback.print_exc()
            if igmessage == False:
                return f'发生错误：{str(e)}'


if __name__ == '__main__':
    import asyncio

    a = asyncio.run(wiki().main('https://minecraft-zh.gamepedia.com/', '海晶石','zh'))
    print(a)
