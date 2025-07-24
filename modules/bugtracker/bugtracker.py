import orjson as json

from core.builtins.message.internal import I18NContext, Plain
from core.logger import Logger
from core.utils.http import post_url, get_url
from core.utils.image import cb64imglst
from core.web_render import web_render, ElementScreenshotOptions

elements = ["div[class^='MuiContainer-root']"]

spx_cache = {}


async def make_screenshot(page_link):
    elements_ = elements.copy()
    Logger.info("[WebRender] Generating element screenshot...")
    try:
        imgs = await web_render.element_screenshot(ElementScreenshotOptions(url=page_link, element=elements_))
        if imgs:
            return cb64imglst(imgs, bot_img=True)
        return False
    except Exception:
        Logger.exception("[WebRender] Generation Failed.")
        return False


async def bugtracker_get(msg, mojira_id: str):
    data = {}
    id_ = mojira_id.upper()

    get_json = await post_url(
        "https://bugs.mojang.com/api/jql-search-post",
        f"""{{
            "advanced": true,
            "project": "{id_.split("-", 1)[0]}",
            "search": "key = {id_}",
            "maxResults": 1
        }}""",
        201,
        headers={"Content-Type": "application/json"},
    )
    try:
        load_json = json.loads(get_json).get("issues")[0]
    except IndexError:
        return I18NContext("bugtracker.message.get_failed"), None
    if mojira_id not in spx_cache:
        get_spx = await get_url(
            "https://spxx-db.teahouse.team/crowdin/zh-CN/zh_CN.json", 200
        )
        if get_spx:
            spx_cache.update(json.loads(get_spx))
    if id_ in spx_cache and msg.session_info.locale.locale == "zh_cn":
        data["translation"] = spx_cache[id_]
    if get_json:
        errmsg = ""
        if "errorMessages" in load_json:
            for msgs in load_json["errorMessages"]:
                errmsg += "\n" + msgs
        else:
            if "key" in load_json:
                data["title"] = f"[{load_json["key"]}] "
            if "fields" in load_json:
                fields = load_json["fields"]
                if "summary" in fields:
                    data["title"] = (
                        data["title"]
                        + fields["summary"]
                        + (
                            f" (spx: {data["translation"]})"
                            if data.get("translation", False)
                            else ""
                        )
                    )
                if "issuetype" in fields:
                    data["type"] = fields["issuetype"]["name"]
                if "status" in fields:
                    data["status"] = fields["status"]["name"]
                if "project" in fields:
                    data["project"] = fields["project"]["name"]
                if "resolution" in fields:
                    data["resolution"] = (
                        fields["resolution"]["name"]
                        if fields["resolution"]
                        else "Unresolved"
                    )
                if "versions" in load_json["fields"]:
                    versions = fields["versions"]
                    verlist = []
                    for item in versions[:]:
                        verlist.append(item["name"])
                    if verlist[0] == verlist[-1]:
                        data["version"] = "Version: " + verlist[0]
                    else:
                        data["version"] = (
                            "Versions: " + verlist[0] + " ~ " + verlist[-1]
                        )
                data["link"] = f"https://bugs.mojang.com/browse/{id_.split("-", 1)[0]}/issues/" + id_
                if "customfield_12200" in fields:
                    if fields["customfield_12200"]:
                        data["priority"] = (
                            "Mojang Priority: " + fields["customfield_12200"]["value"]
                        )
                if "priority" in fields:
                    if fields["priority"]:
                        data["priority"] = "Priority: " + fields["priority"]["name"]
                if "fixVersions" in fields:
                    if data["status"] == "Resolved":
                        if fields["fixVersions"]:
                            data["fixversion"] = fields["fixVersions"][0]["name"]
    issue_link = None
    msglist = []
    if errmsg != "":
        msglist.append(errmsg)
    else:
        if title := data.get("title", False):
            msglist.append(title)
        if type_ := data.get("type", False):
            type_ = "Type: " + type_
            if status_ := data.get("status", False):
                if status_ in ["Open", "Resolved"]:
                    type_ = f"{type_} | Status: {status_}"
            msglist.append(type_)
        if project := data.get("project", False):
            project = "Project: " + project
            msglist.append(project)
        if status_ := data.get("status", False):
            if status_ not in ["Open", "Resolved"]:
                status_ = "Status: " + status_
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
        if link := data.get("link", False):
            issue_link = link
    return Plain("\n".join(msglist)), issue_link
