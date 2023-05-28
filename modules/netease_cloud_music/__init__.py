from core.builtins import Bot, Plain, Image
from core.component import module
from core.utils.http import get_url
from config import Config
from core.utils.image import msgchain2image
from core.builtins import Image, Plain
import ujson as json

api_address = Config('netease_cloud_music_api_url')

ncmusic = module(bind_prefix='ncmusic', developers=['bugungu'], required_superuser=True)

@ncmusic.handle('search <keyword> {{ncmusic.help.search}}')
async def search(msg: Bot.MessageSession):
    keyword = msg.parsed_msg['<keyword>']
    search_url = f"{api_address}search?limit=10&keywords={keyword}"
    result = await get_url(search_url, 200, fmt='text', request_private_ip=True)
    result_json = json.loads(result)
    send_msg = msg.locale.t('ncmusic.search.result') + '\n'
    i = 1
    for song in result_json['result']['songs']:
        send_msg += f"{i}. {song['name']}"
        if 'transNames' in song:
            send_msg += msg.locale.t("ncmusic.message.character", value=' / '.join(song['transNames']))
        send_msg += f"--{' & '.join(artist['name'] for artist in song['artists'])}"
        send_msg += f"--{song['album']['name']}"
        if 'transNames' in song['album']:
            send_msg += msg.locale.t("ncmusic.message.character", value=' / '.join(song['album']['transNames']))
        send_msg += msg.locale.t("ncmusic.message.character", value=song['id']) + "\n"
        i += 1
    img_path = await msgchain2image([Plain(send_msg)])
    send = await msg.sendMessage(Image(img_path))
    await msg.finish(send_msg)

@ncmusic.handle('info <id> {{ncmusic.help.info}}')
async def info(msg: Bot.MessageSession):
    ids = msg.parsed_msg['<id>']
    info_url = f"{api_address}song/detail?ids={ids}"
    result = await get_url(info_url, 200, fmt='json')

    detail_url = f"https://music.163.com/#/song?id={result['song']['id']}"
    url = f"{api_address}song/url?id={result['song']['id']}"
    song_url = await get_url(url, 200, fmt='json')

    await message.finish([Image(f"{result['song']['al']['picUrl']}"),
                        Plain(message.locale.t("ncmusic.message.info", name=result['song']['name'], id=result['song']['id'], 
                                    album=result['song']['al']['name'], album_id=result['song']['al']['id'], artists='&'.join([ar['name'] for ar in result['song']['ar']]), 
                                    detail=detail_url, url=song_url['data'][0]['url']))])



#@netease_cloud_music.handle('info <ids> {{ncmusic.help_doc.info}}', 
#                            required_admin=False, required_superuser=False,
#                            available_for='*')
#async def info(msg: Bot.MessageSession):
#    api_address = Config('netease_cloud_music_api')
#    if not api_address:
#        await msg.sendMessage(msg.locale.t('ncmusic.message.none_config'))
#        return await msg.finish()

#    ids = msg.parsed_msg['<ids>']
#    if not ids:
#        await msg.sendMessage(msg.locale.t('ncmusic.message.wrong_grammar'))
#        return await msg.finish()

#    url = f"{api_address}song/detail?ids={ids}"
#    result = await get_url(url, 200, fmt='text', request_private_ip=True)
#    result_json = json.loads(result)

#    send_msg = []
#    for k in result_json['songs']:
#        send_msg.append(Image(k['al']['picUrl']))
#        send_msg_plain = ''
#        send_msg_plain += f"{msg.locale.t('ncmusic.info.name')}{k['name']}({k['id']})\n"
#        send_msg_plain += f"{msg.locale.t('ncmusic.info.album')}{k['al']['name']}({k['al']['id']})\n"
#        send_msg_plain += f"{msg.locale.t('ncmusic.info.artists')}"
#        send_msg_plain += ' & '.join([ar['name'] for ar in k['ar']])
#        send_msg_plain += '\n'
#        song_page = f"https://music.163.com/#/song?id={k['id']}"
#        send_msg_plain += f"{msg.locale.t('ncmusic.info.song_page')}{song_page}\n"
#        url = f"{api_address}song/url?id={k['id']}"
#        song = await get_url(url, 200, fmt='text', request_private_ip=True)
#        song_url = json.loads(song)
#        send_msg_plain += f"{msg.locale.t('ncmusic.info.song_url')}{song_url['data'][0]['url']}\n"
#        send_msg.append(Plain(send_msg_plain))

#    send_msg.append(Plain(f"\n{msg.locale.t('ncmusic.message.delete')}"))
#    send = await msg.sendMessage(send_msg)
#    await msg.sleep(90)
#    await send.delete()
#    await msg.finish()