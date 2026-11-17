from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from core.utils.bash import run_sys_command

upd = module("update", required_superuser=True, base=True, doc=True)


async def pull_repo(force: bool = False):
    if force:
        await run_sys_command(["git", "reset", "--hard"], timeout=60)
    returncode, output, error = await run_sys_command(["git", "pull"], timeout=60)
    if returncode != 0:
        return error
    return output


async def update_dependencies():
    returncode, _, uv_sync = await run_sys_command(["uv", "sync"], timeout=60)
    if returncode == 0:
        return uv_sync
    _, pip_install, _ = await run_sys_command(["pip", "install", "-r", "requirements.txt"], timeout=60)
    return "..." + pip_install[-500:] if len(pip_install) > 500 else pip_install


@upd.command("[--force] {{I18N:core.help.update}}", options_desc={"--force": "{I18N:core.help.update.option.force}"})
async def _(msg: Bot.MessageSession, force: bool = False):
    if not Bot.Info.binary_mode:
        if Bot.Info.version and Bot.Info.version.startswith("git:"):
            pull_repo_result = await pull_repo(force)
            if pull_repo_result:
                await msg.send_message(Plain(pull_repo_result, disable_joke=True))

        update_dependencies_result = await update_dependencies()
        if update_dependencies_result:
            await msg.finish(Plain(update_dependencies_result, disable_joke=True))
    else:
        await msg.finish(I18NContext("core.message.update.binary_mode"))
