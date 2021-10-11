import datetime
import ujson as json
from sqlalchemy import create_engine, Column, String, Text, Integer, TIMESTAMP, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


DB_LINK = 'sqlite:///database/msg.db'


class MSG(Base):
    __tablename__ = "msg"
    id = Column(Integer, primary_key=True)
    targetId = Column(String(512))
    command = Column(Text)
    message = Column(Text)


class DirtyFilter(Base):
    __tablename__ = "filter_cache"
    desc = Column(Text, primary_key=True)
    result = Column(Text)
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


def LoggerMSG(userid, command, msg):
    session.add_all([MSG(targetId=userid, command=command, message=msg)])
    session.commit()


class DirtyWordCache:
    def __init__(self, query_word):
        self.query_word = query_word
        self.query = session.query(DirtyFilter).filter_by(desc=self.query_word).first()
        self.need_insert = False
        if self.query is None:
            self.need_insert = True
        if self.query is not None and datetime.datetime.now().timestamp() - self.query.timestamp.timestamp() > 86400:
            session.delete(self.query)
            session.commit()
            self.need_insert = True

    def update(self, result: dict):
        session.add_all([DirtyFilter(desc=self.query_word, result=json.dumps(result))])
        session.commit()

    def get(self):
        if not self.need_insert:
            return json.loads(self.query.result)
        else:
            return False
