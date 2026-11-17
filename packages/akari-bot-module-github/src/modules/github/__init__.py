from core.builtins.bot import Bot
from core.component import module
from modules.github.config import GithubConfig

from modules.github import repo, user, search

pat = GithubConfig.github_pat

github = module(
    "github",
    alias="gh",
    developers=["Dianliang233"],
    desc="{I18N:github.help.desc}",
    doc=True,
)


@github.command("<name> {{I18N:github.help}}")
async def _(msg: Bot.MessageSession, name: str):
    if "/" in name:
        await repo.repo(msg, name, pat)
    else:
        await user.user(msg, name, pat)


@github.command("repo <name> {{I18N:github.help.repo}}")
async def _(msg: Bot.MessageSession, name: str):
    await repo.repo(msg, name, pat)


@github.command("user <name> {{I18N:github.help.user}}")
async def _(msg: Bot.MessageSession, name: str):
    await user.user(msg, name, pat)


@github.command("search <keyword> {{I18N:github.help.search}}")
async def _(msg: Bot.MessageSession, keyword: str):
    await search.search(msg, keyword, pat)
