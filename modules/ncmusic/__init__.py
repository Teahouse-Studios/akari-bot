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
    result = await get_url(search_url, 200, fmt='json')
    send_msg = msg.locale.t('ncmusic.message.search.result') + '\n'
    i = 1
    for song in result['result']['songs']:
        send_msg += f"{i}. {song['name']}"
        if 'transNames' in song:
            send_msg += msg.locale.t("ncmusic.message.character", value=' / '.join(song['transNames']))
        send_msg += f"--{' & '.join(artist['name'] for artist in song['artists'])}"
        send_msg += f"《{song['album']['name']}》"
        if 'transNames' in song['album']:
            send_msg += msg.locale.t("ncmusic.message.character", value=' / '.join(song['album']['transNames']))
        send_msg += msg.locale.t("ncmusic.message.character", value=song['id']) + "\n"
        i += 1
    img = await msgchain2image([Plain(send_msg)])
    await msg.finish(Image(img))

@ncmusic.handle('info <id> {{ncmusic.help.info}}')
async def info(msg: Bot.MessageSession):

    ids = msg.parsed_msg['<id>']
    url = f"{api_address}song/detail?ids={ids}"
    result = await get_url(url, 200, fmt='json')

    send_msg = []
    for k in result['songs']:
        send_msg.append(Image(k['al']['picUrl']))
        send_msg_plain = ''
        send_msg_plain += f"{msg.locale.t('ncmusic.message.info.name')}{k['name']} ({k['id']})\n"
        send_msg_plain += f"{msg.locale.t('ncmusic.message.info.album')}{k['al']['name']} ({k['al']['id']})\n"
        send_msg_plain += f"{msg.locale.t('ncmusic.message.info.artists')}"
        send_msg_plain += ' & '.join([ar['name'] for ar in k['ar']])
        send_msg_plain += '\n'
        song_page = f"https://music.163.com/#/song?id={k['id']}"
        send_msg_plain += f"{msg.locale.t('ncmusic.message.info.song_page')}{song_page}\n"
        url = f"{api_address}song/url?id={k['id']}"
        song = await get_url(url, 200, fmt='json')
        send_msg_plain += f"{msg.locale.t('ncmusic.message.info.song_url')}{song['data'][0]['url']}"
        send_msg.append(Plain(send_msg_plain))
    await msg.finish(send_msg)