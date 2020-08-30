import re

from modules.ab import ab
from modules.bug import bugtracker
from modules.checkuser import checkuser
from modules.help import help, credits
from modules.mcv import mcv, mcbv, mcdv
from modules.newbie import new
from modules.ping import ping
from modules.rc import rc
from modules.server import ser
from modules.user import Username
from modules.userp import Userp
from modules.wiki import wiki
from modules.wiki import im, imt, imarc


async def findcommand(str1, group=0):
#    print(group)
    str1 = re.sub(r'^～', '~', str1)
    try:
        q = re.match(r'^.*(: ~)(.*)', str1)
        return q.group(2)
    except Exception:
        try:
            q = re.match(r'^~(.*)', str1)
            return q.group(1)
        except Exception:
            try:
                q = re.match(r'^!(.*\-.*)', str1)
                q = str.upper(q.group(1))
                return 'bug ' + q
            except Exception:
                w = re.findall(r'\[\[(.*?)\]\]', str1)
                w2 = re.findall(r'\{\{(.*?)\}\}', str1)
#                print(str(w), str(w2))
                z = []
                c = '\n'
                try:
                    for x in w:
                        if group == 250500369 or group == 676942198:
                            if x == '':
                                pass
                            else:
                                z.append(await imarc(x))
                        else:
                            if x == '':
                                pass
                            else:
                                z.append(await im(x))
                except Exception:
                    pass
                try:
                    if str(w2) == '['']' or str(w2) == '[]':
                        pass
                    else:
                        for x in w2:
                            if group == 250500369 or group == 676942198:
                                pass
                            else:
                                if x == '':
                                    pass
                                else:
                                    z.append(await imt(x))
                except Exception:
                    pass
                if str(z) == '['']['']' or str(z) == '[][]' or str(z) == '[]':
                    pass
                else:
                    v = c.join(z)
                    return 'echo ' + v


async def command(text, group=0):
    try:
        result = await findcommand(text, group)
        c = result
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
        elif d == 'paa':
            return '爬'
        elif d == 'mcv':
            return await mcv()
        elif d == 'mcbv':
            return await mcbv()
        elif d == 'mcdv':
            return await mcdv()
        elif d.find('新人') != -1 or d.find('new') != -1:
            return await new()
        elif d.find("wiki") != -1 or d.find("Wiki") != -1:
            return await(wiki(c, group))
        elif c.find("bug") != -1 or c.find("MC-") != -1 or c.find("BDS-") != -1 or c.find("MCPE-") != -1 or c.find(
                "MCAPI-") != -1 or c.find("MCCE-") != -1 or c.find("MCD-") != -1 or c.find("MCL-") != -1 or c.find(
            "REALMS-") != -1 or c.find("MCE-") != -1 or c.find("WEB-") != -1:
            return await bugtracker(c)
        elif d == 'server' or d == 'Server':
            return await ser(c)
        elif d.find("user") != -1 or d.find("User") != -1:
            if c.find("-p") != -1:
                f = re.sub(' -p', '', c)
                print(f)
                try:
                    z = re.sub(r'^User', 'user', f)
                    try:
                        g = re.match(r'^user ~(.*) (.*)', z)
                        h = g.group(1)
                        h2 = g.group(2)
                        h2 = re.sub('_', ' ', h2)
                    except Exception:
                        try:
                            g = re.match(r'^user-(.*?) (.*)', z)
                            h = 'minecraft-' + g.group(1)
                            h2 = g.group(2)
                            h2 = re.sub('_', ' ', h2)
                        except Exception:
                            try:
                                g = re.match(r'^user (.*?):(.*)', z)
                                h = 'minecraft-' + g.group(1)
                                h2 = g.group(2)
                                h2 = re.sub('_', ' ', h2)
                            except Exception:
                                try:
                                    g = re.match(r'user (.*)', z)
                                    h = 'minecraft'
                                    h2 = g.group(1)
                                    h2 = re.sub('_', ' ', h2)
                                except Exception as e:
                                    print(str(e))
                    if checkuser(h, h2):
                        h2 = re.sub('User:', '', h2)
                        print(h2)
                        return await Userp(h, h2) + "[[usn:" + h2 + "]]"
                    else:
                        return '没有找到此用户。'
                except Exception as e:
                    print(str(e))

            else:
                return await Username(c)
        elif d == 'rc':
            return await rc()
        elif d == 'ab':
            return await ab()
        elif d == 'ping':
            return await ping()
        elif d == 'credits':
            return credits()
        else:
            pass
    except Exception:
        pass
