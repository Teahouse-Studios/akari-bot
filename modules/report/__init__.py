import ujson as json
from core.builtins import Bot
from core.component import on_command, on_schedule
from core.scheduler import CronTrigger

rp = on_command('report', developers='haoye_qwq', desc='汇报bug', base=True)


def read():
    _data = json.load(open('./modules/report/bugs.json', 'r'))
    return _data


def write(data: str, frome: str):
    if read() is None:
        _data = [{'bug': data, 'from': frome}]
    else:
        _data = read().append({'bug': data, 'from': frome})
    json.dump(_data, open('./modules/report/bugs.json', 'w'))


def delete(bug_id: int):
    data = read()
    json.dump(data.pop(bug_id), open('./modules/report/bugs.json', 'w'))


@rp.handle('open <bug> {汇报一个bug}', required_admin=True)
async def opn(msg: Bot.MessageSession):
    if read() is None:
        length = 1
    else:
        length = len(read())+1
    write(f"#{length}:\n{msg.parsed_msg['<bug>']}\n——{msg.target.senderName}({msg.target.senderId})",
          msg.target.targetId)
    await msg.sendMessage('已添加: #' + str(length))


@rp.handle('close <bug_id> {完成bug修复}', required_superuser=True)
async def cls(msg: Bot.MessageSession):
    try:
        _id = int(msg.parsed_msg['<bug_id>'])
        grpid = read()[_id]['from']
        await Bot.FetchTarget.fetch_target(grpid).sendDirectMessage('已修复#' + str(_id))
        delete(_id)

    except Exception:
        await msg.sendMessage('不存在的id，请检查输入')


@rp.handle('list {你有几个bug?}', required_superuser=True)
async def lst(msg: Bot.MessageSession):
    _msg = []
    if read() is None:
        await msg.sendMessage('没有bug!')
    else:
        for i in read():
            _msg.append(f"来自会话{i['from']}#{len(read())}:\n{i['bug']}")
        await msg.sendMessage('待解决的bug:\n' + ',\n'.join(_msg))


on_schedule(
    bind_prefix='post_bug',
    trigger=CronTrigger.from_crontab('30 10 * * *'),
    desc='推送bug',
    developers='haoye_qwq',
    required_superuser=True
)


async def post(bot: Bot.FetchTarget):
    _msg = []
    if read() is None:
        await bot.post_message('post_bug', '没有bug!')
    else:
        for i in read():
            _msg.append(f"来自会话{i['from']}#{len(read())}:\n{i['bug']}")
        await bot.post_message('post_bug', '待解决的bug:\n' + ',\n'.join(_msg))
