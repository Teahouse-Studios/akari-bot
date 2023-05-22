import os.path
import shutil
import traceback

from core.utils.cache import random_cache_path
from core.builtins import Bot
from core.builtins import Plain, Image
from core.component import module
from core.utils.http import get_url, download_to_cache
from .dbutils import PgrBindInfoManager
from .update import update_assets
from .genb19 import drawb19
from .game_record import parse_game_record

phi = module('phigros', developers=['OasisAkari'], desc='{phigros.help.desc}',
             alias={'p': 'phigros', 'pgr': 'phigros', 'phi': 'phigros'})


@phi.command('bind <sessiontoken> {{phigros.help.bind}}')
async def _(msg: Bot.MessageSession):
    need_revoke = False
    send_msg = []
    if msg.target.targetFrom in ['QQ|Group', 'QQ|Guild', 'Discord|Channel', 'Telegram|group', 'Telegram|supergroup']:
        send_msg.append(await msg.sendMessage(msg.locale.t("phigros.message.bind.warning")))
        need_revoke = True
    token: str = msg.parsed_msg['<sessiontoken>']
    bind = PgrBindInfoManager(msg).set_bind_info(sessiontoken=token)
    if bind:
        send_msg.append(await msg.sendMessage(msg.locale.t("phigros.message.bind.success")))
    if need_revoke:
        await msg.sleep(15)
        for i in send_msg:
            await i.delete()


@phi.command('unbind {{phigros.help.unbind}}')
async def _(msg: Bot.MessageSession):
    unbind = PgrBindInfoManager(msg).remove_bind_info()
    if unbind:
        await msg.finish(msg.locale.t("phigros.message.unbind.success"))


@phi.command('b19 {{phigros.help.b19}}')
async def _(msg: Bot.MessageSession):
    bind = PgrBindInfoManager(msg).get_bind_sessiontoken()
    if bind is None:
        await msg.finish(msg.locale.t("phigros.message.user_unbound", prefix=msg.prefixes[0]))
    else:
        try:
            get_save_url = await get_url('https://phigrosserver.pigeongames.cn/1.1/classes/_GameSave', headers={
                'Accept': 'application/json',
                'X-LC-Session': bind,
                'X-LC-Id': 'rAK3FfdieFob2Nn8Am',
                'X-LC-Key': 'Qr9AEqtuoSVS3zeD6iVbM4ZC0AtkJcQ89tywVyi0',
                'User-Agent': 'LeanCloud-CSharp-SDK/1.0.3',

            }, fmt='json')
            save_url = get_save_url['results'][0]['gameFile']['url']
            download = await download_to_cache(save_url)
            rd_path = random_cache_path()
            shutil.unpack_archive(download, rd_path)
            game_records = parse_game_record(os.path.join(rd_path, 'gameRecord'))
            flattened = {}
            for song in game_records:
                for level in game_records[song]:
                    flattened[f'{level}.{song}'] = game_records[song][level]
            sort_by_rks = sorted(flattened.items(), key=lambda x: x[1]['rks'], reverse=True)
            phi_list = []
            for s in sort_by_rks:
                if s[1]['score'] == 1000000:
                    phi_list.append(s)
            if not phi_list:
                phi_list.append(sort_by_rks[0])
            best_phi = sorted(phi_list, key=lambda x: x[1]['rks'], reverse=True)[0]
            b19_data = [best_phi] + sort_by_rks[0: 19]
            await msg.sendMessage(Image(drawb19('', b19_data)))
        except Exception as e:
            traceback.print_exc()
            await msg.sendMessage(Plain('获取失败，请尝试重新绑定Token或报告开发者：\n' + str(e)))


@phi.command('update', required_superuser=True)
async def _(msg: Bot.MessageSession):
    update_assets_ = await update_assets()
    if update_assets_:
        await msg.finish(msg.locale.t("phigros.message.update.success"))
    else:
        await msg.finish(msg.locale.t("phigros.message.update.failed"))
