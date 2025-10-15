import re
import urllib.parse

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Plain, Url
from core.dirty_check import check_bool, rickroll
from core.logger import Logger
from modules.wiki.utils.utils import strptime2ts
from modules.wiki.utils.wikilib import WikiLib


async def get_user_info(msg: Bot.MessageSession, username, wikiurl, headers=None):
    wiki = WikiLib(wikiurl, headers)
    if not await wiki.check_wiki_available():
        return I18NContext("wiki.message.user.wiki_unavailable", wikiurl=wikiurl)
    await wiki.fixup_wiki_info()
    match_interwiki = re.match(r"(.*?):(.*)", username)
    if match_interwiki:
        if match_interwiki.group(1) in wiki.wiki_info.interwiki:
            await get_user_info(
                msg,
                match_interwiki.group(2),
                wiki.wiki_info.interwiki[match_interwiki.group(1)],
                headers
            )

    data = {}
    base_user_info = (
        await wiki.get_json(
            action="query",
            list="users",
            ususers=username,
            usprop="groups|blockinfo|registration|editcount|gender",
        )
    )["query"]["users"][0]
    if "missing" in base_user_info:
        return I18NContext("wiki.message.user.not_found")

    if await check_bool(base_user_info["name"], msg):
        return Plain(rickroll())
    data["username"] = base_user_info["name"]
    data["url"] = re.sub(
        r"\$1", urllib.parse.quote("User:" + username), wiki.wiki_info.articlepath
    )

    groups = {}
    get_groups = await wiki.get_json(
        action="query", meta="allmessages", amprefix="group-"
    )
    if "query" in get_groups:
        for a in get_groups["query"]["allmessages"]:
            groups[re.sub("^group-", "", a["name"])] = a["*"]

    user_central_auth_data = {}
    if "CentralAuth" in wiki.wiki_info.extensions:
        user_central_auth_data = await wiki.get_json(
            action="query",
            meta="globaluserinfo",
            guiuser=username,
            guiprop="editcount|groups",
        )
    data["users_groups"] = []
    users_groups_ = base_user_info.get("groups", [])
    for x in users_groups_:
        if x != "*":
            data["users_groups"].append(groups[x] if x in groups else x)
    data["global_users_groups"] = []
    if "query" in user_central_auth_data:
        data["global_edit_count"] = str(
            user_central_auth_data["query"]["globaluserinfo"].get("editcount", 0)
        )
        data["global_home"] = user_central_auth_data["query"]["globaluserinfo"]["home"]
        for g in user_central_auth_data["query"]["globaluserinfo"]["groups"]:
            data["global_users_groups"].append(groups[g] if g in groups else g)

    data["registration_time"] = base_user_info.get("registration")
    data["registration_time"] = (
        msg.format_time(strptime2ts(data["registration_time"]))
        if data["registration_time"]
        else "{I18N:message.unknown}"
    )
    data["edited_count"] = str(base_user_info.get("editcount", 0))
    data["gender"] = base_user_info.get("gender")
    if data["gender"] == "female":
        data["gender"] = "{I18N:wiki.message.user.gender.female}"
    elif data["gender"] == "male":
        data["gender"] = "{I18N:wiki.message.user.gender.male}"
    else:
        data["gender"] = "{I18N:message.unknown}"
    # if one day LGBTers...

    if "blockedby" in base_user_info:
        data["blocked_by"] = base_user_info.get("blockedby")
        data["blocked_time"] = base_user_info.get("blockedtimestamp")
        data["blocked_time"] = (
            msg.format_time(strptime2ts(data["blocked_time"]))
            if data["blocked_time"]
            else "{I18N:message.unknown}"
        )
        data["blocked_expires"] = base_user_info.get("blockexpiry")
        if data["blocked_expires"]:
            if data["blocked_expires"] != "infinite":
                data["blocked_expires"] = msg.format_time(
                    strptime2ts(data["blocked_expires"])
                )
        else:
            data["blocked_expires"] = "{I18N:message.unknown}"
        data["blocked_reason"] = base_user_info.get("blockreason")
        data["blocked_reason"] = (
            data["blocked_reason"]
            if data["blocked_reason"]
            else "{I18N:message.unknown}"
        )

    Logger.debug(str(data))
    msgs = []
    if user := data.get("username", ""):
        msgs.append(Plain(
            str(I18NContext("wiki.message.user.username"))
            + user
            + (
                " | "
                + str(I18NContext("wiki.message.user.edited_count"))
                + data["edited_count"]
                if "edited_count" in data and "created_page_count" not in data
                else ""
            ))
        )
    if users_groups := data.get("users_groups", ""):
        msgs.append(Plain(
            str(I18NContext("wiki.message.user.users_groups"))
            + "{I18N:message.delimiter}".join(users_groups)
        ))
    if gender_ := data.get("gender", ""):
        msgs.append(Plain(str(I18NContext("wiki.message.user.gender")) + gender_))
    if registration := data.get("registration_time", ""):
        msgs.append(Plain(str(I18NContext("wiki.message.user.registration_time")) + registration))
    if edited_wiki_count := data.get("edited_wiki_count", ""):
        msgs.append(Plain(
            str(I18NContext("wiki.message.user.edited_wiki_count")) + edited_wiki_count
        ))

    sub_edit_counts1 = []
    if created_page_count := data.get("created_page_count", ""):
        sub_edit_counts1.append(
            str(I18NContext("wiki.message.user.created_page_count")) + created_page_count
        )
    if edited_count := data.get("edited_count", ""):
        if created_page_count:
            sub_edit_counts1.append(
                str(I18NContext("wiki.message.user.edited_count")) + edited_count
            )
    sub_edit_counts2 = []
    if deleted_count := data.get("deleted_count", ""):
        sub_edit_counts2.append(
            str(I18NContext("wiki.message.user.deleted_count")) + deleted_count
        )
    if patrolled_count := data.get("patrolled_count", ""):
        sub_edit_counts2.append(
            str(I18NContext("wiki.message.user.patrolled_count")) + patrolled_count
        )
    sub_edit_counts3 = []
    if site_rank := data.get("site_rank", ""):
        sub_edit_counts3.append(str(I18NContext("wiki.message.user.site_rank")) + site_rank)
    if global_rank := data.get("global_rank", ""):
        sub_edit_counts3.append(
            str(I18NContext("wiki.message.user.global_rank")) + global_rank
        )
    if sub_edit_counts1:
        msgs.append(Plain(" | ".join(sub_edit_counts1)))
    if sub_edit_counts2:
        msgs.append(Plain(" | ".join(sub_edit_counts2)))
    if sub_edit_counts3:
        msgs.append(Plain(" | ".join(sub_edit_counts3)))

    if global_users_groups := data.get("global_users_groups", ""):
        msgs.append(Plain(
            str(I18NContext("wiki.message.user.global_users_groups"))
            + "{I18N:message.delimiter}".join(global_users_groups)
        ))
    if global_edit_count := data.get("global_edit_count", ""):
        msgs.append(Plain(
            str(I18NContext("wiki.message.user.global_edited_count")) + global_edit_count
        ))
    if global_home := data.get("global_home", ""):
        msgs.append(Plain(str(I18NContext("wiki.message.user.global_home")) + global_home))

    if blocked_by := data.get("blocked_by", False):
        msgs.append(Plain(str(I18NContext("wiki.message.user.blocked", user=user))))
        msgs.append(Plain(
            str(I18NContext(
                "wiki.message.user.blocked.detail",
                blocked_by=blocked_by,
                blocked_time=data["blocked_time"],
                blocked_expires=data["blocked_expires"],
            )))
        )
        msgs.append(Plain(
            str(I18NContext("wiki.message.user.blocked.reason")) + data["blocked_reason"]
        ))

    if url := data.get("url", ""):
        msgs.append(Url(url, use_mm=msg.session_info.use_url_manager and not wiki.wiki_info.in_allowlist))
    return MessageChain.assign(msgs)
