import re

ignorelist = []

from commandlist import commandlist

clist = commandlist()

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
        try:
            d = d.split('-')
            d = d[0]
        except Exception:
            d = c
        if d == 'echo':
            echo = re.sub('echo ', '', c)
            if echo != '':
                return echo
        if d in clist:
            k = clist.get(d)
            k1 = re.match(r'from (.*) import (.*)\|(.*)', k)
            if k1:
                cmd = eval(f'__import__("modules.{k1.group(1)}", fromlist=["{k1.group(1)}"]).{k1.group(2)}().{k1.group(3)}')
                if d == c:
                    return await cmd()
                else:
                    return await cmd(c)
            else:
                k2 = re.match(r'from (.*) import (.*)', k)
                if k2:
                    cmd = eval(f'__import__("modules.{k2.group(1)}", fromlist=["{k2.group(1)}"]).{k2.group(2)}')
                    if d == c:
                        return await cmd()
                    else:
                        return await cmd(c)
                else:
                    a = __import__('modules.' + k, fromlist=[k])
                    if d == c:
                        return await a.main()
                    else:
                        return await a.main(c)
    else:
        pass
