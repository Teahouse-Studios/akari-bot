import asyncio
import os
import random
import re
import traceback
from datetime import datetime

from PIL import Image as PILImage
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt

from core.builtins import Bot
from core.builtins import Image, Plain
from core.component import module
from core.logger import Logger
from core.petal import gained_petal
from core.utils.cache import random_cache_path
from core.utils.http import get_url, download_to_cache
from core.utils.text import remove_prefix

csr_link = 'https://www.chemspider.com'  # ChemSpider 的链接
special_id = ["22398", "140526", "4509317", "4509318", "4510681", "4510778", "4512975", "4514248", "4514266", "4514293",
              "4514330", "4514408", "4514534", "4514586", "4514603", "4515054", "4573995", "4574465", "4575369",
              "4575370",
              "4575371", "4885606", "4885717", "4886482", "4886484", "20473555", "21865276",
              "21865280"]  # 可能会导致识别问题的物质（如部分单质）ID，这些 ID 的图片将会在本地调用

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
async def search_csr(id=None):  # 根据 ChemSpider 的 ID 查询 ChemSpider 的链接，留空（将会使用缺省值 None）则随机查询
    if id is not None:  # 如果传入了 ID，则使用 ID 查询
        answer_id = id
    else:
        answer_id = random.randint(1, 116000000)  # 否则随机查询一个题目
    answer_id = str(answer_id)
    Logger.info("ChemSpider ID: " + answer_id)
    get = await get_url(csr_link + '/Search.aspx?q=' + answer_id, 200, fmt='text')  # 在 ChemSpider 上搜索此化学式或 ID
    # Logger.info(get)
    soup = BeautifulSoup(get, 'html.parser')  # 解析 HTML
    name = soup.find(
        'span',
        id='ctl00_ctl00_ContentSection_ContentPlaceHolder1_RecordViewDetails_rptDetailsView_ctl00_prop_MF').text  # 获取化学式名称
    elements = parse_elements(name)  # 解析化学式，转为dict，key为元素，value为数量
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


@ccode.command('{{chemical_code.help}}')  # 直接使用 ccode 命令将触发此装饰器
async def chemical_code_by_random(msg: Bot.MessageSession):
    await chemical_code(msg)  # 将消息会话传入 chemical_code 函数


@ccode.command('captcha {{chemical_code.help.captcha}}')
async def _(msg: Bot.MessageSession):
    await chemical_code(msg, captcha_mode=True)


@ccode.command('stop {{game.help.stop}}')
async def s(msg: Bot.MessageSession):
    state = play_state.get(msg.target.target_id, {})  # 尝试获取 play_state 中是否有此对象的游戏状态
    if state:  # 若有
        if state['active']:  # 检查是否为活跃状态
            play_state[msg.target.target_id]['active'] = False  # 标记为非活跃状态
            await msg.finish(
                msg.locale.t('chemical_code.stop.message', answer=play_state[msg.target.target_id]["answer"]),
                quote=False)  # 发送存储于 play_state 中的答案
        else:
            await msg.finish(msg.locale.t('game.message.stop.none'))
    else:
        await msg.finish(msg.locale.t('game.message.stop.none'))


@ccode.command('<csid> {{chemical_code.help.csid}}')
async def chemical_code_by_id(msg: Bot.MessageSession):
    id = msg.parsed_msg['<csid>']  # 从已解析的消息中获取 ChemSpider ID
    if id.isdigit():  # 如果 ID 为纯数字
        if int(id) == 0:
            await chemical_code(msg)
        else:
            await chemical_code(msg, id, random_mode=False)  # 将消息会话和 ID 一并传入 chemical_code 函数
    else:
        await msg.finish(msg.locale.t('chemical_code.message.csid.invalid'))


async def chemical_code(msg: Bot.MessageSession, id=None, random_mode=True, captcha_mode=False):
    # 要求传入消息会话和 ChemSpider ID，ID 留空将会使用缺省值 None
    # 检查对象（群组或私聊）是否在 play_state 中有记录及是否为活跃状态
    if msg.target.target_id in play_state and play_state[msg.target.target_id]['active']:
        await msg.finish(msg.locale.t('game.message.running'))
    play_state.update({msg.target.target_id: {'active': True}})  # 若无，则创建一个新的记录并标记为活跃状态
    try:
        csr = await search_csr(id)  # 尝试获取 ChemSpider ID 对应的化学式列表
    except Exception as e:  # 意外情况
        traceback.print_exc()  # 打印错误信息
        play_state[msg.target.target_id]['active'] = False  # 将对象标记为非活跃状态
        return await msg.finish(msg.locale.t('chemical_code.message.error'))
    # print(csr)
    play_state[msg.target.target_id]['answer'] = csr['name']  # 将正确答案标记于 play_state 中存储的对象中
    Logger.info(f'Answer: {csr["name"]}')  # 在日志中输出正确答案
    Logger.info(f'Image: {csr["image"]}')  # 在日志中输出图片链接
    download = False
    if csr["id"] in special_id:  # 如果正确答案在 special_id 中
        file_path = os.path.abspath(f'./assets/chemicalcode/special_id/{csr["id"]}.png')
        Logger.info(f'File path: {file_path}')  # 在日志中输出文件路径
        exists_file = os.path.exists(file_path)  # 尝试获取图片文件是否存在
        if exists_file:
            download = file_path
    if not download:
        download = await download_to_cache(csr['image'])  # 从结果中获取链接并下载图片

    with PILImage.open(download) as im:  # 打开下载的图片
        im = im.convert("RGBA")  # 转换为 RGBA 格式
        image = PILImage.new("RGBA", im.size, 'white')  # 创建新图片
        image.alpha_composite(im, (0, 0))  # 将图片合并到新图片中
        newpath = random_cache_path() + '.png'  # 创建新文件名
        image.save(newpath)  # 保存新图片

    set_timeout = csr['length'] // 30
    if set_timeout < 2:
        set_timeout = 2

    async def ans(msg: Bot.MessageSession, answer, random_mode):  # 定义回答函数的功能
        wait = await msg.wait_anyone()  # 等待对象内的任意人回答
        if play_state[msg.target.target_id]['active']:  # 检查对象是否为活跃状态
            if (wait_text := wait.as_display(text_only=True)) != answer:  # 如果回答不正确
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

                Logger.info(f'{wait_text} != {answer}')  # 输出日志
                return await ans(wait, answer, random_mode)  # 进行下一轮检查
            else:
                send_ = wait.locale.t('chemical_code.message.correct')
                if random_mode:
                    if g_msg := gained_petal(wait, 2):
                        send_ += '\n' + g_msg
                await wait.send_message(send_)
                play_state[msg.target.target_id]['active'] = False  # 将对象标记为非活跃状态

    async def timer(start):  # 计时器函数
        if play_state[msg.target.target_id]['active']:  # 检查对象是否为活跃状态
            if datetime.now().timestamp() - start > 60 * set_timeout:  # 如果超过2分钟
                await msg.send_message(
                    msg.locale.t('chemical_code.message.timeup', answer=play_state[msg.target.target_id]["answer"]))
                play_state[msg.target.target_id]['active'] = False
            else:  # 如果未超时
                await asyncio.sleep(1)  # 等待1秒
                await timer(start)  # 重新调用计时器函数

    if not captcha_mode:
        await msg.send_message([Plain(msg.locale.t('chemical_code.message.showid', id=csr["id"])), Image(newpath),
                                Plain(msg.locale.t('chemical_code.message', times=set_timeout))])
        time_start = datetime.now().timestamp()  # 记录开始时间

        await asyncio.gather(ans(msg, csr['name'], random_mode), timer(time_start))  # 同时启动回答函数和计时器函数
    else:
        result = await msg.wait_next_message([Plain(msg.locale.t('chemical_code.message.showid', id=csr["id"])),
                                              Image(newpath), Plain(msg.locale.t('chemical_code.message.captcha',
                                                                                 times=set_timeout))])
        if play_state[msg.target.target_id]['active']:  # 检查对象是否为活跃状态
            if result.as_display(text_only=True) == csr['name']:
                send_ = msg.locale.t('chemical_code.message.correct')
                if g_msg := gained_petal(msg, 1):
                    send_ += '\n' + g_msg
                await result.send_message(send_)
            else:
                await result.send_message(
                    msg.locale.t('chemical_code.message.incorrect', answer=play_state[msg.target.target_id]["answer"]))
            play_state[msg.target.target_id]['active'] = False
