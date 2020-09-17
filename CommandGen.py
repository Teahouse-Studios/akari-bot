import re

ignorelist = [250500369, 676942198]


async def findcommand(str1, group=0):
    str1 = re.sub(r'^～', '~', str1)
    q = re.match(r'^.*(: ~)(.*)', str1)
    if q:
        return q.group(2)
    q = re.match(r'^~(.*)', str1)
    if q:
        return q.group(1)
    q = re.match(r'^!(.*\-.*)', str1)
    if q:
        q = str.upper(q.group(1))
        return 'bug ' + q
    w = re.findall(r'\[\[(.*?)\]\]', str1, re.I)
    w2 = re.findall(r'\{\{(.*?)\}\}', str1, re.I)
    z = []
    c = '\n'
    if w:
        from modules.wiki import im, imarc
        wi1 = []
        if str(w) != '['']' or str(w) != '[]':
            for x in w:
                if x == '' or x in wi1:
                    pass
                else:
                    wi1.append(x)
        if wi1 != []:
            if group in ignorelist:
                z.append(await imarc(wi1))
            else:
                z.append(await im(wi1))
    if w2:
        from modules.wiki import imt
        wi2 = []
        if str(w2) != '['']' or str(w2) != '[]':
            for x in w2:
                if x == '' or x in wi2:
                    pass
                else:
                    wi2.append(x)
        if wi2 != []:
            if group in ignorelist:
                pass
            else:
                z.append(await imt(wi2))
    if str(z):
        v = c.join(z)
        if v != '':
            return 'echo ' + v


async def command(text, group=0):
    result = await findcommand(text, group)
    c = result
    if c != None:
        try:
            d = result.split(' ')
            d = d[0]
        except Exception:
            d = c
        if d == 'echo':
            echo = re.sub(r'^echo ', '', c)
            return echo
        if c == 'help':
            from modules.help import help
            return help()
        if d == 'pa':
            return '爬'
        if d == 'mcv':
            from modules.mcv import mcv
            return await mcv()
        if d == 'mcbv':
            from modules.mcv import mcbv
            return await mcbv()
        if d == 'mcdv':
            from modules.mcv import mcdv
            return await mcdv()
        if d.find('新人') != -1 or d.find('new') != -1:
            from modules.newbie import new
            return await new()
        if d.find("wiki") != -1 or d.find("Wiki") != -1:
            from modules.wiki import wmg
            return await(wmg(c, group))
        if c.find("bug") != -1 or c.find("MC-") != -1 or c.find("BDS-") != -1 or c.find("MCPE-") != -1 or c.find(
                "MCAPI-") != -1 or c.find("MCCE-") != -1 or c.find("MCD-") != -1 or c.find("MCL-") != -1 or c.find(
            "REALMS-") != -1 or c.find("MCE-") != -1 or c.find("WEB-") != -1:
            from modules.bug import bugtracker
            return await bugtracker(c)
        if d == 'server' or d == 'Server':
            from modules.server import ser
            return await ser(c)
        if d.find("user") != -1 or d.find("User") != -1:
            if c.find("-p") != -1:
                from modules.userp import userpic
                return await userpic(c)
            else:
                from modules.user import Username
                return await Username(c)
        if d == 'rc':
            from modules.rc import rc
            return await rc()
        if d == 'ab':
            from modules.ab import ab
            return await ab()
        if d == 'ping':
            from modules.ping import ping
            return await ping()
        if d == 'credits':
            from modules.help import credits
            return credits()
    else:
        pass
