import json
import re

from google_play_scraper import app as google_play_scraper

from core.elements import ErrorMessage
from core.logger import Logger
from core.utils import get_url


async def mcv():
    try:
        data = json.loads(await get_url('https://piston-meta.mojang.com/mc/game/version_manifest.json', 200))
        message1 = f"最新版：{data['latest']['release']}，最新快照：{data['latest']['snapshot']}"
    except (ConnectionError, OSError):  # Probably...
        message1 = "获取manifest.json失败。"
    try:
        mojira = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/10400/versions', 200))
        release = []
        prefix = ' | '
        for v in mojira:
            if not v['archived']:
                release.append(v['name'])
        message2 = prefix.join(release)
    except Exception:
        message2 = "获取Mojira信息失败。"
    return f"""目前启动器内最新版本为：
{message1}，
Mojira上所记录最新版本为：
{message2}
（以启动器内最新版本为准，Mojira仅作版本号预览用）"""


async def mcbv():
    try:  # play store
        play_store_version = google_play_scraper('com.mojang.minecraftpe')['version']
    except Exception:
        play_store_version = '获取失败'
    try:
        data = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/10200/versions', 200))
    except (ConnectionError, OSError):  # Probably...
        return ErrorMessage('土豆熟了')
    beta = []
    preview = []
    release = []
    for v in data:
        if not v['archived']:
            if re.match(r".*Beta$", v["name"]):
                beta.append(v["name"])
            elif re.match(r".*Preview$", v["name"]):
                preview.append(v["name"])
            else:
                if v["name"] != "Future Release":
                    release.append(v["name"])
    fix = " | "
    msg2 = f'Beta: {fix.join(beta)}\nPreview: {fix.join(preview)}\nRelease: {fix.join(release)}'
    return f"""目前商店内最新正式版为：
{play_store_version}，
Mojira上所记录最新版本为：
{msg2}
（以商店内最新版本为准，Mojira仅作版本号预览用）"""


async def mcdv():
    try:
        data = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/11901/versions', 200))
    except (ConnectionError, OSError):  # Probably...
        return ErrorMessage('土豆熟了')
    release = []
    for v in data:
        if not v['archived']:
            release.append(v["name"])
    return f'最新版：{" | ".join(release)} \n（数据来源于MoJira，可能会比官方发布要早一段时间。信息仅供参考。）'


async def mcev():
    try:
        data = await get_url('https://meedownloads.blob.core.windows.net/win32/x86/updates/Updates.txt', 200)
        Logger.debug(data)
        version = re.search(r'(?<=\[)(.*?)(?=])', data)[0]
        Logger.debug(version)
    except (ConnectionError, OSError):  # Probably...
        return ErrorMessage('土豆熟了')
    return f'最新版：{version}'
