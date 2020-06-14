import re
import string
import blacklist
def command(str1,member):
    try:
        q = re.match(r'\[\[(.*)\|.*\]\]',str1)
        return ('im '+q.group(1))
    except Exception:
        try:
            q = re.match(r'^(发现新人：).*',str1)
            print(q.group(1))
            if str(member) == '2736881328':
                return  ('xrrrlei '+q.group(1))
            else:
                return ('paa')
        except Exception:
            try:
                q = re.match(r'\[\[(.*)\]\]', str1)
                if q.group(1) == '爬':
                    if member in blacklist():
                        return ('paa')
                    else:
                        return ('im ' + q.group(1))
                else:
                    return ('im ' + q.group(1))
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
                            pass