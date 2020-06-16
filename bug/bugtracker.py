# -*- coding:utf-8 -*-
import requests
from xml.etree import ElementTree
import json
import string
import os, sys

def bug(pagename):
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
                    Type = "Type: " + node.find("type").text
                    Project = "Project: " + node.find("project").text
                    TStatus = "Status: " + node.find("status").text
                    Resolution = "Resolution: " + node.find("resolution").text
                    Link = node.find("link").text
            if TStatus == 'Status: Resolved':
                TStatus = "Status: " + node.find("status").text + ' | Fixed Version: '+ node.find("fixVersion").text
            url_json = 'https://bugs.mojang.com/rest/api/2/issue/'+str.upper(pagename)
            json_text = requests.get(url_json,timeout=10)
            file = json.loads(json_text.text)
            Versions = file['fields']['versions']
            name = []
            for item in Versions[:]:
                name.append(item['name'])
            if name[0] == name[-1]:
                Version = "Version: "+name[0]
            else:
                Version = "Versions: "+name[0]+"~"+name[-1]
            try:
                Priority = "Mojang Priority: "+file['fields']['customfield_12200']['value']
                return(Title+'\n'+Type+'\n'+Project+'\n'+TStatus+'\n'+Priority+'\n'+Resolution+'\n'+Version+'\n'+Link)
            except Exception:
                return (Title+'\n'+Type+'\n'+Project+'\n'+TStatus+'\n'+Resolution+'\n'+Version+'\n'+Link)
        except Exception:
            try:
                return (Title+'\n'+Type+'\n'+TStatus+'\n'+Priority+'\n'+Resolution+'\n'+Link)
            except Exception:
                try:
                    return(Link)
                except Exception as e:
                    return ("发生错误："+str(e)+".")
    except Exception as e:      
        return ("发生错误："+str(e)+".")