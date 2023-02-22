from core.builtins import Bot
from core.component import on_command
from modules.github import repo, user, search

github = on_command('github', alias=['gh'], developers=['Dianliang233'])


@github.handle('<name> {尝试自动识别并区分 repo/user}')
async def _(msg: Bot.MessageSession):
    if '/' in msg.parsed_msg['<name>']:
        await repo.repo(msg)
    else:
        await user.user(msg)


@github.handle('repo <name> {获取 GitHub 仓库信息}')
async def _(msg: Bot.MessageSession):
    await repo.repo(msg)


@github.handle(['user <name> {获取 GitHub 用户或组织信息}', 'org <name> {~github user 的别名}'])
async def _(msg: Bot.MessageSession):
    await user.user(msg)


@github.handle('search <query> {搜索 GitHub 上的仓库}')
async def _(msg: Bot.MessageSession):
    await search.search(msg)
