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
                        Type = "Type: " + node.find("type").text
                        Project = "Project: " + node.find("project").text
                        TStatus = "Status: " + node.find("status").text
                        Resolution = "Resolution: " + node.find("resolution").text
                        Link = node.find("link").text
                sign = appid + q + str(salt) + secretKey
                sign = hashlib.md5(sign.encode()).hexdigest()
                myurl = myurl + '?appid=' + appid + '&q=' + urllib.parse.quote(q) + '&from=' + fromLang + '&to=' + toLang + '&salt=' + str(salt) + '&sign=' + sign +'&action=1'
                url_json = 'https://bugs.mojang.com/rest/api/2/issue/'+str.upper(pagename)
                json_text = requests.get(url_json,timeout=10)
                file = json.loads(json_text.text)
                Versions = file['fields']['versions']
                for item in Versions[:]:
                    name = item['name']+"|"
                    y = open('bug_cache_text.txt',mode='a',encoding='utf-8')
                    y.write(name)
                    y.close()
                z = open('bug_cache_text.txt',mode='r',encoding='utf-8')
                j = z.read()
                m = j.strip(string.punctuation)
                httpClient = http.client.HTTPConnection('api.fanyi.baidu.com')
                httpClient.request('GET', myurl)
                response = httpClient.getresponse()
                result_all = response.read().decode("utf-8")
                result = json.loads(result_all)
                for item in result['trans_result']:
                    dst=item['dst']
                if m.split('|')[0] == m.split('|')[-1]:
                    Version = "Version: "+m.split('|')[0]
                else: 
                    Version = "Versions: "+m.split('|')[0]+"~"+m.split('|')[-1]
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
                            Type = "Type: " + node.find("type").text
                            TStatus = "Status: " + node.find("status").text
                            Resolution = "Resolution: " + node.find("resolution").text
                            Priority = "Priority: " + node.find("priority").text
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