import re
import traceback
from .wikitextlib import wi
from interwikilist import iwlist,iwlink
async def im(str1):
    try:
        pipe = re.match(r'(.*?)\|.*',str1)
        str1 = pipe.group(1)
    except Exception:
        str1 = str1
    str1 = re.sub(r'^:','',str1)
    try:
        d = re.match(r'(.*?):(.*)',str1)
        w = d.group(1)
        w = str.lower(w)
        if w in iwlist():
            c = iwlink(w)
            pagename = d.group(2)
            itw = 't'
        else:
            c = iwlink('zh')
            pagename = str1
            itw = 'f'
    except Exception:
        c = iwlink('zh')
        pagename = str1
        itw = 'f'
        w = '.'
    return(await wi(c,w,pagename,itw,ignoremessage='f'))

async def imarc(str1):
    try:
        pipe = re.match(r'(.*?)\|.*',str1)
        str1 = pipe.group(1)
    except Exception:
        str1 = str1
    str1 = re.sub(r'^:','',str1)
    c = 'wiki.arcaea.cn'
    itw = 'f'
    w = '.'
    return(await wi(c,w,str1,itw,ignoremessage='t'))

async def imt(str1):
    try:
        pipe = re.match(r'(.*?)\|.*',str1)
        str1 = pipe.group(1)
    except Exception:
        str1 = str1
    str1 = re.sub(r'^:','',str1)
    try:
        d = re.match(r'(.*?):(.*)',str1)
        w = d.group(1)
        w = str.lower(w)
        if w in iwlist():
            c = iwlink(w)
            pagename = 'Template:'+d.group(2)
            itw = 't'
        else:
            c = iwlink('zh')
            pagename = 'Template:'+str1
            itw = 'f'
    except Exception:
        c = iwlink('zh')
        pagename = 'Template:'+str1
        itw = 'f'
        w = '.'
    return(await wi(c,w,pagename,itw,ignoremessage='f',template = 't'))