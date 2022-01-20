from typing import Union

from tenacity import retry, stop_after_attempt

from core.elements import MessageSession
from database import session, auto_rollback_error
from .orm import ArcBindInfo


class ArcBindInfoManager:
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def __init__(self, msg: MessageSession):
        self.targetId = msg.target.senderId
        self.query = session.query(ArcBindInfo).filter_by(targetId=self.targetId).first()
        if self.query is None:
            session.add_all([ArcBindInfo(targetId=self.targetId, username='', friendcode='')])
            session.commit()
            self.query = session.query(ArcBindInfo).filter_by(targetId=self.targetId).first()

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def get_bind_friendcode(self) -> Union[str, None]:
        bind_info = self.query.friendcode
        if bind_info != '':
            return bind_info
        return None

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def set_bind_info(self, username, friendcode):
        self.query.username = username
        self.query.friendcode = friendcode
        session.commit()
        return True

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def remove_bind_info(self):
        session.delete(self.query)
        session.commit()
        return True
