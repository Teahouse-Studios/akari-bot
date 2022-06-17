import asyncio
import aiohttp
import random

from sqlalchemy import create_engine, Column, String, Text, Integer, TIMESTAMP, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from tenacity import retry, stop_after_attempt

from datetime import datetime

from core.component import on_command
from core.elements import MessageSession, Image, Plain
from core.utils import download_to_cache
from core.logger import Logger

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
playlist = []


@cc.handle()
async def _(msg: MessageSession):
    if msg.target.targetId in playlist:
        await msg.finish('当前有一局游戏正在进行中。')
    playlist.append(msg.target.targetId)
    get_rand = randcc()
    get_image = await download_to_cache(f'https://www.chemicalbook.com/CAS/GIF/{get_rand[0]}.gif')
    Logger.info(get_rand[1])
    await msg.sendMessage([Image(get_image), Plain('请于2分钟内发送正确答案。')])
    time_start = datetime.now().timestamp()

    async def ans(msg: MessageSession, answer):
        if datetime.now().timestamp() - time_start > 120:
            return await msg.sendMessage(f'已超时，正确答案是 {answer}', quote=False)
        if msg.asDisplay() != answer:
            next_ = await msg.waitAnyone()
            return await ans(next_, answer)
        else:
            await msg.sendMessage('回答正确。')
    wait = await msg.waitAnyone()
    await ans(wait, answer=get_rand[1])
    playlist.remove(msg.target.targetId)





