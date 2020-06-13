# -*- coding:utf-8 -*-
import requests
from xml.etree import ElementTree
import json
import string
import os, sys
import http.client
import hashlib
import urllib
import random

async def bugcb(pagename):
    appid = '20200328000407172'
    secretKey = '9wUEKfwOtQsMh_2Ozr7R'
    httpClient = None
    myurl = '/api/trans/vip/translate'
    fromLang = 'en'   #原文语种
    toLang = 'zh' 
    salt = random.randint(32768, 65536)
    try:
        try:
            try:
                os.remove('bug_cache_text.txt')
            except Exception:
                pass
            url_str ='https://bugs.mojang.com/si/jira.issueviews:issue-xml/'+ str.upper(pagename) + '/' + str.upper(pagename) + '.xml'
            respose_str =  requests.get(url_str,timeout=10)
            try:
                respose_str.encoding = 'utf-8'
                root = ElementTree.XML(respose_str.text)
                for node in root.iter("channel"):
                    for node in root.iter("item"):
                        Title = node.find("title").text
                        q = node.find("title").text
                        Type = "类型：" + node.find("type").text
                        Project = "项目：" + node.find("project").text
                        TStatus = "进度：" + node.find("status").text
                        Resolution = "状态：" + node.find("resolution").text
                        Link = node.find("link").text
                sign = appid + q + str(salt) + secretKey
                sign = hashlib.md5(sign.encode()).hexdigest()
                myurl = myurl + '?appid=' + appid + '&q=' + urllib.parse.quote(q) + '&from=' + fromLang + '&to=' + toLang + '&salt=' + str(salt) + '&sign=' + sign +'&action=1'
                url_json = 'https://bugs.mojang.com/rest/api/2/issue/'+str.upper(pagename)
                json_text = requests.get(url_json,timeout=10)
                file = json.loads(json_text.text)
                Versions = file['fields']['versions']
                name = []
                for item in Versions[:]:
                    name.append(item['name'])
                httpClient = http.client.HTTPConnection('api.fanyi.baidu.com')
                httpClient.request('GET', myurl)
                response = httpClient.getresponse()
                result_all = response.read().decode("utf-8")
                result = json.loads(result_all)
                for item in result['trans_result']:
                    dst=item['dst']
                if name[0] == name[-1]:
                    Version = "Version: "+name[0]
                else:
                    Version = "Versions: "+name[0]+"~"+name[-1]
                try:
                    Priority = "Mojang Priority: "+file['fields']['customfield_12200']['value']
                    return(Title+'\n'+dst+'\n'+Type+'\n'+Project+'\n'+TStatus+'\n'+Priority+'\n'+Resolution+'\n'+Version+'\n'+Link+'\n'+'由百度翻译提供支持。')
                    z.close()
                    os.remove('bug_cache_text.txt')
                except Exception:
                    return(Title+'\n'+dst+'\n'+Type+'\n'+Project+'\n'+TStatus+'\n'+Resolution+'\n'+Version+'\n'+Link+'\n'+'由百度翻译提供支持。')
            except Exception:
                try:
                    respose_str.encoding = 'utf-8'
                    root = ElementTree.XML(respose_str.text)
                    for node in root.iter("channel"):
                        for node in root.iter("item"):
                            Title = node.find("title").text
                            q = node.find("title").text
                            Type = "类型：" + node.find("type").text
                            TStatus = "项目：" + node.find("status").text
                            Resolution = "进度：" + node.find("resolution").text
                            Priority = "Mojang优先级：" + node.find("priority").text
                            Link = node.find("link").text
                    sign = appid + q + str(salt) + secretKey
                    sign = hashlib.md5(sign.encode()).hexdigest()
                    myurl = myurl + '?appid=' + appid + '&q=' + urllib.parse.quote(q) + '&from=' + fromLang + '&to=' + toLang + '&salt=' + str(salt) + '&sign=' + sign
                    httpClient = http.client.HTTPConnection('api.fanyi.baidu.com')
                    httpClient.request('GET', myurl,timeout=10)
                    response = httpClient.getresponse()
                    result_all = response.read().decode("utf-8")
                    result = json.loads(result_all)
                    for item in result['trans_result']:
                        dst=item['dst']
                    return(Title+'\n'+dst+'\n'+Type+'\n'+TStatus+'\n'+Priority+'\n'+Resolution+'\n'+Link+'\n'+'由百度翻译提供支持。')
                except Exception:
                    try:
                        respose_str.encoding = 'utf-8'
                        root = ElementTree.XML(respose_str.text)
                        for node in root.iter("channel"):
                            for node in root.iter("item"):
                                Link = node.find("link").text
                                return(Link)
                    except Exception as e:      
                        return("发生错误："+str(e)+".")
        except Exception as e:      
            return("发生错误："+str(e)+".")
    except Exception as e:      
            return("发生错误："+str(e)+".")