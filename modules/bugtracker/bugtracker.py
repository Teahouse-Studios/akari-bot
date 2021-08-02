import json
import re

from core.utils import get_url


async def bugtracker_get(MojiraID):
    Title = False
    Type = False
    TStatus = False
    Project = False
    Resolution = False
    Priority = False
    Version = False
    Link = False
    FixVersion = False
    Translation = False
    ID = str.upper(MojiraID)
    json_url = 'https://bugs.mojang.com/rest/api/2/issue/' + ID
    get_json = await get_url(json_url)
    get_spx = await get_url('https://spx.spgoding.com/bugs')
    if get_spx:
        spx = json.loads(get_spx)
        if ID in spx:
            Translation = re.sub(r"(\[backcolor=White\]\[font=Monaco,Consolas,'Lucida Console','Courier New',serif\]|\[/font\]\[/backcolor\])", '', spx[ID]['summary'])
    if get_json:
        load_json = json.loads(get_json)
        errmsg = ''
        if 'errorMessages' in load_json:
            for msg in load_json['errorMessages']:
                errmsg += '\n' + msg
        else:
            if 'key' in load_json:
                Title = f'[{load_json["key"]}] '
            if 'fields' in load_json:
                fields = load_json['fields']
                if 'summary' in fields:
                    if Translation:
                        Title = Title + fields['summary'] + f' ({Translation})' if Translation else ''
                    else:
                        Title = Title + fields['summary']
                if 'issuetype' in fields:
                    Type = fields['issuetype']['name']
                if 'status' in fields:
                    TStatus = fields['status']['name']
                if 'project' in fields:
                    Project = fields['project']['name']
                if 'resolution' in fields:
                    if fields['resolution'] is not None:
                        Resolution = fields['resolution']['name']
                    else:
                        Resolution = 'Unresolved'
                if 'versions' in load_json['fields']:
                    Versions = fields['versions']
                    verlist = []
                    for item in Versions[:]:
                        verlist.append(item['name'])
                    if verlist[0] == verlist[-1]:
                        Version = "Version: " + verlist[0]
                    else:
                        Version = "Versions: " + verlist[0] + " ~ " + verlist[-1]
                Link = 'https://bugs.mojang.com/browse/' + str.upper(MojiraID)
                if 'customfield_12200' in fields:
                    if fields['customfield_12200']:
                        Priority = "Mojang Priority: " + fields['customfield_12200']['value']
                if 'priority' in fields:
                    if fields['priority']:
                        Priority = "Priority: " + fields['priority']['name']
                if 'fixVersions' in fields:
                    if TStatus == 'Resolved':
                        if fields['fixVersions']:
                            print(fields['fixVersions'])
                            FixVersion = fields['fixVersions'][0]['name']
    else:
        return '发生错误：获取Json失败。'
    msglist = []
    if errmsg != '':
        msglist.append(errmsg)
    else:
        if Title:
            msglist.append(Title)
        if Type:
            Type = 'Type: ' + Type
            if TStatus in ['Open', 'Resolved']:
                Type = f'{Type} | Status: {TStatus}'
            msglist.append(Type)
        if Project:
            Project = 'Project: ' + Project
            msglist.append(Project)
        if TStatus:
            if TStatus not in ['Open', 'Resolved']:
                TStatus = 'Status: ' + TStatus
                msglist.append(TStatus)
        if Priority:
            msglist.append(Priority)
        if Resolution:
            Resolution = "Resolution: " + Resolution + ('\nFixed Version: ' + FixVersion if FixVersion else '')
            msglist.append(Resolution)
        if Version:
            msglist.append(Version)
        if Link:
            msglist.append(Link)
        msg = '\n'.join(msglist)
    return msg
