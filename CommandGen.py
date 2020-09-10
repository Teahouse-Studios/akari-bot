import re

from modules.ab import ab
from modules.bug import bugtracker
from modules.help import help, credits
from modules.mcv import mcv, mcbv, mcdv
from modules.newbie import new
from modules.ping import ping
from modules.rc import rc
from modules.server import ser
from modules.user import Username
from modules.userp import userpic
from modules.wiki import wmg
from modules.wiki import im, imt, imarc

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
    w = re.findall(r'\[\[(.*?)\]\]', str1)
    w2 = re.findall(r'\{\{(.*?)\}\}', str1)
    z = []
    c = '\n'
    if w:
        if str(w) != '['']' or str(w) != '[]':
            for x in w:
                if x == '':
                    pass
                else:
                    if group in ignorelist:
                        z.append(await imarc(x))
                    else:
                        z.append(await im(x))
    if w2:
        if str(w2) != '['']' or str(w2) != '[]':
            for x in w2:
                if x == '':
                    pass
                else:
                    if group in ignorelist:
                        pass
                    else:
                        z.append(await imt(x))
    if str(z) != '['']['']' or str(z) != '[][]' or str(z) != '[]':
        v = c.join(z)
        return 'echo ' + v


async def command(text, group=0):
    result = await findcommand(text, group)
    c = result
    if c == None:
        return
    try:
        d = result.split(' ')
        d = d[0]
    except Exception:
        d = c
    if d == 'echo':
        echo = re.sub(r'^echo ', '', c)
        return echo
    if c == 'help':
        return help()
    if d == 'pa':
        return '爬'
    if d == 'mcv':
        return await mcv()
    if d == 'mcbv':
        return await mcbv()
    if d == 'mcdv':
        return await mcdv()
    if d.find('新人') != -1 or d.find('new') != -1:
        return await new()
    if d.find("wiki") != -1 or d.find("Wiki") != -1:
        return await(wmg(c, group))
    if c.find("bug") != -1 or c.find("MC-") != -1 or c.find("BDS-") != -1 or c.find("MCPE-") != -1 or c.find(
            "MCAPI-") != -1 or c.find("MCCE-") != -1 or c.find("MCD-") != -1 or c.find("MCL-") != -1 or c.find(
        "REALMS-") != -1 or c.find("MCE-") != -1 or c.find("WEB-") != -1:
        return await bugtracker(c)
    if d == 'server' or d == 'Server':
        return await ser(c)
    if d.find("user") != -1 or d.find("User") != -1:
        if c.find("-p") != -1:
            return await userpic(c)
        else:
            return await Username(c)
    if d == 'rc':
        return await rc()
    if d == 'ab':
        return await ab()
    if d == 'ping':
        return await ping()
    if d == 'credits':
        return credits()
    else:
        pass