from core.builtins import Bot
from core.component import module
from .chemical_code import chemical_code
from .twenty_four import twenty_four

play_state = {}  # 创建一个空字典用于存放游戏状态


ccode = module('chemical_code', alias={'cc': 'chemical_code',
                                       'chemicalcode': 'chemical_code',
                                       'chemical_captcha': 'chemical_code captcha',
                                       'chemicalcaptcha': 'chemical_code captcha',
                                       'ccode': 'chemical_code',
                                       'ccaptcha': 'chemical_code captcha'},
               desc='{game.chemical_code.help.desc}', developers=['OasisAkari'])


@ccode.command('{{game.chemical_code.help}}')  # 直接使用 ccode 命令将触发此装饰器
async def chemical_code_by_random(msg: Bot.MessageSession):
    await chemical_code(msg, play_state)  # 将消息会话传入 chemical_code 函数


@ccode.command('captcha {{game.chemical_code.help.captcha}}')
async def _(msg: Bot.MessageSession):
    await chemical_code(msg, play_state, captcha_mode=True)


@ccode.command('stop {{game.stop.help}}')
async def stop(msg: Bot.MessageSession):
    state = play_state.get(msg.target.targetId, False)  # 尝试获取 play_state 中是否有此对象的游戏状态
    if state:  # 若有
        if state['active']:  # 检查是否为活跃状态
            if state['game'] == 'ccode':
                play_state[msg.target.targetId]['active'] = False  # 标记为非活跃状态
                await msg.finish(
                    msg.locale.t('game.chemical_code.stop.message', answer=play_state[msg.target.targetId]["answer"]),
                    quote=False)  # 发送存储于 play_state 中的答案
            else:
                await msg.finish(msg.locale.t('game.stop.message.others'))
        else:
            await msg.finish(msg.locale.t('game.stop.message.none'))
    else:
        await msg.finish(msg.locale.t('game.stop.message.none'))


@ccode.command('<csid> {{game.chemical_code.help.csid}}')
async def chemical_code_by_id(msg: Bot.MessageSession):
    id = msg.parsed_msg['<csid>']  # 从已解析的消息中获取 ChemSpider ID
    if (id.isdigit() and int(id) > 0):  # 如果 ID 为纯数字
        await chemical_code(msg, play_state, id)  # 将消息会话和 ID 一并传入 chemical_code 函数
    else:
        await msg.finish(msg.locale.t('game.chemical_code.message.error.invalid'))




tf = module('twenty_four', alias=['twentyfour', '24'],
               desc='{game.twenty_four.help.desc}', developers=['DoroWolf'])


@tf.command('{{game.twenty_four.help}}')
async def _(msg: Bot.MessageSession):
    await twenty_four(msg, play_state)  # 将消息会话传入 chemical_code 函数


@tf.command('stop {{game.stop.help}}')
async def stop(msg: Bot.MessageSession):
    state = play_state.get(msg.target.targetId, False)
    if state:
        if state['active']:
            if state['game'] == '24':
                play_state[msg.target.targetId]['active'] = False
                await msg.finish(msg.locale.t('game.stop.message', quote=False))
            else:
                await msg.finish(msg.locale.t('game.stop.message.others'))
        else:
            await msg.finish(msg.locale.t('game.stop.message.none'))
    else:
        await msg.finish(msg.locale.t('game.stop.message.none'))