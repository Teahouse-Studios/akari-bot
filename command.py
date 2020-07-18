import re
import string
from blacklist import blacklist
from wikil import im
async def command(str1,member,group = '0'):
    str1 = re.sub(r'^～','~',str1)
    try:
        q = re.match(r'^(发现新人：).*',str1)
        print(q.group(1))
        if str(group) == '657876815':
            if str(member) == '2736881328':
                return  ('xrrrlei '+q.group(1))
            else:
                return ('paa')
        else:
            pass
    except Exception:
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
                        if str(w) == '[]':
                            pass
                        else:
                            z = []
                            c = '\n'
                            for x in w:
                                z.append(await im(x))
                            v = c.join(z)
                            return('echo '+v)
                    except Exception:
                        pass