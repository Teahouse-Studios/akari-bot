import json
from core.utils import get_url
async def news():
    try:
        information = json.loads(await get_url('https://api.iyk0.com/60s/'))
    except (ConnectionError, OSError):
        return '新闻API获取失败。'
    if int(information['code']) != 200 or str(information['msg']) != 'Success':
        return '新闻API获取失败。'
    img_url = str(information['imageUrl'])
    return img_url
