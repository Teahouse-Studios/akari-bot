from core.elements import MessageSession
from database import BotDBUtil


async def warn_target(msg: MessageSession, reason=None):
    current_warns = int(msg.target.senderInfo.query.warns) + 1
    msg.target.senderInfo.edit('warns', current_warns)
    warn_template = ['警告：',
                     '根据服务条款，你已违反我们的行为准则。']
    if reason is not None:
        warn_template.append('具体原因：' + reason)
    if current_warns < 5:
        warn_template.append(f'这是对你的第{current_warns}次警告。如超过5次警告，我们将会把你的账户加入黑名单。')
    if current_warns <= 2:
        warn_template.append(f'如果你有任何异议，请至https://github.com/Teahouse-Studios/bot/issues/new/choose发起issue。')
    if current_warns == 5:
        warn_template.append(f'这是对你的最后一次警告。')
    if current_warns > 5:
        msg.target.senderInfo.edit('isInBlockList', True)
        return
    await msg.sendMessage('\n'.join(warn_template))


async def pardon_user(user: str):
    BotDBUtil.SenderInfo(user).edit('warns', 0)


async def warn_user(user: str, count=1):
    current_warns = int(BotDBUtil.SenderInfo(user).query.warns) + count
    BotDBUtil.SenderInfo(user).edit('warns', current_warns)
    if current_warns > 5:
        BotDBUtil.SenderInfo(user).edit('isInBlockList', True)
    return current_warns
