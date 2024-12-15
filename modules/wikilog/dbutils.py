import re

import orjson as json
from tenacity import retry, stop_after_attempt

from core.builtins import Bot
from core.database import session, auto_rollback_error
from modules.wikilog.orm import WikiLogTargetSetInfo


class WikiLogUtil:
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def __init__(self, msg: [Bot.MessageSession, str]):
        if isinstance(msg, Bot.MessageSession):
            if msg.target.target_from != "QQ|Guild":
                target_id = msg.target.target_id
            else:
                target_id = re.match(
                    r"(QQ\|Guild\|.*?)\|.*", msg.target.target_id
                ).group(1)
        else:
            target_id = msg
        self.query = (
            session.query(WikiLogTargetSetInfo).filter_by(targetId=target_id).first()
        )
        if not self.query:
            session.add_all([WikiLogTargetSetInfo(targetId=target_id, infos="{}")])
            session.commit()
            self.query = (
                session.query(WikiLogTargetSetInfo)
                .filter_by(targetId=target_id)
                .first()
            )

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def conf_wiki(self, apilink: dict, add=False, reset=False):
        infos = json.loads(self.query.infos)
        if add or reset:
            if apilink not in infos or reset:
                infos[apilink] = {}
                infos[apilink].setdefault(
                    "AbuseLog", {"enable": False, "filters": ["*"]}
                )
                infos[apilink].setdefault(
                    "RecentChanges",
                    {"enable": False, "filters": ["*"], "rcshow": ["!bot"]},
                )
                infos[apilink].setdefault("use_bot", False)
                infos[apilink].setdefault("keep_alive", False)
                self.query.infos = json.dumps(infos)
                session.commit()
                session.expire_all()
                return True
        else:
            if apilink in infos:
                del infos[apilink]
                self.query.infos = json.dumps(infos)
                session.commit()
                session.expire_all()
                return True
        return False

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def conf_log(self, apilink: str, logname: str, enable=False):
        infos = json.loads(self.query.infos)
        if apilink in infos:
            infos[apilink][logname]["enable"] = enable
            self.query.infos = json.dumps(infos)
            session.commit()
            session.expire_all()
            return True
        return False

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def set_filters(self, apilink: str, logname: str, filters: list[str]):
        infos = json.loads(self.query.infos)
        if apilink in infos:
            infos[apilink][logname]["filters"] = filters
            self.query.infos = json.dumps(infos)
            session.commit()
            session.expire_all()
            return True
        return False

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def get_filters(self, apilink: str, logname: str):
        infos = json.loads(self.query.infos)
        if apilink in infos:
            return infos[apilink][logname]["filters"]
        return False

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def set_rcshow(self, apilink: str, rcshow: list):
        infos = json.loads(self.query.infos)
        if apilink in infos:
            infos[apilink]["RecentChanges"]["rcshow"] = rcshow
            self.query.infos = json.dumps(infos)
            session.commit()
            session.expire_all()
            return True
        return False

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def get_rcshow(self, apilink: str):
        infos = json.loads(self.query.infos)
        if apilink in infos:
            return infos[apilink]["RecentChanges"]["rcshow"]
        return False

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def set_use_bot(self, apilink: str, use_bot: bool):
        infos = json.loads(self.query.infos)
        if apilink in infos:
            infos[apilink]["use_bot"] = use_bot
            self.query.infos = json.dumps(infos)
            session.commit()
            session.expire_all()
            return True
        return False

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def get_use_bot(self, apilink: str):
        infos = json.loads(self.query.infos)
        if apilink in infos:
            return infos[apilink]["use_bot"]
        return False

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def set_keep_alive(
        self, apilink: str, keep_alive: bool
    ):  # oh no it smells shit, will rewrite it in the future
        infos = json.loads(self.query.infos)
        if apilink in infos:
            infos[apilink]["keep_alive"] = keep_alive
            self.query.infos = json.dumps(infos)
            session.commit()
            session.expire_all()
            return True
        return False

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def get_keep_alive(self, apilink: str):
        infos = json.loads(self.query.infos)
        if apilink in infos and "keep_alive" in infos[apilink]:
            return infos[apilink]["keep_alive"]
        return False

    @staticmethod
    def return_all_data():
        all_data = session.query(WikiLogTargetSetInfo).all()
        data_d = {}
        for x in all_data:
            data_d[x.targetId] = json.loads(x.infos)
        return data_d
