from core.component import module
from core.builtins import Bot
from core.utils.http import download_to_cache
from core.builtins import Image, Plain
from core.logger import Logger
from random import *
import ujson as json
import shutil
import os

cave = module('cave', desc = '{cave.help.desc}', developers = ['bugungu'])

@cave.command('add {{cave.help.add}}')

async def add(msg: Bot.MessageSession):
    filename = './modules/cave/data.json'
    add = await msg.waitNextMessage(msg.locale.t('cave.msg.add'), delete = True)
    responce = await add.toMessageChain()
    data_json = []
    with open(filename, 'r', encoding = 'utf-8') as data:
        data_json = json.loads(data.read())
        data.close()
    write_json = {'sender':'',"content":[]}
    image_id = data_json['image_max_count'] + 1
    image_count = 0
    cave_id = len(data_json['contents']) + 1
    for v in responce.value:
        if isinstance(v, Image):
            i = v.path
            image_name = str(image_id) + '_' + str(image_count + 1)
            image_count += 1
            image_path = await download_to_cache(i, image_name)
            Logger.info('Get Image Path: ' + image_path)
            shutil.copy(image_path, '.\\modules\\cave\\images\\')
            write_json['content'].append({'image':'.\\modules\\cave\\images\\' + image_name})
        if isinstance(v, Plain):
            i = v.text
            write_json['content'].append({'text':i})
    Logger.info('Get Sender Name: ' + msg.target.senderName)
    write_json['sender'] = msg.target.senderName
    if write_json['content'] == None:
        await msg.finish(msg.locale.t('cave.msg.no_content'))
    data_json['contents'].append(write_json)
    with open(filename, 'w', encoding = 'utf-8') as data:
        data.write(json.dumps(data_json))
        data.close()
    await msg.finish(msg.locale.t('cave.msg.done', id = str(cave_id)))

@cave.command('delete <id> {{cave.help.delete}}', required_superuser = True)

async def delete(msg: Bot.MessageSession):
    filename = './modules/cave/data.json'
    data_json = []
    with open(filename, 'r', encoding = 'utf-8') as data:
        data_json = json.loads(data.read())
        data.close()
    id = int(msg.parsed_msg['<id>'])
    data_json['contents'].pop(id - 1)
    with open(filename, 'w', encoding = 'utf-8') as data:
        data.write(json.dumps(data_json))
        data.close()
    await msg.finish(msg.locale.t('cave.msg.delete', id = str(id)))

@cave.command('{{cave.help.get}}')

async def get(msg: Bot.MessageSession):
    filename = './modules/cave/data.json'
    data_json = []
    send_msg = []
    id = 0
    with open(filename, 'r', encoding = 'utf-8') as data:
        content = json.loads(data.read())
        id = randint(1, len(content['contents']))
        data_json = content['contents'][id - 1]
        data.close()
    send_msg.append(Plain(msg.locale.t('cave.msg.name') + ' #' + str(id)))
    Logger.info(data_json['content'])
    for i in data_json['content']:
        Logger.info(i)
        try:
            send_msg.append(Plain(i['text']))
            Logger.info('Get Text: ' + i['text'])
        except:
            send_msg.append(Image(i['image']))
            Logger.info('Get Image: ' + i['image'])
    send_msg.append(Plain('——' + data_json['sender'] + '\n' + msg.locale.t('cave.msg.recall')))
    send = await msg.sendMessage(send_msg)
    await msg.sleep(90)
    await send.delete()
    await msg.finish()