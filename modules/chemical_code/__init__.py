import asyncio
import random
import traceback

from bs4 import BeautifulSoup
from sqlalchemy import create_engine, Column, String, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from tenacity import retry, stop_after_attempt

from datetime import datetime

from core.component import on_command
from core.elements import MessageSession, Image, Plain
from core.utils import get_url, download_to_cache, random_cache_path
from core.logger import Logger

from PIL import Image as PILImage


Base = declarative_base()

DB_LINK = 'sqlite:///modules/chemical_code/answer.db'


class Answer(Base):
    __tablename__ = "Answer"
    id = Column(Integer, primary_key=True)
    cas = Column(String(512))
    answer = Column(Text)


class MSGDBSession:
    def __init__(self):
        self.engine = engine = create_engine(DB_LINK)
        Base.metadata.create_all(bind=engine, checkfirst=True)
        self.Session = sessionmaker()
        self.Session.configure(bind=self.engine)

    @property
    def session(self):
        return self.Session()


session = MSGDBSession().session


def auto_rollback_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            session.rollback()
            raise e

    return wrapper


@retry(stop=stop_after_attempt(3))
@auto_rollback_error
def randcc():
    num = random.randint(1, 20000)
    query = session.query(Answer).filter_by(id=num).first()
    return query.cas, query.answer


csr_link = 'https://www.chemspider.com'


@retry(stop=stop_after_attempt(3), reraise=True)
async def search_csr(id=None):
    if id is not None:
        answer = id
    else:
        cas, answer = randcc()
    get = await get_url(csr_link + '/Search.aspx?q=' + answer, 200, fmt='text')
    # Logger.info(get)
    soup = BeautifulSoup(get, 'html.parser')
    rlist = []
    try:
        results = soup.find_all('tbody')[0].find_all('tr')
        for x in results:
            sub = x.find_all('td')[0:4]
            name = sub[2].text
            image = sub[1].find_all('img')[0].get('src')
            rlist.append({'name': name, 'image': csr_link + image + '&w=500&h=500'})
    except IndexError:
        try:
            name = soup.find('span',
                             id='ctl00_ctl00_ContentSection_ContentPlaceHolder1_RecordViewDetails_rptDetailsView_ctl00_prop_MF').text
            image = soup.find('img',
                              id='ctl00_ctl00_ContentSection_ContentPlaceHolder1_RecordViewDetails_rptDetailsView_ctl00_ThumbnailControl1_viewMolecule')\
                .get('src')
            rlist.append({'name': name, 'image': csr_link + image})
        except Exception as e:
            raise e


    return rlist


cc = on_command('chemical_code', alias=['cc', 'chemicalcode'], desc='化学式验证码测试', developers=['OasisAkari'])
play_state = {}


@cc.handle()
async def chemical_code_by_random(msg: MessageSession):
    await c(msg)


@cc.handle('<id> {根据 ID 出题}')
async def chemical_code_by_id(msg: MessageSession):
    id = msg.parsed_msg['<id>']
    if id.isdigit():
        await c(msg, id)


async def c(msg: MessageSession, id=None):
    if msg.target.targetId in play_state and play_state[msg.target.targetId]['active']:
        await msg.finish('当前有一局游戏正在进行中。')
    play_state.update({msg.target.targetId: {'active': True}})
    try:
        csr = await search_csr(id)
    except Exception as e:
        traceback.print_exc()
        play_state[msg.target.targetId]['active'] = False
        return await msg.finish('发生错误：拉取题目失败，请重新发起游戏。')
    # print(csr)
    choice = random.choice(csr)
    play_state[msg.target.targetId]['answer'] = choice['name']
    Logger.info(f'Answer: {choice["name"]}')

    """get_image = await download_to_cache(f'https://www.chemicalbook.com/CAS/GIF/{get_rand[0]}.gif')
    Logger.info(get_rand[1])
    play_state[msg.target.targetId]['answer'] = get_rand[1]

    with PILImage.open(get_image) as im:
        if im.size[0] < 10:
            del play_state[msg.target.targetId]
            return await _(msg)
        im.seek(0)
        image = im.convert("RGBA")
        datas = image.getdata()
        newData = []
        for item in datas:
            if item[3] == 0:  # if transparent
                newData.append((230, 230, 230))  # set transparent color in jpg
            else:
                newData.append(tuple(item[:3]))
        image = PILImage.new("RGBA", im.size)
        image.getdata()
        image.putdata(newData)
        newpath = random_cache_path() + '.png'
        image.save(newpath)"""

    download = await download_to_cache(choice['image'])

    with PILImage.open(download) as im:
        datas = im.getdata()
        newData = []
        for item in datas:
            if item[3] == 0:  # if transparent
                newData.append((230, 230, 230))  # set transparent color in jpg
            else:
                newData.append(tuple(item[:3]))
        image = PILImage.new("RGBA", im.size)
        image.getdata()
        image.putdata(newData)
        newpath = random_cache_path() + '.png'
        image.save(newpath)

    await msg.sendMessage([Image(newpath),
                           Plain('请于2分钟内发送正确答案。（请使用字母表顺序，如：CHBrClF）')])
    time_start = datetime.now().timestamp()

    async def ans(msg: MessageSession, answer):
        wait = await msg.waitAnyone()
        if play_state[msg.target.targetId]['active']:
            if wait.asDisplay() != answer:
                Logger.info(f'{wait.asDisplay()} != {answer}')
                return await ans(wait, answer)
            else:
                await wait.sendMessage('回答正确。')
                play_state[msg.target.targetId]['active'] = False

    async def timer(start):
        if play_state[msg.target.targetId]['active']:
            if datetime.now().timestamp() - start > 120:
                await msg.sendMessage(f'已超时，正确答案是 {play_state[msg.target.targetId]["answer"]}', quote=False)
                play_state[msg.target.targetId]['active'] = False
            else:
                await asyncio.sleep(1)
                await timer(start)

    await asyncio.gather(ans(msg, choice['name']), timer(time_start))


@cc.handle('stop {停止当前的游戏。}')
async def s(msg: MessageSession):
    state = play_state.get(msg.target.targetId, False)
    if state:
        if state['active']:
            play_state[msg.target.targetId]['active'] = False
            await msg.sendMessage(f'已停止，正确答案是 {state["answer"]}', quote=False)
        else:
            await msg.sendMessage('当前无活跃状态的游戏。')
    else:
        await msg.sendMessage('当前无活跃状态的游戏。')


