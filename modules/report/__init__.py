import redis
import ujson as json

from config import Config
from core.builtins import Bot
from core.component import on_command, on_schedule
from core.scheduler import CronTrigger

rp = on_command('report', developers='haoye_qwq', desc='汇报bug')

redis_ = Config('redis').split(':')
db = redis.StrictRedis(host=redis_[0], port=int(redis_[1]), db=0, decode_responses=True, charset='UTF-8')


def write(data: str, frome: str):
    _data = read().append({"bug": data, "from": frome})
    db.set('bug', str(_data))


def read():
    _data = db.get('bug')
    return json.loads(_data)


def exist():
    return db.exists('bug')


def delete(bug_id: int):
    data = read()
    db.set('bug', data.pop(bug_id))


@rp.handle('open <bug> {汇报一个bug}', required_admin=True)
async def opn(msg: Bot.MessageSession):
    write(f"#{len(read())}:\n{msg.parsed_msg['<bug>']}\n——{msg.target.senderName}({msg.target.senderId})",
          msg.target.targetId)
    await msg.sendMessage('已添加: #' + str(len(read())))


@rp.handle('close <bug_id> {完成bug修复}', required_superuser=True)
async def cls(msg: Bot.MessageSession):
    try:
        _id = int(msg.parsed_msg['<bug_id>'])
        grpid = read()[_id]['from']
        await Bot.FetchTarget.fetch_target(grpid).sendDirectMessage('已修复#' + str(_id))
        delete(_id)

    except Exception:
        await msg.sendMessage('不存在的id，请检查输入')


on_schedule(
    bind_prefix='post_bug',
    trigger=CronTrigger.from_crontab('30 10 * * *'),
    desc='推送bug',
    developers='haoye_qwq',
    required_superuser=True
)


async def post(bot: Bot.FetchTarget):
    msg = []
    for i in read():
        msg.append(f"来自会话{i['from']}#{len(read())}:\n{i['bug']}")
    await bot.post_message('post_bug', '待解决的bug:\n'+',\n'.join(msg))
