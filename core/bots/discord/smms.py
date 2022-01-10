from config import Config
from core.utils import post_url, get_url

import ujson as json
from datetime import datetime, timedelta


class SMMS:
    status = False
    token = None
    endpoint = 'https://sm.ms/api/v2/'

    def __init__(self):
        token = Config('smms_token')
        if token:
            self.status = True
            self.token = token

    async def upload(self, file):
        if self.status:
            url = self.endpoint + 'upload'
            header = {'Authorization': self.token}
            with open(file, 'rb') as f:
                data = {'smfile': f.read()}
                post = await post_url(url, data, header)
                print(post)
                post_result = json.loads(post)
                if post_result['success']:
                    rturl = post_result['data']['url']
                else:
                    if 'images' in post_result:
                        rturl = post_result['images']
                    else:
                        return False
                history_url = self.endpoint + 'upload_history'
                history_data = {'page': 1}
                history_header = {'Authorization': self.token, 'Content-Type': 'multipart/form-data'}
                history = await get_url(history_url, headers=history_header)
                print(history)
                history = json.loads(history)
                for i in history['data']:
                    o = datetime.fromtimestamp(i['created_at'])
                    n = datetime.now()
                    if n - o > timedelta(days=1):
                        del_url = i['delete']
                        await get_url(del_url)
                return rturl

