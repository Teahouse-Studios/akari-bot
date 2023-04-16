from core.component import on_command
from core.builtins.message import MessageSession
from core.dirty_check import check
from .get import get_hitokoto

hitokoto = on_command(bind_prefix='hitokoto', developers=['bugungu'])

@hitokoto.handle('{接入一言API}', required_admin = False, required_superuser = False, available_for = '*')

async def print_out(msg: MessageSession):
    send = await msg.sendMessage(await get_hitokoto() + '\n[90秒后撤回]')
    await msg.sleep(90)
    await send.delete()
    await msg.finish()