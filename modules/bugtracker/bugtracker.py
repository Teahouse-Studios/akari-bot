import os

import aiohttp
import ujson as json
from PIL import ImageFont

from config import CFG
from core.builtins import Url
from core.logger import Logger
from core.utils.http import download_to_cache, get_url

web_render = CFG.get_url('web_render')
web_render_local = CFG.get_url('web_render_local')
elements = ['div#descriptionmodule']
assets_path = os.path.abspath('./assets/')
font = ImageFont.truetype(f'{assets_path}/SourceHanSansCN-Normal.ttf', 15)

spx_cache = {}


async def make_screenshot(page_link, use_local=True):
    elements_ = elements.copy()
    if not web_render_local:
        if not web_render:
            Logger.warn('[Webrender] Webrender is not configured.')
            return False
        use_local = False
    Logger.info('[Webrender] Generating element screenshot...')
    try:
        img = await download_to_cache((web_render_local if use_local else web_render) + 'element_screenshot',
                                      status_code=200,
                                      headers={'Content-Type': 'application/json'},
                                      method="POST",
                                      post_data=json.dumps({
                                          'url': page_link,
                                          'element': elements_}),
                                      attempt=1,
                                      timeout=30,
                                      request_private_ip=True
                                      )
        if img:
            return img
        else:
            Logger.info('[Webrender] Generation Failed.')
            return False
    except aiohttp.ClientConnectorError:
        if use_local:
            return await make_screenshot(page_link, use_local=False)
        else:
            return False
    except ValueError:
        Logger.info('[Webrender] Generation Failed.')
        return False


async def bugtracker_get(session, mojira_id: str, nolink=False):
    data = {}
    id_ = mojira_id.upper()
    try:
        json_url = 'https://bugs.mojang.com/rest/api/2/issue/' + id_
        get_json = await get_url(json_url, 200)
    except ValueError as e:
        if str(e).startswith('401'):
            await session.finish(session.locale.t("bugtracker.message.get_failed"))
    if mojira_id not in spx_cache:
        get_spx = await get_url('https://bugs.guangyaostore.com/translations', 200)
        if get_spx:
            spx_cache.update(json.loads(get_spx))
    if id_ in spx_cache:
        data["translation"] = spx_cache[id_]
    if get_json:
        load_json = json.loads(get_json)
        errmsg = ''
        if 'errorMessages' in load_json:
            for msg in load_json['errorMessages']:
                errmsg += '\n' + msg
        else:
            if 'key' in load_json:
                data["title"] = f'[{load_json["key"]}] '
            if 'fields' in load_json:
                fields = load_json['fields']
                if 'summary' in fields:
                    data["title"] = data["title"] + \
                        fields['summary'] + (
                        f' (spx: {data["translation"]})' if data.get("translation", False) else '')
                if 'issuetype' in fields:
                    data["type"] = fields['issuetype']['name']
                if 'status' in fields:
                    data["status"] = fields['status']['name']
                if 'project' in fields:
                    data["project"] = fields['project']['name']
                if 'resolution' in fields:
                    data["resolution"] = fields['resolution']['name'] if fields[
                        'resolution'] else 'Unresolved'
                if 'versions' in load_json['fields']:
                    versions = fields['versions']
                    verlist = []
                    for item in versions[:]:
                        verlist.append(item['name'])
                    if verlist[0] == verlist[-1]:
                        data['version'] = "Version: " + verlist[0]
                    else:
                        data['version'] = "Versions: " + \
                                          verlist[0] + " ~ " + verlist[-1]
                data["link"] = 'https://bugs.mojang.com/browse/' + id_
                if 'customfield_12200' in fields:
                    if fields['customfield_12200']:
                        data["priority"] = "Mojang Priority: " + \
                                           fields['customfield_12200']['value']
                if 'priority' in fields:
                    if fields['priority']:
                        data["priority"] = "Priority: " + fields['priority']['name']
                if 'fixVersions' in fields:
                    if data["status"] == 'Resolved':
                        if fields['fixVersions']:
                            data["fixversion"] = fields['fixVersions'][0]['name']
    issue_link = None
    msglist = []
    if errmsg != '':
        msglist.append(errmsg)
    else:
        if title := data.get("title", False):
            msglist.append(title)
        if type_ := data.get("type", False):
            type_ = 'Type: ' + type_
            if status_ := data.get("status", False):
                if status_ in ['Open', 'Resolved']:
                    type_ = f'{type_} | Status: {status_}'
            msglist.append(type_)
        if project := data.get("project", False):
            project = 'Project: ' + project
            msglist.append(project)
        if status_ := data.get("status", False):
            if status_ not in ['Open', 'Resolved']:
                status_ = 'Status: ' + status_
                msglist.append(status_)
        if priority := data.get("priority", False):
            msglist.append(priority)
        if resolution := data.get("resolution", False):
            resolution = "Resolution: " + resolution
            msglist.append(resolution)
        if fixversion := data.get("fixversion", False):
            msglist.append("Fixed Version: " + fixversion)
        if version := data.get("version", False):
            msglist.append(version)
        if (link := data.get("link", False)) and not nolink:
            msglist.append(str(Url(link)))
            issue_link = link
    msg = '\n'.join(msglist)
    return msg, issue_link
