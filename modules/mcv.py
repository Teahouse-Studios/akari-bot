import aiohttp


async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")


async def main():
    try:
        data = await get_data('http://launchermeta.mojang.com/mc/game/version_manifest.json', "json")
        message1 = f"最新版：{data['latest']['release']}，最新快照：{data['latest']['snapshot']}"
    except (ConnectionError, OSError):  # Probably...
        message1 = "获取manifest.json失败。"
    try:
        mojira = await get_data('https://bugs.mojang.com/rest/api/2/project/10400/versions', 'json')
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


command = {'mcv': 'mcv'}
