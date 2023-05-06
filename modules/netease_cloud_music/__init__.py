from core.builtins import Bot
from core.component import module
from core.utils.http import get_url
from config import Config
from core.utils.image import msgchain2image
from core.builtins import Image, Plain
import ujson as json

netease_cloud_music = module(bind_prefix = 'music', developers = ['bugungu'])

@netease_cloud_music.handle('search <value> {{ncmusic.msg.help.search}}')

async def search(msg: Bot.MessageSession):
    api_address = Config('netease_cloud_music_api')
    if api_address and msg.parsed_msg['<value>']:
        api_address += 'search?limit=10&keywords=' + msg.parsed_msg['<value>']
        result = await get_url(api_address, 200, fmt = 'text', request_private_ip = True)
        result_json = json.loads(result)
        send_msg = msg.locale.t('ncmusic.msg.search_result') + '\n'
        cnt = 1
        for k in result_json['result']['songs']:
            #歌名（如果有翻译则加上翻译）
            send_msg += str(cnt) + '. ' + k['name']
            if 'transNames' in k:
                time = len(k['transNames'])
                value_trans = ''
                for i in range(time):
                    if i == time - 1:
                        value_trans += k['transNames'][i]
                    else:
                        value_trans += k['transNames'][i] + ' / '
                send_msg += msg.locale.t('ncmusic.msg.character', value = value_trans)
            #歌手名
            send_msg += ' ' + msg.locale.t('ncmusic.msg.come_from') + ' '
            time = len(k['artists'])
            for i in range(time):
                if i == time - 1:
                    send_msg += k['artists'][i]['name']
                else:
                    send_msg += k['artists'][i]['name'] + ' & '
            #专辑名（如果有翻译则加上翻译）
            send_msg += ' ' + msg.locale.t('ncmusic.msg.come_from') + ' ' + k['album']['name']
            if 'transNames' in k['album']:
                time = len(k['album']['transNames'])
                value_trans = ''
                for i in range(time):
                    if i == time - 1:
                        value_trans += k['album']['transNames'][i]
                    else:
                        value_trans += k['album']['transNames'][i] + ' / '
                send_msg += msg.locale.t('ncmusic.msg.character', value = value_trans)
            #歌曲号
            send_msg += msg.locale.t('ncmusic.msg.character', value = str(k['id']))
            send_msg += '\n'
            cnt += 1
        send_msg += '\n' + msg.locale.t('ncmusic.msg.recall')
        img_path = await msgchain2image([Plain(send_msg)])
        send = await msg.sendMessage(Image(img_path))
        await msg.sleep(90)
        await send.delete()
        await msg.finish()

@netease_cloud_music.handle('info <ids> {{ncmusic.msg.help.info}}', 
                            required_admin = False, required_superuser = False,
                            available_for = '*')

async def info(msg: Bot.MessageSession):
    api_address = Config('netease_cloud_music_api')
    if api_address and msg.parsed_msg['<ids>']:
        url = api_address + 'song/detail?ids=' + msg.parsed_msg['<ids>']
        result = await get_url(url, 200, fmt = 'text', request_private_ip = True)
        result_json = json.loads(result)
        send_msg = []
        for k in result_json['songs']:
            send_msg.append(Image(k['al']['picUrl']))
            send_msg_plain = ''
            #歌名
            send_msg_plain += msg.locale.t('ncmusic.msg.name') + k['name'] + \
                              msg.locale.t('ncmusic.msg.character', value = str(k['id'])) + '\n'
            #专辑名
            send_msg_plain += msg.locale.t('ncmusic.msg.album') + k['al']['name'] + \
                              msg.locale.t('ncmusic.msg.character', value = str(k['al']['id'])) + '\n'
            #歌手
            send_msg_plain += msg.locale.t('ncmusic.msg.artists')
            time = len(k['ar'])
            for i in range(time):
                if i == time - 1:
                    send_msg_plain += k['ar'][i]['name']
                else:
                    send_msg_plain += k['ar'][i]['name'] + ' & '
            send_msg_plain += '\n'
            #歌曲详情页
            song_page = 'https://music.163.com/#/song?id=' + str(k['id'])
            send_msg_plain += msg.locale.t('ncmusic.msg.song_page') + song_page + '\n'
            #歌曲链接
            url = api_address + 'song/url?id=' + str(k['id'])
            song = await get_url(url, 200, fmt = 'text', request_private_ip = True)
            song_url = json.loads(song)
            send_msg_plain += msg.locale.t('ncmusic.msg.song_url') + song_url['data'][0]['url'] + '\n'
            send_msg.append(Plain(send_msg_plain))
        send_msg.append(Plain('\n' + msg.locale.t('ncmusic.msg.recall')))
        send = await msg.sendMessage(send_msg)
        await msg.sleep(90)
        await send.delete()
        await msg.finish()
    