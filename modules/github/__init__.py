from core.builtins import Bot
from core.component import module
from modules.github import repo, user, search

github = module('github', alias='gh', developers=['Dianliang233'], desc='{github.help.desc}')


@github.command('<name> {{github.help}}')
async def _(msg: Bot.MessageSession, name: str):
    if '/' in name:
        await repo.repo(msg, name)
    else:
        await user.user(msg, name)


@github.command('repo <name> {{github.help.repo}}')
async def _(msg: Bot.MessageSession, name: str):
    await repo.repo(msg, name)


@github.command('user <name> {{github.help.user}}')
async def _(msg: Bot.MessageSession, name: str):
    await user.user(msg, name)


@github.command('search <keyword> {{github.help.search}}')
async def _(msg: Bot.MessageSession, keyword: str):
    await search.search(msg, keyword)
