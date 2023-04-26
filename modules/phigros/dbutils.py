from typing import Union

from tenacity import retry, stop_after_attempt

from core.builtins import Bot
from database import session, auto_rollback_error
from .orm import PgrBindInfo


class ArcBindInfoManager:
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def __init__(self, msg: Bot.MessageSession):
        self.targetId = msg.target.senderId
        self.query = session.query(PgrBindInfo).filter_by(targetId=self.targetId).first()
        if self.query is None:
            session.add_all([PgrBindInfo(targetId=self.targetId, sessiontoken='')])
            session.commit()
            self.query = session.query(PgrBindInfo).filter_by(targetId=self.targetId).first()

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def get_bind_sessiontoken(self) -> Union[str, None]:
        bind_info = self.query.sessiontoken
        if bind_info != '':
            return bind_info
        return None

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def set_bind_info(self, username, sessiontoken):
        self.query.username = username
        self.query.sessiontoken = sessiontoken
        session.commit()
        return True

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def remove_bind_info(self):
        session.delete(self.query)
        session.commit()
        return True
