import re
from datetime import datetime
from typing import Union
from urllib.parse import urlparse

import orjson as json
from tenacity import retry, stop_after_attempt

from core.builtins import MessageSession
from core.database import session, auto_rollback_error
from modules.wiki.utils.orm import (
    WikiTargetSetInfo,
    WikiInfo,
    WikiAllowList,
    WikiBlockList,
    WikiBotAccountList,
)


class WikiTargetInfo:
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def __init__(self, msg: [MessageSession, str]):
        if isinstance(msg, MessageSession):
            if msg.target.target_from != "QQ|Guild":
                target_id = msg.target.target_id
            else:
                target_id = re.match(
                    r"(QQ\|Guild\|.*?)\|.*", msg.target.target_id
                ).group(1)
        else:
            target_id = msg
        self.query = (
            session.query(WikiTargetSetInfo).filter_by(targetId=target_id).first()
        )
        if not self.query:
            session.add_all(
                [WikiTargetSetInfo(targetId=target_id, iws="{}", headers="{}")]
            )
            session.commit()
            self.query = (
                session.query(WikiTargetSetInfo).filter_by(targetId=target_id).first()
            )

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def add_start_wiki(self, url):
        self.query.link = url
        session.commit()
        session.expire_all()
        return True

    def get_start_wiki(self) -> Union[str, None]:
        if self.query:
            return self.query.link if self.query.link else None

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def config_interwikis(self, iw: str, iwlink: str = None, let_it=True):
        interwikis = json.loads(self.query.iws)
        if let_it:
            interwikis[iw] = iwlink
        else:
            if iw in interwikis:
                del interwikis[iw]
        self.query.iws = json.dumps(interwikis)
        session.commit()
        session.expire_all()
        return True

    def get_interwikis(self) -> dict:
        q = self.query.iws
        if q:
            iws = json.loads(q)
            return iws
        return {}

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def config_headers(self, headers, let_it: [bool, None] = True):
        try:
            headers_ = json.loads(self.query.headers)
            if let_it:
                headers = json.loads(headers)
                for x in headers:
                    headers_[x] = headers[x]
            elif not let_it:
                headers_ = {}
            else:
                headers_ = {k: v for k, v in headers_.items() if k not in headers}
            self.query.headers = json.dumps(headers_)
            session.commit()
            return True
        except BaseException:
            return False

    def get_headers(self):
        if self.query:
            q = self.query.headers
            headers = json.loads(q)
        else:
            headers = {
                "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"
            }
        return headers

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def set_prefix(self, prefix: str):
        self.query.prefix = prefix
        session.commit()
        return True

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def del_prefix(self):
        self.query.prefix = None
        session.commit()
        return True

    def get_prefix(self):
        return self.query.prefix


class WikiSiteInfo:
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def __init__(self, api_link):
        self.api_link = api_link
        self.query = session.query(WikiInfo).filter_by(apiLink=api_link).first()

    def get(self):
        if self.query:
            return self.query.siteInfo, self.query.timestamp
        return False

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def update(self, info: dict):
        if not self.query:
            session.add_all(
                [WikiInfo(apiLink=self.api_link, siteInfo=json.dumps(info))]
            )
        else:
            self.query.siteInfo = json.dumps(info)
            self.query.timestamp = datetime.now()
        session.commit()
        return True

    @staticmethod
    def get_like_this(t: str):
        return session.query(WikiInfo).filter(WikiInfo.apiLink.like(f"%{t}%")).first()


class Audit:
    def __init__(self, api_link):
        self.api_link = api_link

    @property
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def inAllowList(self) -> bool:
        session.expire_all()
        apilink = urlparse(self.api_link).netloc
        return bool(
            session.query(WikiAllowList)
            .filter(WikiAllowList.apiLink.like(f"%{apilink}%"))
            .first()
        )

    @property
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def inBlockList(self) -> bool:
        session.expire_all()
        return bool(
            session.query(WikiBlockList).filter_by(apiLink=self.api_link).first()
        )

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def add_to_AllowList(self) -> bool:
        if self.inAllowList:
            return False
        session.add_all([WikiAllowList(apiLink=self.api_link)])
        session.commit()
        session.expire_all()
        return True

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def remove_from_AllowList(self) -> Union[bool, None]:
        if not self.inAllowList:
            return False
        if (
            query := session.query(WikiAllowList)
            .filter_by(apiLink=self.api_link)
            .first()
        ):
            session.delete(query)
            session.commit()
            session.expire_all()
            return True
        return None

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def add_to_BlockList(self) -> bool:
        if self.inBlockList:
            return False
        session.add_all([WikiBlockList(apiLink=self.api_link)])
        session.commit()
        session.expire_all()
        return True

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def remove_from_BlockList(self) -> bool:
        if not self.inBlockList:
            return False
        session.delete(
            session.query(WikiBlockList).filter_by(apiLink=self.api_link).first()
        )
        session.commit()
        session.expire_all()
        return True

    @staticmethod
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def get_allow_list() -> list:
        return session.query(WikiAllowList.apiLink, WikiAllowList.timestamp)

    @staticmethod
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def get_block_list() -> list:
        return session.query(WikiBlockList.apiLink, WikiBlockList.timestamp)


class BotAccount:
    @staticmethod
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def add(api_link, bot_account, bot_password):
        session.add_all(
            [
                WikiBotAccountList(
                    apiLink=api_link, botAccount=bot_account, botPassword=bot_password
                )
            ]
        )
        session.commit()
        session.expire_all()
        return True

    @staticmethod
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def remove(api_link):
        session.delete(
            session.query(WikiBotAccountList).filter_by(apiLink=api_link).first()
        )
        session.commit()
        session.expire_all()
        return True

    @staticmethod
    @retry(stop=stop_after_attempt(3), reraise=True)
    def get_all():
        return session.query(WikiBotAccountList).all()
