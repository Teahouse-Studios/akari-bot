import json
import requests
import os,sys
from nonebot import on_command, CommandSession
import re
from collections import OrderedDict
@on_command('wikisearch')
async def wikisearch(session: CommandSession):
    try:
        stripped_arg = session.current_arg_text.strip()
        session.state['pagename'] = stripped_arg
        pagename = session.get('pagename')
        try:
            os.remove('search.txt')
        except Exception:
            pass
        try:
            p = re.match(r'(.*):.*',pagename, re.M|re.I)
            w = re.sub(r':.*',"",p.group(1))
        except Exception:
            w = "None"
            pass
        if (w=="cs" or w=="de" or w=="el" or w=="en" or w=="es" or w=="fr" or w=="hu" or w=="it" or w=="ja" or w=="ko" or w=="nl" or w=="pl" or w=="pt" or w=="ru" or w=="th" or w=="tr" or w=="uk" or w=="zh"):
            try:
                q = re.sub(w+r':',"",pagename)
                url='https://minecraft-'+w+'.gamepedia.com/api.php?action=query&generator=search&gsrsearch='+q+'&srsort=relevance&prop=info&srlimit=1&format=json'
                s = requests.get(url,timeout=10)
                file = json.loads(s.text,object_pairs_hook=OrderedDict)
                x=file['query']['pages']
                for item in sorted(x.keys()):
                    a = open('search.txt',mode='a',encoding='UTF-8')
                    a.write(x[item]['title']+'\n')
                    a.close()
                m = open('search.txt',mode='r',encoding='UTF-8')
                await session.send(m.read())
                m.close()
            except KeyError:
                await session.send('什么都没找到。')
        else:
            try:
                url='https://minecraft.gamepedia.com/api.php?action=query&generator=search&gsrsearch='+pagename+'&srsort=relevance&prop=info&format=json'
                s = requests.get(url,timeout=10)
                file = json.loads(s.text,object_pairs_hook=OrderedDict)
                x=file['query']['pages']
                for item in sorted(x.keys()):
                    a = open('search.txt',mode='a',encoding='UTF-8')
                    a.write(x[item]['title']+'\n')
                    a.close()
                m = open('search.txt',mode='r',encoding='UTF-8')
                await session.send(m.read())
                m.close()
            except KeyError:
                await session.send('什么都没找到。')
    except ConnectionError as e:
        await session.send('发生错误：无法连接至服务器。')
    except Exception as e:
        await session.send('发生错误：'+str(e))