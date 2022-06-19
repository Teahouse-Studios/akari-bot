import asyncio
import random

from sqlalchemy import create_engine, Column, String, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from tenacity import retry, stop_after_attempt

from datetime import datetime

from core.component import on_command
from core.elements import MessageSession, Image, Plain
from core.utils import download_to_cache, random_cache_path
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


cc = on_command('chemical_code', alias=['cc', 'chemicalcode'], desc='化学式验证码测试', developers=['OasisAkari'])
play_state = {}


@cc.handle()
async def _(msg: MessageSession):
    if msg.target.targetId in play_state and play_state[msg.target.targetId]['active']:
        await msg.finish('当前有一局游戏正在进行中。')
    play_state.update({msg.target.targetId: {'active': True}})
    get_rand = randcc()
    get_image = await download_to_cache(f'https://www.chemicalbook.com/CAS/GIF/{get_rand[0]}.gif')
    Logger.info(get_rand[1])
    play_state[msg.target.targetId]['answer'] = get_rand[1]

    with PILImage.open(get_image) as im:
        if im.size[0] == 4:
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
        image.save(newpath)

    await msg.sendMessage([Image(newpath),
                           Plain('请于2分钟内发送正确答案。（请使用字母表顺序，如：CHBrClF）')])
    time_start = datetime.now().timestamp()

    async def ans(msg: MessageSession, answer):
        wait = await msg.waitAnyone()
        if play_state[msg.target.targetId]['active']:
            if wait.asDisplay() != answer:
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

    await asyncio.gather(ans(msg, get_rand[1]), timer(time_start))


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


