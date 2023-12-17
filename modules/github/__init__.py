from core.builtins import Bot
from core.component import module
from modules.github import repo, user, search

github = module('github', alias='gh', developers=['Dianliang233'], desc='{github.help.desc}')


@github.handle('<name> {{github.help}}')
async def _(msg: Bot.MessageSession, name: str):
    if '/' in name:
        await repo.repo(msg)
    else:
        await user.user(msg)


@github.handle('repo <name> {{github.help.repo}}')
async def _(msg: Bot.MessageSession):
    await repo.repo(msg)


@github.handle(('user <name> {{github.help.user}}'))
async def _(msg: Bot.MessageSession):
    await user.user(msg)


@github.handle('search <query> {{github.help.search}}')
async def _(msg: Bot.MessageSession):
    await search.search(msg)
