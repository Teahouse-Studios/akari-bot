from core.builtins import MessageSession
from core.config import Config
from core.logger import Logger
from modules.wiki.utils.rc import convert_rc_to_detailed_format
from modules.wiki.utils.wikilib import WikiLib


async def rc_qq(msg: MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    qq_account = Config("qq_account", cfg_type=(int, str), table_name="bot_aiocqhttp")
    query = await wiki.get_json(
        action="query",
        list="recentchanges",
        rcprop="title|user|timestamp|loginfo|comment|redirect|flags|sizes|ids",
        rclimit=99,
        rctype="edit|new|log",
        _no_login=not msg.options.get("use_bot_account", False),
    )
    wiki_info = wiki.wiki_info

    nodelist = [
        {
            "type": "node",
            "data": {
                "name": msg.locale.t("wiki.message.rc.qq.link.title"),
                "uin": int(qq_account),
                "content": [
                    {
                        "type": "text",
                        "data": {
                            "text": wiki_info.articlepath.replace(
                                "$1", "Special:RecentChanges"
                            )
                            + (
                                "\n" + msg.locale.t("wiki.message.rc.qq.link.prompt")
                                if wiki.wiki_info.in_allowlist
                                else ""
                            )
                        },
                    }
                ],
            },
        }
    ]

    rclist = await convert_rc_to_detailed_format(
        query["query"]["recentchanges"], wiki_info, msg
    )

    for x in rclist:
        nodelist.append(
            {
                "type": "node",
                "data": {
                    "name": msg.locale.t("wiki.message.rc.qq.title"),
                    "uin": int(qq_account),
                    "content": [{"type": "text", "data": {"text": x}}],
                },
            }
        )
    Logger.debug(nodelist)
    return nodelist


def compare_groups(old_groups, new_groups):
    added_groups = [group for group in new_groups if group not in old_groups]
    removed_groups = [group for group in old_groups if group not in new_groups]
    added = "+" + ", ".join(map(str, added_groups)) if added_groups else ""
    removed = "-" + ", ".join(map(str, removed_groups)) if removed_groups else ""
    return f"{added} {removed}" if added and removed else f"{added}{removed}"
