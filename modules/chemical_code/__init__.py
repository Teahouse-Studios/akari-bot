import asyncio
import os
import random
import re
import traceback
from datetime import datetime

from PIL import Image as PILImage
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt

from core.builtins import Bot, Image, Plain
from core.component import module
from core.logger import Logger
from core.petal import gained_petal
from core.utils.cache import random_cache_path
from core.utils.http import get_url, download_to_cache
from core.utils.text import remove_prefix

csr_link = 'https://www.chemspider.com'

special_id_path = os.path.abspath(f'./assets/chemical_code/special_id') # 去掉文件扩展名并存储在special_id列表中
special_id = [os.path.splitext(filename)[0] for filename in os.listdir(special_id_path)] # 可能会导致识别问题的物质（如部分单质）ID，这些 ID 的图片将会在本地调用

element_lists = ['He', 'Li', 'Be', 'Ne', 'Na', 'Mg', 'Al', 'Si', 'Cl',
                 'Ar', 'Ca', 'Sc', 'Ti', 'Cr', 'Mn', 'Fe', 'Co', 'Ni',
                 'Cu', 'Zn', 'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr', 'Rb',
                 'Sr', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag',
                 'Cd', 'In', 'Sn', 'Sb', 'Te', 'Xe', 'Cs', 'Ba', 'La',
                 'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy',
                 'Ho', 'Er', 'Tm', 'Yb', 'Lu', 'Hf', 'Ta', 'Re', 'Os',
                 'Ir', 'Pt', 'Au', 'Hg', 'Tl', 'Pb', 'Bi', 'Po', 'At',
                 'Rn', 'Fr', 'Ra', 'Ac', 'Th', 'Pa', 'Np', 'Pu', 'Am',
                 'Cm', 'Bk', 'Cf', 'Es', 'Fm', 'Md', 'No', 'Lr', 'Rf',
                 'Db', 'Sg', 'Bh', 'Hs', 'Mt', 'Ds', 'Rg', 'Cn', 'Nh',
                 'Fl', 'Mc', 'Lv', 'Ts', 'Og', 'C', 'H', 'B', 'K', 'N',
                 'O', 'F', 'P', 'S', 'V', 'I', 'U', 'Y', 'W']  # 元素列表，用于解析化学式（请不要手动修改当前的排序）


def parse_elements(formula: str) -> dict:
    elements = {}
    while True:
        if formula == '':
            break
        for element in element_lists:
            if formula.startswith(element):
                formula = remove_prefix(formula, element)
                if count := re.match('^([0-9]+).*$', formula):
                    elements[element] = int(count.group(1))
                    formula = remove_prefix(formula, count.group(1))
                else:
                    elements[element] = 1
                break
        else:
            raise ValueError('Unknown element: ' + formula)
    return elements


@retry(stop=stop_after_attempt(3), reraise=True)
async def search_csr(id=None):
    if id is not None: 
        answer_id = id
    else:
        answer_id = random.randint(1, 200000000)  # 数据库增长速度很快，可手动在此修改ID区间
    answer_id = str(answer_id)
    Logger.info("ChemSpider ID: " + answer_id)
    get = await get_url(csr_link + '/Search.aspx?q=' + answer_id, 200, fmt='text')
    # Logger.info(get)
    soup = BeautifulSoup(get, 'html.parser')
    name = soup.find(
        'span',
        id='ctl00_ctl00_ContentSection_ContentPlaceHolder1_RecordViewDetails_rptDetailsView_ctl00_prop_MF').text  # 获取化学式名称
    elements = parse_elements(name)
    value = 0
    for element in elements:
        value += elements[element]
    wh = 500 * value // 100
    if wh < 500:
        wh = 500
    return {'id': answer_id,
            'name': name,
            'image': f'https://www.chemspider.com/ImagesHandler.ashx?id={answer_id}' +
                     (f"&w={wh}&h={wh}" if answer_id not in special_id else ""),
            'length': value,
            'elements': elements}


ccode = module('chemical_code', alias={'cc': 'chemical_code',
                                       'chemicalcode': 'chemical_code',
                                       'chemical_captcha': 'chemical_code captcha',
                                       'chemicalcaptcha': 'chemical_code captcha',
                                       'ccode': 'chemical_code',
                                       'ccaptcha': 'chemical_code captcha'},
               desc='{chemical_code.help.desc}', developers=['OasisAkari'])
play_state = {}  # 创建一个空字典用于存放游戏状态


@ccode.command('{{chemical_code.help}}')  
async def chemical_code_by_random(msg: Bot.MessageSession):
    await chemical_code(msg)


@ccode.command('captcha {{chemical_code.help.captcha}}')
async def _(msg: Bot.MessageSession):
    await chemical_code(msg, captcha_mode=True)


@ccode.command('stop {{game.help.stop}}')
async def s(msg: Bot.MessageSession):
    state = play_state.get(msg.target.target_id, {})  # 尝试获取 play_state 中是否有此对象的游戏状态
    if state:
        if state['active']:
            play_state[msg.target.target_id]['active'] = False
            await msg.finish(
                msg.locale.t('chemical_code.stop.message', answer=play_state[msg.target.target_id]["answer"]),
                quote=False)
        else:
            await msg.finish(msg.locale.t('game.message.stop.none'))
    else:
        await msg.finish(msg.locale.t('game.message.stop.none'))


@ccode.command('<csid> {{chemical_code.help.csid}}')
async def chemical_code_by_id(msg: Bot.MessageSession):
    id = msg.parsed_msg['<csid>']
    if id.isdigit():
        if int(id) == 0: # 若 id 为 0，则随机
            await chemical_code(msg)
        else:
            await chemical_code(msg, id, random_mode=False)
    else:
        await msg.finish(msg.locale.t('chemical_code.message.csid.invalid'))


async def chemical_code(msg: Bot.MessageSession, id=None, random_mode=True, captcha_mode=False):
    if msg.target.target_id in play_state and play_state[msg.target.target_id]['active']:
        await msg.finish(msg.locale.t('game.message.running'))
    play_state.update({msg.target.target_id: {'active': True}})
    try:
        csr = await search_csr(id)
    except Exception as e:
        traceback.print_exc()
        play_state[msg.target.target_id]['active'] = False
        return await msg.finish(msg.locale.t('chemical_code.message.error'))
    # print(csr)
    play_state[msg.target.target_id]['answer'] = csr['name'] 
    Logger.info(f'Answer: {csr["name"]}')
    Logger.info(f'Image: {csr["image"]}')
    download = False
    if csr["id"] in special_id:  # 如果正确答案在 special_id 中
        file_path = os.path.abspath(f'./assets/chemicalcode/special_id/{csr["id"]}.png')
        Logger.info(f'File path: {file_path}')
        exists_file = os.path.exists(file_path)
        if exists_file:
            download = file_path
    if not download:
        download = await download_to_cache(csr['image'])

    with PILImage.open(download) as im:
        im = im.convert("RGBA")
        image = PILImage.new("RGBA", im.size, 'white')
        image.alpha_composite(im, (0, 0))
        newpath = random_cache_path() + '.png'
        image.save(newpath)

    set_timeout = csr['length'] // 30
    if set_timeout < 2:
        set_timeout = 2

    async def ans(msg: Bot.MessageSession, answer, random_mode):
        wait = await msg.wait_anyone()
        if play_state[msg.target.target_id]['active']:
            if (wait_text := wait.as_display(text_only=True)) != answer:
                if re.match(r'^[A-Za-z0-9]+$', wait_text):
                    try:
                        parse_ = parse_elements(wait_text)  # 解析消息中的化学元素
                        value = 0
                        for i in parse_:
                            value += parse_[i]
                        v_ = csr['length'] - value
                        if v_ < 0:
                            v_ = -v_
                        if v_ > 6:
                            await wait.send_message(wait.locale.t('chemical_code.message.incorrect.remind1'))
                        else:
                            if csr['elements'] == parse_:
                                await wait.send_message(wait.locale.t('chemical_code.message.incorrect.remind5'))
                            elif v_ <= 2:
                                missing_something = False
                                for i in csr['elements']:
                                    if i not in parse_:
                                        await wait.send_message(
                                            wait.locale.t('chemical_code.message.incorrect.remind4'))
                                        missing_something = True
                                        break
                                if not missing_something:
                                    await wait.send_message(wait.locale.t('chemical_code.message.incorrect.remind3'))
                            else:
                                incorrect_list = []
                                for i in csr['elements']:
                                    if i in parse_:
                                        if parse_[i] != csr['elements'][i]:
                                            incorrect_list.append(i)
                                    else:
                                        await wait.send_message(
                                            wait.locale.t('chemical_code.message.incorrect.remind4'))
                                        incorrect_list = []
                                        break

                                if incorrect_list:
                                    incorrect_elements = wait.locale.t('message.delimiter').join(incorrect_list)
                                    await wait.send_message(wait.locale.t('chemical_code.message.incorrect.remind2',
                                                                          elements=incorrect_elements))

                    except ValueError:
                        traceback.print_exc()

                Logger.info(f'{wait_text} != {answer}')
                return await ans(wait, answer, random_mode)
            else:
                send_ = wait.locale.t('chemical_code.message.correct')
                if random_mode:
                    if (g_msg := await gained_petal(wait, 2)):
                        send_ += '\n' + g_msg
                await wait.send_message(send_)
                play_state[msg.target.target_id]['active'] = False

    async def timer(start):
        if play_state[msg.target.target_id]['active']: 
            if datetime.now().timestamp() - start > 60 * set_timeout:
                await msg.send_message(
                    msg.locale.t('chemical_code.message.timeup', answer=play_state[msg.target.target_id]["answer"]))
                play_state[msg.target.target_id]['active'] = False
            else:
                await asyncio.sleep(1)  # 防冲突
                await timer(start)

    if not captcha_mode:
        await msg.send_message([Plain(msg.locale.t('chemical_code.message.showid', id=csr["id"])), Image(newpath),
                                Plain(msg.locale.t('chemical_code.message', times=set_timeout))])
        time_start = datetime.now().timestamp()

        await asyncio.gather(ans(msg, csr['name'], random_mode), timer(time_start))
    else:
        result = await msg.wait_next_message([Plain(msg.locale.t('chemical_code.message.showid', id=csr["id"])),
                                              Image(newpath), Plain(msg.locale.t('chemical_code.message.captcha',
                                                                                 times=set_timeout))], append_instruction=False)
        if play_state[msg.target.target_id]['active']: 
            if result.as_display(text_only=True) == csr['name']:
                send_ = msg.locale.t('chemical_code.message.correct')
                if (g_msg := await gained_petal(wait, 1)):
                    send_ += '\n' + g_msg
                await result.send_message(send_)
            else:
                await result.send_message(
                    msg.locale.t('chemical_code.message.incorrect', answer=play_state[msg.target.target_id]["answer"]))
            play_state[msg.target.target_id]['active'] = False
