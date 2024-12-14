import datetime

from core import dirty_check as dirty
from core.constants.info import Info


def dark_check(message: str):
    blacklist = [
        "china-dictatorship" "cirosantilli",
        "gfwlist",
        "v2ray",
        "shadowsocks",
        "xi-yu-yan-kai-fa",
        "xi-winnie-rainbow-fart",
        "xi-speech-synthesizer",
        "dnmkrgi",
        "xi-speech-demo",
        "zhao",
        "programthink",
    ]
    if Info.dirty_word_check:
        return any(message.find(i) != -1 for i in blacklist)
    return False


def time_diff(time: str):
    datetimed = datetime.datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ").timestamp()
    now = datetime.datetime.now().timestamp()
    diff = now - datetimed
    t = diff / 60 / 60 / 24
    dw = " day(s)"
    if t < 1:
        t = diff / 60 / 60
        dw = " hour(s)"
        if t < 1:
            t = diff / 60
            dw = " minute(s)"
            if t < 1:
                t = diff
                dw = " second(s)"
    diff = str(int(t)) + dw
    return diff


async def dirty_check(text: str, *allowlist_check):
    allowlist = [
        "Teahouse-Studios",
        "Dianliang233",
        "OasisAkari",
        "Lakejason0",
        "wyapx",
        "XxLittleCxX",
        "lakejason0",
    ]
    if allowlist_check in allowlist:
        return False
    check = await dirty.check_bool(text)
    if check:
        return True
    return False
