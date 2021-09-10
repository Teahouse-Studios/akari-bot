from sqlalchemy import create_engine, Column, String, Text, Integer
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
