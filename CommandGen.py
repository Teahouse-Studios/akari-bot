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
            echo = re.sub('echo ', '', c)
            if echo != '':
                return echo
        if d in clist:
            k = clist.get(d)
            k1 = re.match(r'from (.*) import (.*)\|(.*)', k)
            if k1:
                cmd = eval(
                    f'__import__("modules.{k1.group(1)}", fromlist=["{k1.group(1)}"]).{k1.group(2)}().{k1.group(3)}')
                if d == c:
                    return await cmd()
                else:
                    c = re.sub(r'^'+d+' ','',c)
                    return await cmd(c)
            else:
                k2 = re.match(r'from (.*) import (.*)', k)
                if k2:
                    cmd = eval(f'__import__("modules.{k2.group(1)}", fromlist=["{k2.group(1)}"]).{k2.group(2)}')
                    if d == c:
                        return await cmd()
                    else:
                        c = re.sub(r'^' + d + ' ', '', c)
                        return await cmd(c)
                else:
                    a = __import__('modules.' + k, fromlist=[k])
                    if d == c:
                        return await a.main()
                    else:
                        c = re.sub(r'^' + d + ' ', '', c)
                        return await a.main(c)


async def ttext(text, group):
    w = re.findall(r'\[\[(.*?)\]\]', text, re.I)
    w2 = re.findall(r'\{\{(.*?)\}\}', text, re.I)
    z = []
    c = '\n'
    if w:
        from modules.wiki import im
        wi1 = []
        if str(w) != '['']' or str(w) != '[]':
            for x in w:
                if x == '' or x in wi1:
                    pass
                else:
                    wi1.append(x)
        if wi1 != []:
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
            z.append(await imt(wi2))
    w3 = re.findall(r'(https://bugs.mojang.com/browse/.*?-\d*)', text)
    for link in w3:
        matchbug = re.match(r'https://bugs.mojang.com/browse/(.*?-\d*)',link)
        if matchbug:
            import modules.bug
            z.append(await modules.bug.main(matchbug.group(1)))
    if str(z):
        v = c.join(z)
        if v != '':
            return v
