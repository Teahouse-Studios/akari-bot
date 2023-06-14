from core.builtins import Bot, Plain, Image
from core.component import module
from core.utils.http import get_url
from config import Config
from core.utils.image import msgchain2image
from core.builtins import Image, Plain
import ujson as json

api_address = Config('netease_cloud_music_api_url')

ncmusic = module(bind_prefix='ncmusic', developers=['bugungu', 'DoroWolf'], required_superuser=True)


@ncmusic.handle('search <keyword> {{ncmusic.help.search}}')
async def search(msg: Bot.MessageSession, keyword: str):
    search_url = f"{api_address}search?keywords={keyword}"
    result = await get_url(search_url, 200, fmt='json')

    songs = result['result']['songs'][0][:10]
    send_msg = msg.locale.t('ncmusic.message.search.result') + '\n'

    for i, song in enumerate(songs, start=1):
        send_msg += f"{i}. {song['name']}"
        if 'transNames' in song:
            send_msg += f"（{' / '.join(song['transNames'])}）"
        send_msg += f"——{' & '.join(artist['name'] for artist in song['artists'])}"
        send_msg += f"《{song['album']['name']}》"
        if 'transNames' in song['album']:
            send_msg += f"（{' / '.join(song['album']['transNames'])}）"
        send_msg += f"（{song['id']}）"

        if len(result['result']['songs']) > 10:
            send_msg += '\n' + msg.locale.t('ncmusic.message.search.collapse')

    img = await msgchain2image([Plain(send_msg)])
    await msg.finish(Image(img))



@ncmusic.handle('info <sid> {{ncmusic.help.info}}')
async def info(msg: Bot.MessageSession, sid: str):
    url = f"{api_address}song/detail?ids={sid}"
    result = await get_url(url, 200, fmt='json')

    info = result['songs'][0]
    artist='/'.join([ar['name'] for ar in info['ar']])
    song_page = f"https://music.163.com/#/song?id={info['id']}"

    song_url = f"{api_address}song/url?id={info['id']}"
    song = await get_url(song_url, 200, fmt='json')

    send_msg = msg.locale.t('ncmusic.message.info', 
                            name=info['name'], id=info['id'], 
                            album=info['al']['name'], album_id=info['al']['id'], 
                            artists=artist, detail=song_page, 
                            url=song['data'][0]['url'])

    await msg.finish([Image(info['al']['picUrl']), Plain(send_msg)])