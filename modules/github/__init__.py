from core.builtins import Bot
from core.component import module
from modules.github import repo, user, search

github = module('github', alias='gh', developers=['Dianliang233'], desc='{github.help.desc}')


@github.command('<name> {{github.help}}')
async def _(msg: Bot.MessageSession, name: str):
    if '/' in name:
        await repo.repo(msg)
    else:
        await user.user(msg)


@github.command('repo <name> {{github.help.repo}}')
async def _(msg: Bot.MessageSession):
    await repo.repo(msg)


@github.command('user <name> {{github.help.user}}')
async def _(msg: Bot.MessageSession):
    await user.user(msg)


@github.command('search <query> {{github.help.search}}')
async def _(msg: Bot.MessageSession):
    await search.search(msg)
