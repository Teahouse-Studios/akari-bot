import re

from .orm import WikiWhitelist
from database.orm import DBSession
from tenacity import retry, stop_after_attempt

session = DBSession().session


@retry(stop=stop_after_attempt(3))
def audit_query(apiLinkRegex: str):
    try:
        session.expire_all()
        link = session.query(WikiWhitelist).filter_by(apiLinkRegex=apiLinkRegex).first()
        if link is not None:
            return True
        else:
            return False
    except Exception:
        session.rollback()
        raise


@retry(stop=stop_after_attempt(3))
def audit_allow(apiLinkRegex: str, operator: str):
    if audit_query(apiLinkRegex):
        return False
    try:
        session.add(WikiWhitelist(apiLinkRegex=apiLinkRegex, operator=operator))
        session.commit()
        session.expire_all()
        return True
    except Exception:
        session.rollback()
        raise


@retry(stop=stop_after_attempt(3))
def audit_remove(apiLinkRegex_: str):
    if not audit_query(apiLinkRegex_):
        return False
    try:
        session.query(WikiWhitelist).filter(WikiWhitelist.apiLinkRegex == apiLinkRegex_).delete()
        session.expire_all()
        return True
    except Exception:
        session.rollback()
        raise


@retry(stop=stop_after_attempt(3))
def audit_list():
    try:
        return session.query(WikiWhitelist.apiLinkRegex, WikiWhitelist.operator)
    except Exception:
        raise


def check_whitelist(apiLink: str):
    whitepair = audit_list()
    whitelist = []
    for pair in whitepair:
        whitelist.append(pair[0])
    for pattern in whitelist:
        if re.match(pattern, apiLink):
            return True
    return False


class WikiWhitelistError(Exception):
    '''The wiki is not in the bot whitelist'''
