from core.component import on_command
from core.elements import MessageSession
from modules.github import repo, user, search

github = on_command('github', alias=['gh'], developers=['Dianliang233'])


@github.handle('repo <name> {获取 GitHub 仓库信息}')
async def _(msg: MessageSession):
    await repo.repo(msg)


@github.handle(['user <name> {获取 GitHub 用户或组织信息}', 'org <name> {~github user 的别名}'])
async def _(msg: MessageSession):
    await user.user(msg)


@github.handle('search <query> {搜索 GitHub 上的仓库}')
async def _(msg: MessageSession):
    await search.search(msg)
