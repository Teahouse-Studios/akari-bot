from typing import Union

from tenacity import retry, stop_after_attempt

from core.builtins import Bot
from database import session, auto_rollback_error
from .orm import DivingProberBindInfo


class DivingProberBindInfoManager:
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def __init__(self, msg: Bot.MessageSession):
        self.target_id = msg.target.sender_id
        self.query = session.query(DivingProberBindInfo).filter_by(targetId=self.target_id).first()
        if not self.query:
            session.add_all([DivingProberBindInfo(targetId=self.target_id, username='')])
            session.commit()
            self.query = session.query(DivingProberBindInfo).filter_by(targetId=self.target_id).first()

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def get_bind_username(self) -> Union[str, None]:
        bind_info = self.query.username
        if bind_info != '':
            return bind_info
        return None

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def set_bind_info(self, username):
        self.query.username = username
        session.commit()
        return True

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def remove_bind_info(self):
        session.delete(self.query)
        session.commit()
        return True
