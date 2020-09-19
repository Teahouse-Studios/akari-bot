# -*- coding:utf-8 -*-
import json
from xml.etree import ElementTree

import aiohttp


async def bug(pagename):
    try:
        url_str = 'https://bugs.mojang.com/si/jira.issueviews:issue-xml/' + str.upper(pagename) + '/' + str.upper(
            pagename) + '.xml'
        async with aiohttp.ClientSession() as session:
            async with session.get(url_str, timeout=aiohttp.ClientTimeout(total=20)) as req:
                if req.status != 200:
                    return f"请求时发生错误：{req.status}"
                else:
                    respose_str = await req.text()
        try:
            root = ElementTree.XML(respose_str)
            for node in root.iter("channel"):
                for node in root.iter("item"):
                    Title = node.find("title").text
                    Type = "Type: " + node.find("type").text
                    Project = "Project: " + node.find("project").text
                    TStatus = "Status: " + node.find("status").text
                    Resolution = "Resolution: " + node.find("resolution").text
                    Link = node.find("link").text
            url_json = 'https://bugs.mojang.com/rest/api/2/issue/' + str.upper(pagename)
            async with aiohttp.ClientSession() as session2:
                async with session2.get(url_json, timeout=aiohttp.ClientTimeout(total=5)) as reqjson:
                    if reqjson.status != 200:
                        return f"请求时发生错误：{reqjson.status}"
                    else:
                        json_text = await reqjson.text()
            file = json.loads(json_text)
            Versions = file['fields']['versions']
            name = []
            for item in Versions[:]:
                name.append(item['name'])
            if name[0] == name[-1]:
                Version = "Version: " + name[0]
            else:
                Version = "Versions: " + name[0] + " ~ " + name[-1]
            try:
                Priority = "Mojang Priority: " + file['fields']['customfield_12200']['value']
                if TStatus == 'Status: Open':
                    Type = "Type: " + node.find("type").text + ' | Status: ' + node.find("status").text
                    return (
                            Title + '\n' + Type + '\n' + Project + '\n' + Priority + '\n' + Resolution + '\n' + Version + '\n' + Link)
                elif TStatus == 'Status: Resolved':
                    Resolution = "Resolution: " + node.find("resolution").text + ' | Fixed Version: ' + node.find(
                        "fixVersion").text
                    Type = Type + ' | ' + TStatus
                    return (
                            Title + '\n' + Type + '\n' + Project + '\n' + Resolution + '\n' + Priority + '\n' + Version + '\n' + Link)
                else:
                    return (
                            Title + '\n' + Type + '\n' + Project + '\n' + TStatus + '\n' + Priority + '\n' + Resolution + '\n' + Version + '\n' + Link)
            except Exception:
                try:
                    if TStatus == 'Status: Open':
                        Type = "Type: " + node.find("type").text + ' | Status: ' + node.find("status").text
                        return (Title + '\n' + Type + '\n' + Project + '\n' + Resolution + '\n' + Version + '\n' + Link)
                    elif TStatus == 'Status: Resolved':
                        Resolution = "Resolution: " + node.find("resolution").text + ' | Fixed Version: ' + node.find(
                            "fixVersion").text
                        Type = Type + ' | ' + TStatus
                        return (Title + '\n' + Type + '\n' + Project + '\n' + Resolution + '\n' + Version + '\n' + Link)
                    else:
                        return (
                                Title + '\n' + Type + '\n' + Project + '\n' + TStatus + '\n' + Resolution + '\n' + Version + '\n' + Link)
                except Exception:
                    return (
                            Title + '\n' + Type + '\n' + Project + '\n' + TStatus + '\n' + Resolution + '\n' + Version + '\n' + Link)
        except Exception:
            try:
                return (
                        Title + '\n' + Type + '\n' + Project + '\n' + TStatus + '\n' + Priority + '\n' + Resolution + '\n' + Link)
            except Exception:
                try:
                    return (Title + '\n' + Type + '\n' + Project + '\n' + TStatus + '\n' + Resolution + '\n' + Link)
                except Exception:
                    try:
                        return (Link)
                    except Exception as e:
                        return ("发生错误：此漏洞可能不存在，以下为traceback：\n" + str(e) + ".")
    except Exception as e:
        return ("发生错误：" + str(e) + ".")
