import httpx
import json
async def get_url(url):
    async with httpx.AsyncClient() as client:
        resp = await client.get(url,timeout=600)
        result = resp.text
        return result
async def news():
    try:
        information = json.loads(await get_url('https://api.iyk0.com/60s/'))
    except (ConnectionError, OSError):
        return '新闻API获取失败。'
    if int(information['code']) != 200 or str(information['msg']) != 'Success':
        return '新闻API获取失败。'
    img_url = str(information['imageUrl'])
    return img_url
