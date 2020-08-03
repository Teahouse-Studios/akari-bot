import re
import traceback
from .wikitextlib import wi
async def im(str1):
    try:
        pipe = re.match(r'(.*?)\|.*',str1)
        str1 = pipe.group(1)
    except Exception:
        str1 = str1
    try:
        d = re.match(r'(.*?):(.*)',str1)
        w = d.group(1)
        w = str.lower(w)
        if (w == "cs" or w == "de" or w == "el" or w == "es" or w == "fr" or w == "hu" or w == "it" or w == "ja" or w == "ko" or w == "nl" or w == "pl" or w == "pt" or w == "ru" or w == "th" or w == "tr" or w == "uk" or w == "zh"):
            c = 'minecraft-'+w+'.gamepedia.com'
            pagename = d.group(2)
            itw = 't'
        elif w == "en":
            c = 'minecraft.gamepedia.com'
            pagename = d.group(2)
            itw = 't'
        elif w == 'arc' or w == 'arcaea':
            c = 'wiki.arcaea.cn'
            pagename = d.group(2)
            itw = 't'
        elif w == 'moe' or w == 'moegirl':
            c = 'zh.moegirl.org.cn'
            pagename = d.group(2)
            itw = 't'
        else:
            c = 'minecraft-zh.gamepedia.com'
            pagename = str1
            itw = 'f'
    except Exception:
        c = 'minecraft-zh.gamepedia.com'
        pagename = str1
        itw = 'f'
    return(await wi(c,pagename,itw,ignoremessage='f'))

async def imarc(str1):
    try:
        pipe = re.match(r'(.*?)\|.*',str1)
        str1 = pipe.group(1)
    except Exception:
        str1 = str1
    c = 'wiki.arcaea.cn'
    itw = 'f'
    return(await wi(c,str1,itw,ignoremessage='t'))