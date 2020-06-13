import requests
import json
import asyncio

async def mcv():
    url = 'http://launchermeta.mojang.com/mc/game/version_manifest.json'
    try:
        version_manifest = requests.get(url)
        file = json.loads(version_manifest.text)
        return("最新版：" + file['latest']['release'] + "，最新快照：" + file['latest']['snapshot'])
    except Exception:
        return("发生错误：土豆熟了。")