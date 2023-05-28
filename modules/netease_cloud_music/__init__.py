from core.builtins import Bot
from core.component import module
from core.utils.http import get_url
from config import Config
from core.utils.image import msgchain2image
from core.builtins import Image, Plain
import ujson as json

api_address = Config('netease_cloud_music_api')

ncmusic = module(bind_prefix='ncmusic', developers=['bugungu'])

@ncmusic.handle('search <keyword> {{ncmusic.help.search}}', required_superuser=True)
async def search(msg: Bot.MessageSession):
    keyword = msg.parsed_msg['<keyword>']
    if api_address and keyword:
        api_address += f"search?limit=10&keywords={keyword}"
        result = await get_url(api_address, 200, fmt='text', request_private_ip=True)
        result_json = json.loads(result)
        send_msg = msg.locale.t('ncmusic.search.result') + '\n'
        cnt = 1
        for song in result_json['result']['songs']:
            send_msg += f"{cnt}. {song['name']}"
            if 'transNames' in song:
                send_msg += msg.locale.t("ncmusic.message.character", value=' / '.join(song['transNames']))
            send_msg += f"--{' & '.join(artist['name'] for artist in song['artists'])}"
            send_msg += f"--{song['album']['name']}"
            if 'transNames' in song['album']:
                send_msg += msg.locale.t("ncmusic.message.character", value=' / '.join(song['album']['transNames']))
            send_msg += msg.locale.t("ncmusic.message.character", value=song['id']) + "\n"
            cnt += 1
        img_path = await msgchain2image([Plain(send_msg)])
        send = await msg.sendMessage(Image(img_path))
    elif not keyword:
        send_msg = msg.locale.t('ncmusic.message.wrong_grammar')
    else:
        send_msg = msg.locale.t('ncmusic.message.none_config')
    await msg.sendMessage(send_msg)

@ncmusic.handle('info <ids> {{ncmusic.help.info}}', required_superuser=True)
async def info(msg: Bot.MessageSession):
    if not api_address:
        await msg.sendMessage(msg.locale.t('ncmusic.message.none_config'))

    ids = msg.parsed_msg['<ids>']
    if not ids:
        await msg.sendMessage(msg.locale.t('ncmusic.message.wrong_grammar'))

    url = f"{api_address}song/detail?ids={ids}"
    result = await get_url(url, 200, fmt='text', request_private_ip=True)
    result_json = json.loads(result)

    send_msg = []
    for k in result_json['songs']:
        send_msg.append(Image(k['al']['picUrl']))
        send_msg_plain = ''
        send_msg_plain += f"{msg.locale.t('ncmusic.message.info.name')}{k['name']}({k['id']})\n"
        send_msg_plain += f"{msg.locale.t('ncmusic.message.info.album')}{k['al']['name']}({k['al']['id']})\n"
        send_msg_plain += f"{msg.locale.t('ncmusic.message.info.artists')}"
        send_msg_plain += ' & '.join([ar['name'] for ar in k['ar']])
        send_msg_plain += '\n'
        song_page = f"https://music.163.com/#/song?id={k['id']}"
        send_msg_plain += f"{msg.locale.t('ncmusic.message.info.song_page')}{song_page}\n"
        url = f"{api_address}song/url?id={k['id']}"
        song = await get_url(url, 200, fmt='text', request_private_ip=True)
        song_url = json.loads(song)
        send_msg_plain += f"{msg.locale.t('ncmusic.message.info.url')}{song_url['data'][0]['url']}\n"
        send_msg.append(Plain(send_msg_plain))

    await msg.sendMessage(send_msg)
