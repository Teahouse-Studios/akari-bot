import uuid

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Image, Plain, Url
from core.dirty_check import rickroll
from core.utils.http import download, get_url
from modules.github.utils import time_diff, dirty_check, dark_check


async def repo(msg: Bot.MessageSession, name: str, pat: str):
    try:
        result = await get_url(
            f"https://api.github.com/repos/{name}",
            200,
            fmt="json",
            headers={"Authorization": f"Bearer {pat}"} if pat else {},
        )
        rlicense = "Unknown"
        if "license" in result and result.get("license"):
            if "spdx_id" in result["license"]:
                rlicense = result["license"]["spdx_id"]
        is_fork = result.get("fork", False)
        parent = False

        if result.get("homepage"):
            website = str(Url(result["homepage"])) + "\n"
        else:
            website = ""

        if result.get("mirror_url"):
            mirror = f" (This is a mirror of {str(Url(result['mirror_url']))})"
        else:
            mirror = ""

        if is_fork:
            parent_name = result.get("parent", {}).get("name", "")
            parent = f" (This is a fork of {parent_name})"

        desc = result.get("description")
        if not desc:
            desc = ""
        else:
            desc = "\n" + desc

        message = f"""{result.get("full_name", "")} ({result.get("id", "")}){desc}
Fork · {result.get("forks_count", 0)} | Star · {result.get("stargazers_count", 0)} | Watch · {result.get("subscribers_count", 0)}
Language: {result.get("language", "")} | License: {rlicense}
Created {time_diff(result.get("created_at", ""))} ago | Updated {time_diff(result.get("updated_at", ""))} ago
{website}{str(Url(result.get("html_url", "")))}"""

        if mirror:
            message += "\n" + mirror

        if parent:
            message += "\n" + parent

        is_dirty = await dirty_check(msg, message, result.get("owner", {}).get("login", "")) or dark_check(message)
        if is_dirty:
            await msg.finish(rickroll())
        else:
            await msg.send_message(Plain(message))

        repo_hash = str(uuid.uuid4())
        download_pic = await download(
            url=f"https://opengraph.githubassets.com/{repo_hash}/{result['full_name']}",
            filename=f"{repo_hash}.png",
        )
        if download_pic:
            await msg.finish(Image(download_pic), quote=False)

    except ValueError as e:
        if str(e).startswith("404"):
            await msg.finish(I18NContext("github.message.repo.not_found"))
        else:
            raise e
