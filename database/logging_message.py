import datetime

import ujson as json
from sqlalchemy import create_engine, Column, String, Text, Integer, TIMESTAMP, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from tenacity import retry, stop_after_attempt

Base = declarative_base()

DB_LINK = 'sqlite:///database/msg.db'


class MSG(Base):
    __tablename__ = "msg"
    id = Column(Integer, primary_key=True)
    targetId = Column(String(512))
    command = Column(Text)
    message = Column(Text)


class DirtyFilterTable(Base):
    __tablename__ = "filter_cache"
    desc = Column(Text, primary_key=True)
    result = Column(Text)
    timestamp = Column(TIMESTAMP, default=text('CURRENT_TIMESTAMP'))


class UnfriendlyActionsTable(Base):
    __tablename__ = "unfriendly_action"
    id = Column(Integer, primary_key=True)
    targetId = Column(String(512))
    senderId = Column(String(512))
    action = Column(String(512))
    detail = Column(String(512))
    timestamp = Column(TIMESTAMP, default=text('CURRENT_TIMESTAMP'))


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


def LoggerMSG(userid, command, msg):
    session.add_all([MSG(targetId=userid, command=command, message=msg)])
    session.commit()


class DirtyWordCache:
    @retry(stop=stop_after_attempt(3))
    @auto_rollback_error
    def __init__(self, query_word):
        self.query_word = query_word
        self.query = session.query(DirtyFilterTable).filter_by(desc=self.query_word).first()
        self.need_insert = False
        if self.query is None:
            self.need_insert = True
        if self.query is not None and datetime.datetime.now().timestamp() - self.query.timestamp.timestamp() > 86400:
            session.delete(self.query)
            session.commit()
            self.need_insert = True

    @retry(stop=stop_after_attempt(3))
    @auto_rollback_error
    def update(self, result: dict):
        session.add_all([DirtyFilterTable(desc=self.query_word, result=json.dumps(result))])
        session.commit()

    def get(self):
        if not self.need_insert:
            return json.loads(self.query.result)
        else:
            return False


class UnfriendlyActions:
    def __init__(self, targetId, senderId):
        self.targetId = targetId
        self.senderId = senderId

    @retry(stop=stop_after_attempt(3))
    @auto_rollback_error
    def check_mute(self) -> bool:
        """

        :return: True = yes, False = no
        """
        query = session.query(UnfriendlyActionsTable).filter_by(targetId=self.targetId).all()
        unfriendly_list = []
        for records in query:
            if datetime.datetime.now().timestamp() - records.timestamp.timestamp() < 432000:
                unfriendly_list.append(records)
        if len(unfriendly_list) > 5:
            return True
        count = {}
        for criminal in unfriendly_list:
            if datetime.datetime.now().timestamp() - criminal.timestamp.timestamp() < 86400:
                if criminal.senderId not in count:
                    count[criminal.senderId] = 0
                else:
                    count[criminal.senderId] += 1
        if len(count) >= 3:
            return True
        for convict in count:
            if count[convict] >= 3:
                return True
        return False

    @retry(stop=stop_after_attempt(3))
    @auto_rollback_error
    def add_and_check(self, action='default', detail='') -> bool:
        """

        :return: True = yes, False = no
        """
        session.add_all(
            [UnfriendlyActionsTable(targetId=self.targetId, senderId=self.senderId, action=action, detail=detail)])
        session.commit()
        return self.check_mute()
