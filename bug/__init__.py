from .bugtracker import bug
from .bugtrackerbc import bugcb
from .bugtrackergc import buggc
import re
async def bugtracker(name):
    try:
        if name.find(" -h") != -1:
            return('''~bug <JiraID> - 从Mojira中获取此Bug的信息。
[-b] - 使用百度翻译。
[-g] - 使用Google翻译。''')
        elif name.find(" -g") != -1:
            name = re.sub(' -g','',name)
            q = re.match(r'^bug (.*\-.*)', name)
            return (await buggc(q.group(1)))
        elif name.find(" -b") != -1:
            name = re.sub(' -b', '', name)
            q = re.match(r'^bug (.*\-.*)', name)
            return (await bugcb(q.group(1)))
        else:
            try:
                q = re.match(r'^bug (.*)\-(.*)', name)
                return(bug(q.group(1)+'-'+q.group(2)))
            except Exception:
                return ('未知语法，请使用~bug -h获取帮助。')
    except Exception:
        return (str(e))