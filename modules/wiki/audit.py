import re

from tenacity import retry, stop_after_attempt

from database import auto_rollback_error, session
from .orm import WikiWhitelist


@retry(stop=stop_after_attempt(3))
@auto_rollback_error
def audit_query(apiLinkRegex: str):
    session.expire_all()
    link = session.query(WikiWhitelist).filter_by(apiLinkRegex=apiLinkRegex).first()
    if link is not None:
        return True
    else:
        return False


@retry(stop=stop_after_attempt(3))
@auto_rollback_error
def audit_allow(apiLinkRegex: str, operator: str):
    if audit_query(apiLinkRegex):
        return False
    session.add(WikiWhitelist(apiLinkRegex=apiLinkRegex, operator=operator))
    session.commit()
    session.expire_all()
    return True


@retry(stop=stop_after_attempt(3))
@auto_rollback_error
def audit_remove(apiLinkRegex_: str):
    if not audit_query(apiLinkRegex_):
        return False
    session.query(WikiWhitelist).filter(WikiWhitelist.apiLinkRegex == apiLinkRegex_).delete()
    session.expire_all()
    return True


@retry(stop=stop_after_attempt(3))
@auto_rollback_error
def audit_list():
    return session.query(WikiWhitelist.apiLinkRegex, WikiWhitelist.operator)


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
