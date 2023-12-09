from core.builtins import Bot, Plain, Image
from core.component import module
from core.utils.image_table import image_table_render, ImageTable
from core.utils.http import get_url
from core.logger import logger

ncmusic = module('ncmusic',
                 developers=['bugungu', 'DoroWolf'],
                 support_languages=['zh_cn'])


@ncmusic.handle(['search <keyword> {{ncmusic.help.search}}',
                 'search legacy <keyword> {{ncmusic.help.search.legacy}}'])
async def search(msg: Bot.MessageSession, keyword: str):
    url = f"https://ncmusic.akari-bot.top/search?keywords={keyword}"
    result = await get_url(url, 200, fmt='json')
    legacy = True

    if result['result']['songCount'] == 0:
        await msg.finish(msg.locale.t('ncmusic.message.search.not_found'))

    songs = result['result']['songs'][:10]

    if not msg.parsed_msg.get('legacy', False) and msg.Feature.image:

        send_msg = [Plain(msg.locale.t('ncmusic.message.search.result') + '\n')]
        data = [[
                str(i),
                song['name'] + (f" ({' / '.join(song['transNames'])})" if 'transNames' in song else ''),
                f"{' / '.join(artist['name'] for artist in song['artists'])}",
                f"{song['album']['name']}" + (f" ({' / '.join(song['album']['transNames'])})" if 'transNames' in song['album'] else ''),
                f"{song['id']}"
            ] for i, song in enumerate(songs, start=1)
        ]

        tables = ImageTable(data, [
            msg.locale.t('ncmusic.message.search.table.header.id'),
            msg.locale.t('ncmusic.message.search.table.header.name'),
            msg.locale.t('ncmusic.message.search.table.header.artists'),
            msg.locale.t('ncmusic.message.search.table.header.album'),
            'ID'
            ])

        img = await image_table_render(tables)
        if img:
            legacy = False

            send_msg.append(Image(img))
            if len(result['result']['songs']) > 10:
                send_msg.append(Plain(msg.locale.t('ncmusic.message.search.collapse')))
            send_msg.append(Plain(msg.locale.t('ncmusic.message.search.prompt')))
            query = await msg.wait_next_message(send_msg)
            query = query.as_display(text_only=True)
            try:
                query = int(query)
                if query > 10:
                    await msg.finish(msg.locale.t('ncmusic.message.search.invalid.out_of_range'))
                sid = result['result']['songs'][query - 1]['id']
                url = f"https://ncmusic.akari-bot.top/song/detail?ids={sid}"
                info = await get_url(url, 200, fmt='json')
                info = info['songs'][0]
                artist = ' / '.join([ar['name'] for ar in info['ar']])
                song_page = f"https://music.163.com/#/song?id={info['id']}"

                send_msg = msg.locale.t('ncmusic.message.info',
                                        name=info['name'], id=info['id'],
                                        album=info['al']['name'], album_id=info['al']['id'],
                                        artists=artist, detail=song_page)
                await msg.finish([Image(info['al']['picUrl']), Plain(send_msg)])
            except Exception:
                await msg.finish(msg.locale.t('ncmusic.message.search.invalid.non_digital'))

    if legacy:
        send_msg = msg.locale.t('ncmusic.message.search.result') + '\n'

        for i, song in enumerate(songs, start=1):
            send_msg += f"{i}\u200B. {song['name']}"
            if 'transNames' in song:
                send_msg += f"（{' / '.join(song['transNames'])}）"
            send_msg += f"——{' / '.join(artist['name'] for artist in song['artists'])}"
            send_msg += f"《{song['album']['name']}》"
            if 'transNames' in song['album']:
                send_msg += f"（{' / '.join(song['album']['transNames'])}）"
            send_msg += f"（{song['id']}）\n"

        if len(result['result']['songs']) > 10:
            send_msg += msg.locale.t('ncmusic.message.search.collapse')
        send_msg += '\n'
        send_msg += msg.locale.t('ncmusic.message.search.prompt')
        query = await msg.wait_next_message(send_msg)
        query = query.as_display(text_only=True)
        try:
            query = int(query)
            if query > 10:
                await msg.finish(msg.locale.t('ncmusic.message.search.invalid.out_of_range'))
            sid = result['result']['songs'][query - 1]['id']
            url = f"https://ncmusic.akari-bot.top/song/detail?ids={sid}"
            logger.info(url)
            info = await get_url(url, 200, fmt='json')
            info = info['songs'][0]
            artist = ' / '.join([ar['name'] for ar in info['ar']])
            song_page = f"https://music.163.com/#/song?id={info['id']}"

            send_msg = msg.locale.t('ncmusic.message.info',
                                    name=info['name'], id=info['id'],
                                    album=info['al']['name'], album_id=info['al']['id'],
                                    artists=artist, detail=song_page)
            await msg.finish([Image(info['al']['picUrl']), Plain(send_msg)])
        except Exception:
            await msg.finish(msg.locale.t('ncmusic.message.search.invalid.non_digital'))
        

@ncmusic.handle('info <sid> {{ncmusic.help.info}}')
async def info(msg: Bot.MessageSession, sid: str):
    url = f"https://ncmusic.akari-bot.top/song/detail?ids={sid}"
    result = await get_url(url, 200, fmt='json')

    info = result['songs'][0]
    artist = ' / '.join([ar['name'] for ar in info['ar']])
    song_page = f"https://music.163.com/#/song?id={info['id']}"

    send_msg = msg.locale.t('ncmusic.message.info',
                            name=info['name'], id=info['id'],
                            album=info['al']['name'], album_id=info['al']['id'],
                            artists=artist, detail=song_page)

    await msg.finish([Image(info['al']['picUrl']), Plain(send_msg)])
