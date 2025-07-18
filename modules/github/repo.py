import uuid

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Image, Plain, Url
from core.dirty_check import rickroll
from core.utils.http import download, get_url
from modules.github.utils import time_diff, dirty_check, dark_check


async def repo(msg: Bot.MessageSession, name: str, pat: str):
    try:
        result = await get_url("https://api.github.com/repos/" + name, 200, fmt="json",
                               headers=[("Authorization", f"Bearer {pat}")] if pat else [])
        rlicense = "Unknown"
        if "license" in result and result["license"]:
            if "spdx_id" in result["license"]:
                rlicense = result["license"]["spdx_id"]
        is_fork = result["fork"]
        parent = False

        if result["homepage"]:
            website = "Website: " + str(Url(result["homepage"], md_format=msg.session_info.use_url_md_format)) + "\n"
        else:
            website = ""

        if result["mirror_url"]:
            mirror = f" (This is a mirror of {
                str(Url(result["mirror_url"], md_format=msg.session_info.use_url_md_format))} )"
        else:
            mirror = ""

        if is_fork:
            parent_name = result["parent"]["name"]
            parent = f" (This is a fork of {parent_name} )"

        desc = result["description"]
        if not desc:
            desc = ""
        else:
            desc = "\n" + result["description"]

        message = f"""{result["full_name"]} ({result["id"]}){desc}
Fork · {result["forks_count"]} | Star · {result["stargazers_count"]} | Watch · {result["watchers_count"]}
Language: {result["language"]} | License: {rlicense}
Created {time_diff(result["created_at"])} ago | Updated {time_diff(result["updated_at"])} ago
{website}{str(Url(result["html_url"], md_format=msg.session_info.use_url_md_format))}"""

        if mirror:
            message += "\n" + mirror

        if parent:
            message += "\n" + parent

        is_dirty = await dirty_check(message, result["owner"]["login"]) or dark_check(
            message
        )
        if is_dirty:
            await msg.finish(rickroll())
        else:
            await msg.send_message(Plain(message))

        repo_hash = str(uuid.uuid4())
        download_pic = await download(
            url=f"https://opengraph.githubassets.com/{repo_hash}/{result["full_name"]}",
            filename=f"{repo_hash}.png",
        )
        if download_pic:
            await msg.finish(Image(download_pic), quote=False)

    except ValueError as e:
        if str(e).startswith("404"):
            await msg.finish(I18NContext("github.message.repo.not_found"))
        else:
            raise e
