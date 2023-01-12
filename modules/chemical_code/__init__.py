import asyncio
import os
import random
import re
import traceback
from datetime import datetime

from PIL import Image as PILImage
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt

from core.builtins.message import MessageSession
from core.component import on_command
from core.elements import Image, Plain
from core.logger import Logger
from core.utils import get_url, download_to_cache, random_cache_path

csr_link = 'https://www.chemspider.com'  # ChemSpider 的链接
special_id = ["22398", "140526", "4509317", "4509318", "4510681", "4510778", "4512975", "4514248", "4514266", "4514293",
              "4514330", "4514408", "4514534", "4514586", "4514603", "4515054", "4573995", "4574465", "4575369",
              "4575370",
              "4575371", "4885606", "4885717", "4886482", "4886484", "20473555", "21865276", "21865280"]  # 可能会导致识别问题的物质（如部分单质）ID，这些 ID 的图片将会在本地调用


@retry(stop=stop_after_attempt(3), reraise=True)
async def search_csr(id=None):  # 根据 ChemSpider 的 ID 查询 ChemSpider 的链接，留空（将会使用缺省值 None）则随机查询
    if id is not None:  # 如果传入了 ID，则使用 ID 查询
        answer_id = id
    else:
        answer_id = random.randint(1, 115015500)  # 否则随机查询一个题目
    answer_id = str(answer_id)
    Logger.info("ChemSpider ID: " + answer_id)
    get = await get_url(csr_link + '/Search.aspx?q=' + answer_id, 200, fmt='text')  # 在 ChemSpider 上搜索此化学式或 ID
    # Logger.info(get)
    soup = BeautifulSoup(get, 'html.parser')  # 解析 HTML
    name = soup.find('span',
                     id='ctl00_ctl00_ContentSection_ContentPlaceHolder1_RecordViewDetails_rptDetailsView_ctl00_prop_MF').text  # 获取化学式名称
    values_ = re.split(r'[A-Za-z]+', name)  # 去除化学式名称中的字母
    value = 0  # 起始元素记数，忽略单个元素（有无意义不大）
    for v in values_:  # 遍历剔除字母后的数字
        if v.isdigit():
            value += int(v)  # 加一起
    wh = 500 * value // 100
    if wh < 500:
        wh = 500
    return {'id': answer_id, 'name': name,
            'image': f'https://www.chemspider.com/ImagesHandler.ashx?id={answer_id}' +
                     (f"&w={wh}&h={wh}" if answer_id not in special_id else ""), 'length': value}


cc = on_command('chemical_code', alias={'cc': 'chemical_code',
                                        'chemicalcode': 'chemical_code',
                                        'captcha': 'chemical_code captcha'},
                desc='化学式回答小游戏', developers=['OasisAkari'])
play_state = {}  # 创建一个空字典用于存放游戏状态


@cc.handle('{普通样式（时间限制，多人）}')  # 直接使用 cc 命令将触发此装饰器
async def chemical_code_by_random(msg: MessageSession):
    await chemical_code(msg)  # 将消息会话传入 chemical_code 函数


@cc.handle('captcha {验证码样式（不支持指定ID，只限一次，单人）}')
async def _(msg: MessageSession):
    await chemical_code(msg, captcha_mode=True)


@cc.handle('stop {停止当前的游戏。}')
async def s(msg: MessageSession):
    state = play_state.get(msg.target.targetId, False)  # 尝试获取 play_state 中是否有此对象的游戏状态
    if state:  # 若有
        if state['active']:  # 检查是否为活跃状态
            play_state[msg.target.targetId]['active'] = False  # 标记为非活跃状态
            await msg.sendMessage(f'已停止，正确答案是 {state["answer"]}', quote=False)  # 发送存储于 play_state 中的答案
        else:
            await msg.sendMessage('当前无活跃状态的游戏。')
    else:
        await msg.sendMessage('当前无活跃状态的游戏。')


@cc.handle('<csid> {根据 ChemSpider ID 出题}')
async def chemical_code_by_id(msg: MessageSession):
    id = msg.parsed_msg['<csid>']  # 从已解析的消息中获取 ChemSpider ID
    if id.isdigit():  # 如果 ID 为纯数字
        await chemical_code(msg, id)  # 将消息会话和 ID 一并传入 chemical_code 函数
    else:
        await msg.finish('请输入纯数字ID！')


async def chemical_code(msg: MessageSession, id=None, captcha_mode=False):  # 要求传入消息会话和 ChemSpider ID，ID 留空将会使用缺省值 None
    if msg.target.targetId in play_state and play_state[msg.target.targetId][
        'active']:  # 检查对象（群组或私聊）是否在 play_state 中有记录及是否为活跃状态
        await msg.finish('当前有一局游戏正在进行中。')
    play_state.update({msg.target.targetId: {'active': True}})  # 若无，则创建一个新的记录并标记为活跃状态
    try:
        csr = await search_csr(id)  # 尝试获取 ChemSpider ID 对应的化学式列表
    except Exception as e:  # 意外情况
        traceback.print_exc()  # 打印错误信息
        play_state[msg.target.targetId]['active'] = False  # 将对象标记为非活跃状态
        return await msg.finish('发生错误：拉取题目失败，可能是因为请求超时或 ID 无效，请重新发起游戏。')
    # print(csr)
    play_state[msg.target.targetId]['answer'] = csr['name']  # 将正确答案标记于 play_state 中存储的对象中
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

    async def ans(msg: MessageSession, answer):  # 定义回答函数的功能
        wait = await msg.waitAnyone()  # 等待对象内的任意人回答
        if play_state[msg.target.targetId]['active']:  # 检查对象是否为活跃状态
            if wait.asDisplay() != answer:  # 如果回答不正确
                Logger.info(f'{wait.asDisplay()} != {answer}')  # 输出日志
                return await ans(wait, answer)  # 进行下一轮检查
            else:
                await wait.sendMessage('回答正确。')
                play_state[msg.target.targetId]['active'] = False  # 将对象标记为非活跃状态

    async def timer(start):  # 计时器函数
        if play_state[msg.target.targetId]['active']:  # 检查对象是否为活跃状态
            if datetime.now().timestamp() - start > 60 * set_timeout:  # 如果超过2分钟
                await msg.sendMessage(f'已超时，正确答案是 {play_state[msg.target.targetId]["answer"]}')
                play_state[msg.target.targetId]['active'] = False
            else:  # 如果未超时
                await asyncio.sleep(1)  # 等待1秒
                await timer(start)  # 重新调用计时器函数

    if not captcha_mode:
        await msg.sendMessage([Image(newpath),
                               Plain(f'请在 {set_timeout} 分钟内发送这个化合物的分子式。（除 C、H 外使用字母表顺序，如：CHBrClF）')])
        time_start = datetime.now().timestamp()  # 记录开始时间

        await asyncio.gather(ans(msg, csr['name']), timer(time_start))  # 同时启动回答函数和计时器函数
    else:
        result = await msg.waitNextMessage([Image(newpath), Plain('请发送这个化合物的分子式。（除 C、H 外使用字母表顺序，如：CHBrClF）')])
        if play_state[msg.target.targetId]['active']:  # 检查对象是否为活跃状态
            if result.asDisplay() == csr['name']:
                await result.sendMessage('回答正确。')
            else:
                await result.sendMessage('回答错误，正确答案是 ' + csr['name'])
            play_state[msg.target.targetId]['active'] = False
