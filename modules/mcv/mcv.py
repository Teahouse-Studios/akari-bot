import json
import re
from core.elements.others import ErrorMessage

from core.utils import get_url


async def mcv():
    try:
        data = json.loads(await get_url('http://launchermeta.mojang.com/mc/game/version_manifest.json'))
        message1 = f"最新版：{data['latest']['release']}，最新快照：{data['latest']['snapshot']}"
    except (ConnectionError, OSError):  # Probably...
        message1 = "获取manifest.json失败。"
    try:
        mojira = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/10400/versions'))
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
    try:
        data = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/10200/versions'))
    except (ConnectionError, OSError):  # Probably...
        return ErrorMessage('土豆熟了')
    beta = []
    release = []
    for v in data:
        if not v['archived']:
            match = re.match(r"(.*Beta)$", v["name"])
            if match:
                beta.append(match.group(1))
            else:
                release.append(v["name"])
    fix = " | "
    return f'Beta：{fix.join(beta)}，Release：{fix.join(release)}\n' \
           f'（数据来源于MoJira，可能会比官方发布要早一段时间。信息仅供参考。）'


async def mcdv():
    try:
        data = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/11901/versions'))
    except (ConnectionError, OSError):  # Probably...
        return ErrorMessage('土豆熟了')
    release = []
    for v in data:
        if not v['archived']:
            release.append(v["name"])
    return f'最新版：{" | ".join(release)} \n（数据来源于MoJira，可能会比官方发布要早一段时间。信息仅供参考。）'


async def mcev():
    try:
        data = await get_url('https://meedownloads.blob.core.windows.net/win32/x86/updates/Updates.txt')
        print(data)
        version = re.search(r'(?<=\[)(.*?)(?=\])', data)[0]
        print(version)
    except (ConnectionError, OSError):  # Probably...
        return ErrorMessage('土豆熟了')
    return f'最新版：{version}'
