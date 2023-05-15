from core.builtins import Bot
from core.component import module
from core.utils.http import get_url
from config import Config
from core.utils.image import msgchain2image
from core.builtins import Image, Plain
import ujson as json

netease_cloud_music = module(bind_prefix='music', developers=['bugungu'])

@netease_cloud_music.handle('search <value> {{ncmusic.help_doc.search}}',
                            required_admin=False, required_superuser=False, available_for='*')
async def search(msg: Bot.MessageSession):
    api_address = Config('netease_cloud_music_api')
    value = msg.parsed_msg['<value>']
    if api_address and value:
        api_address += f"search?limit=10&keywords={value}"
        result = await get_url(api_address, 200, fmt='text', request_private_ip=True)
        result_json = json.loads(result)
        send_msg = msg.locale.t('ncmusic.search_result') + '\n'
        cnt = 1
        for song in result_json['result']['songs']:
            send_msg += f"{cnt}. {song['name']}"
            if 'transNames' in song:
                send_msg += f"{msg.locale.t('ncmusic.character.(')}{' / '.join(song['transNames'])}{msg.locale.t('ncmusic.character.)')}"
            send_msg += f" {msg.locale.t('ncmusic.come_from.character')} {' & '.join(artist['name'] for artist in song['artists'])}"
            send_msg += f" {msg.locale.t('ncmusic.come_from.character')} {song['album']['name']}"
            if 'transNames' in song['album']:
                send_msg += f"{msg.locale.t('ncmusic.character.(')}{' / '.join(song['album']['transNames'])}{msg.locale.t('ncmusic.character.)')}"
            send_msg += f"{msg.locale.t('ncmusic.character.(')}{song['id']}{msg.locale.t('ncmusic.character.)')}\n"
            cnt += 1
        send_msg += f"\n{msg.locale.t('ncmusic.message.delete')}"
        img_path = await msgchain2image([Plain(send_msg)])
        send = await msg.sendMessage(Image(img_path))
        await msg.sleep(90)
        await send.delete()
        await msg.finish()
    elif not value:
        send_msg = msg.locale.t('ncmusic.message.wrong_grammar')
    else:
        send_msg = msg.locale.t('ncmusic.message.none_config')
    send = await msg.sendMessage(send_msg)
    await msg.finish()

@netease_cloud_music.handle('info <ids> {{ncmusic.help_doc.info}}', 
                            required_admin=False, required_superuser=False,
                            available_for='*')
async def info(msg: Bot.MessageSession):
    api_address = Config('netease_cloud_music_api')
    if not api_address:
        await msg.sendMessage(msg.locale.t('ncmusic.message.none_config'))
        return await msg.finish()

    ids = msg.parsed_msg['<ids>']
    if not ids:
        await msg.sendMessage(msg.locale.t('ncmusic.message.wrong_grammar'))
        return await msg.finish()

    url = f"{api_address}song/detail?ids={ids}"
    result = await get_url(url, 200, fmt='text', request_private_ip=True)
    result_json = json.loads(result)

    send_msg = []
    for k in result_json['songs']:
        send_msg.append(Image(k['al']['picUrl']))
        send_msg_plain = ''
        send_msg_plain += f"{msg.locale.t('ncmusic.info.name')}{k['name']}({k['id']})\n"
        send_msg_plain += f"{msg.locale.t('ncmusic.info.album')}{k['al']['name']}({k['al']['id']})\n"
        send_msg_plain += f"{msg.locale.t('ncmusic.info.artists')}"
        send_msg_plain += ' & '.join([ar['name'] for ar in k['ar']])
        send_msg_plain += '\n'
        song_page = f"https://music.163.com/#/song?id={k['id']}"
        send_msg_plain += f"{msg.locale.t('ncmusic.info.song_page')}{song_page}\n"
        url = f"{api_address}song/url?id={k['id']}"
        song = await get_url(url, 200, fmt='text', request_private_ip=True)
        song_url = json.loads(song)
        send_msg_plain += f"{msg.locale.t('ncmusic.info.song_url')}{song_url['data'][0]['url']}\n"
        send_msg.append(Plain(send_msg_plain))

    send_msg.append(Plain(f"\n{msg.locale.t('ncmusic.message.delete')}"))
    send = await msg.sendMessage(send_msg)
    await msg.sleep(90)
    await send.delete()
    await msg.finish()