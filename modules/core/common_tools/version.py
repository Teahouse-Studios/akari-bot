from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Url
from core.config.base import CoreConfig
from core.utils.bash import run_sys_command
from modules.core.common_tools.about import about
from modules.core.common_tools.version_utils import get_version_display


@about.command("version {{I18N:core.help.about.version}}")
async def _(msg: Bot.MessageSession):
    if version_display := get_version_display():
        send_msgs = MessageChain.assign(
            I18NContext("core.message.about.version", version=version_display, disable_joke=True)
        )
        if str(Bot.Info.version).startswith("git:"):
            if CoreConfig.enable_commit_url:
                returncode, repo_url, _ = await run_sys_command(["git", "config", "--get", "remote.origin.url"])
                if returncode == 0:
                    repo_url = repo_url.strip().replace(".git", "")
                    commit_url = f"{repo_url}/commit/{version_display}"
                    send_msgs.append(Url(commit_url, trusted=True))
        else:
            if CoreConfig.enable_commit_url:
                version_tag = "nightly" if version_display.startswith("nightly") else version_display
                returncode, repo_url, _ = await run_sys_command(["git", "config", "--get", "remote.origin.url"])
                if returncode == 0:
                    repo_url = repo_url.strip().replace(".git", "")
                    commit_url = f"{repo_url}/releases/tag/{version_tag}"
                    send_msgs.append(Url(commit_url, trusted=True))
        await msg.finish(send_msgs)
    else:
        await msg.finish(I18NContext("core.message.about.version.unknown"))
