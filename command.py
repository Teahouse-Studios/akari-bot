import re
import string
from blacklist import blacklist
from wikil import im,imarc
async def command(str1,member,group = '0'):
    str1 = re.sub(r'^～','~',str1)
    try:
        q = re.match(r'^.*(: ~)(.*)',str1)
        return q.group(2)
    except Exception:
        try:
            q = re.match(r'^~(.*)',str1)
            if q.group(1).find('爬') != -1:
                if member in blacklist():
                    return ('paa')
                else:
                    return q.group(1)
            else:
                return q.group(1)
        except Exception:
            try:
                q = re.match(r'^!(.*\-.*)',str1)
                q = str.upper(q.group(1))
                return ('bug '+q)
            except Exception:
                try:
                    w = re.findall(r'\[\[(.*?)\]\]',str1)
                    print(str(w))
                    if str(w) == '[]'or str(w) == "['']":
                        pass
                    else:
                        z = []
                        c = '\n'
                        for x in w:
                            if group == '250500369':
                                z.append(await imarc(x))
                            else:
                                z.append(await im(x))
                        v = c.join(z)
                        return('echo '+v)
                except Exception:
                    try:
                        if group == '250500369':
                            pass
                        else:
                            w2 = re.findall(r'\{\{(.*?)\}\}',str1)
                            print(str(w2))
                            if str(w2) == '[]'or str(w2) == "['']":
                                pass
                            else:
                                z2 = []
                                c2 = '\n'
                                for x in w2:
                                    z2.append(await imt(x))
                                v2 = c.join(z2)
                                return('echo '+v)