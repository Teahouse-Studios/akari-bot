from .userlib import User1
import requests
import json
import re

def User(Username):
    try:
        z = re.match(r'(.*) (.*)', Username)
        q = z.group(2)
        metaurl = 'https://' + z.group(1) + '.gamepedia.com'
        return(User1(metaurl, q))
    except Exception:
        try:
            p = re.match(r'(.*):.*',Username, re.M|re.I)
            w = re.sub(r':.*',"",p.group(1))
        except Exception:
            w = "None"
            pass
        if (w=="cs" or w=="de" or w=="el" or w=="en" or w=="es" or w=="fr" or w=="hu" or w=="it" or w=="ja" or w=="ko" or w=="nl" or w=="pl" or w=="pt" or w=="ru" or w=="th" or w=="tr" or w=="uk" or w=="zh"):
            try:
                q = re.sub(w+r':',"",Username)
                metaurl = 'https://minecraft-'+w+'.gamepedia.com'
                return(User1(metaurl,q))
            except  Exception as e:
                return('发生错误：'+ str(e))
        else:
            try:
                metaurl = 'https://minecraft.gamepedia.com'
                return(User1(metaurl,Username))
            except  Exception as e:
                return('发生错误：' + str(e))