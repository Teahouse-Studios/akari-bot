from core.builtins import Bot, Plain, Image
from core.component import module
from core.utils.http import get_url

ncmusic = module('ncmusic',
                 developers=['bugungu', 'DoroWolf'],
                 support_languages=['zh_cn'])


@ncmusic.handle('search <keyword> {{ncmusic.help.search}}')
async def search(msg: Bot.MessageSession, keyword: str):
    url = f"https://autumnfish.cn/search?keywords={keyword}"
    result = await get_url(url, 200, fmt='json')

    if result['result']['songCount'] == 0:
        await msg.finish(msg.locale.t('ncmusic.message.search.not_found'))

    songs = result['result']['songs'][:10]
    send_msg = msg.locale.t('ncmusic.message.search.result') + '\n'

    for i, song in enumerate(songs, start=1):
        send_msg += f"{i}. {song['name']}"
        if 'transNames' in song:
            send_msg += f"（{' / '.join(song['transNames'])}）"
        send_msg += f"——{' / '.join(artist['name'] for artist in song['artists'])}"
        send_msg += f"《{song['album']['name']}》"
        if 'transNames' in song['album']:
            send_msg += f"（{' / '.join(song['album']['transNames'])}）"
        send_msg += f"（{song['id']}）\n"

    if len(result['result']['songs']) > 10:
        send_msg += msg.locale.t('ncmusic.message.search.collapse')

    await msg.finish(send_msg)


@ncmusic.handle('info <sid> {{ncmusic.help.info}}')
async def info(msg: Bot.MessageSession, sid: str):
    url = f"https://autumnfish.cn/song/detail?ids={sid}"
    result = await get_url(url, 200, fmt='json')

    info = result['songs'][0]
    artist = ' / '.join([ar['name'] for ar in info['ar']])
    song_page = f"https://music.163.com/#/song?id={info['id']}"

    send_msg = msg.locale.t('ncmusic.message.info',
                            name=info['name'], id=info['id'],
                            album=info['al']['name'], album_id=info['al']['id'],
                            artists=artist, detail=song_page)

    await msg.finish([Image(info['al']['picUrl']), Plain(send_msg)])
