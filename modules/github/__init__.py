from core.elements import MessageSession
from core.decorator import on_command
from modules.github import repo, user, search


@on_command('github', alias=['gh'], help_doc=(
        '~github repo <name> {获取 GitHub 仓库信息}',
        '~github user <name> {获取 GitHub 用户或组织信息}',
        '~github org <name> {~github user 的别名}',
        '~github search <query> {搜索 GitHub 上的仓库}'),
            developers=['Dianliang233'],
            allowed_none=False)
async def github(msg: MessageSession):
    if msg.parsed_msg['repo']:
        return await repo.repo(msg)
    elif msg.parsed_msg['user'] or msg.parsed_msg['org']:
        return await user.user(msg)
    elif msg.parsed_msg['search']:
        return await search.search(msg)
    else:
        return await msg.sendMessage('发生错误：指令使用错误，请选择 repo、user 或 search 工作模式。使用 ~help github 查看详细帮助。')
