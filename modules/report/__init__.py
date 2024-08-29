import ujson as json
import traceback

from core.builtins import Bot
from core.component import module
from core.scheduler import CronTrigger

rp = module('report', developers='haoye_qwq', desc='汇报bug', base=True)


def read():
    _data = json.load(open('./modules/report/bugs.json', 'r'))
    return _data


def write(data: str, frome: str, serial: int):
    if not read():
        _data = [{'bug': data, 'from': frome, 'serial': serial}]
    else:
        _data = read().append({'bug': data, 'from': frome, 'serial': serial})
    json.dump(_data, open('./modules/report/bugs.json', 'w'))


def delete(bug_id: int):
    data = read()
    del data[bug_id]
    json.dump(data, open('./modules/report/bugs.json', 'w'))


@rp.handle('open <bug> {汇报一个bug}', required_admin=True)
async def opn(msg: Bot.MessageSession):
    if not read():
        serial = 1
    else:
        serial = len(read()) + 1
    write(f"{msg.parsed_msg['<bug>']}\n——{msg.target.sender_name}({msg.target.sender_id})",
          msg.target.target_id, serial)
    await msg.sendMessage('已添加: #' + str(serial))


@rp.handle('close <bug_id> {完成bug修复}', required_superuser=True)
async def cls(msg: Bot.MessageSession):
    try:
        _id = int(msg.parsed_msg['<bug_id>']) - 1
        grpid = read()[_id]['from']
        f = await Bot.FetchTarget.fetch_target(grpid)
        await f.sendDirectMessage('已修复#' + str(_id))
        delete(_id)

    except Exception:
        await msg.sendMessage('不存在的id，请检查输入')
        traceback.print_exc()


@rp.handle('list {你有几个bug?}', required_superuser=True)
async def lst(msg: Bot.MessageSession):
    _msg = []
    if not read():
        await msg.sendMessage('没有bug!')
    else:
        for i in read():
            _msg.append(f"来自会话{i['from']}#{i['serial']}: {i['bug']}")
        await msg.sendMessage('待解决的bug:\n' + ',\n'.join(_msg))


on_schedule(
    bind_prefix='post_bug',
    trigger=CronTrigger.from_crontab('30 10 * * *'),
    desc='推送bug',
    alias=None,
    recommend_modules=None,
    developers='haoye_qwq',
    required_superuser=True
)


async def post(bot: Bot.FetchTarget):
    _msg = []
    if not read():
        await bot.post_message('post_bug', '没有bug!')
    else:
        for i in read():
            _msg.append(f"来自会话{i['from']}#{i['serial']}:\n{i['bug']}")
        await bot.post_message('post_bug', '待解决的bug:\n' + ',\n'.join(_msg))
