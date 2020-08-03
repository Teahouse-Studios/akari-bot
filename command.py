import re
import string
from blacklist import blacklist
from wikil import im,imarc,imt
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
                    w2 = re.findall(r'\{\{(.*?)\}\}',str1)
                    print(str(w),str(w2))
                    z = []
                    c = '\n'
                    try:
                        if str(w) == '['']' or str(w) == '[]':
                            pass
                        else:
                            for x in w:
                                if group == '250500369' or group == '676942198':
                                    z.append(await imarc(x))
                                else:
                                    z.append(await im(x))
                    except:
                        pass
                    try:
                        if str(w2) == '['']' or str(w2) == '[]':
                            pass
                        else:
                            for x in w2:
                                if group == '250500369' or group == '676942198':
                                    pass
                                else:
                                    z.append(await imt(x))
                    except:
                        pass
                    if str(z) =='['']['']' or str(z) == '[][]' or str(z) == '[]':
                        pass
                    else:
                        v = c.join(z)
                        return('echo '+v)
                except Exception:
                    pass