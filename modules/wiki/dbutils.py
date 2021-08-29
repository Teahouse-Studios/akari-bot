import ujson as json

from core.elements import MessageSession
from .orm import session, WikiTargetSetInfo, WikiInfo


class WikiTargetInfo:
    def __init__(self, msg: [MessageSession, str]):
        if isinstance(msg, MessageSession):
            targetId = msg.target.targetId
        else:
            targetId = msg
        self.query = session.query(WikiTargetSetInfo).filter_by(targetId=targetId).first()
        if self.query is None:
            try:
                session.add_all([WikiTargetSetInfo(targetId=targetId, iws='{}', headers='{}')])
                session.commit()
            except Exception:
                session.rollback()
                raise
            self.query = session.query(WikiTargetSetInfo).filter_by(targetId=targetId).first()

    def add_start_wiki(self, url):
        try:
            self.query.link = url
            session.commit()
            session.expire_all()
            return True
        except Exception:
            session.rollback()
            raise

    def get_start_wiki(self):
        if self.query is not None:
            return self.query.link if self.query.link is not None else False
        return False

    def config_interwikis(self, iw: str, iwlink: str = None, let_it=True):
        try:
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
        except Exception:
            session.rollback()
            raise

    def get_interwikis(self):
        q = self.query.iws
        if q is not None:
            iws = json.loads(q)
            return iws
        else:
            return False

    def config_headers(self, headers, let_it: [bool, None] = True):
        try:
            headers_ = json.loads(self.query.headers)
            if let_it:
                for x in headers:
                    headers_[x] = headers[x]
            elif let_it is None:
                headers_ = {}
            else:
                for x in headers:
                    if x in headers_:
                        del headers_[x]
            self.query.headers = json.dumps(headers_)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise

    def get_headers(self):
        if self.query is not None:
            q = self.query.headers
            headers = json.loads(q)
        else:
            headers = {'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6'}
        return headers


class WikiSiteInfo:
    def __init__(self, api_link):
        self.api_link = api_link
        self.query = session.query(WikiInfo).filter_by(apiLink=api_link).first()

    def get(self):
        if self.query is not None:
            return self.query.siteInfo, self.query.timestamp
        return False

    def update(self, info: dict):
        try:
            if self.query is None:
                session.add_all([WikiInfo(apiLink=self.api_link, siteInfo=json.dumps(info))])
            else:
                self.query.siteInfo = json.dumps(info)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise