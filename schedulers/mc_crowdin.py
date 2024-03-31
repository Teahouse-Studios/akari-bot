import random
import re
import traceback
from datetime import datetime, timezone
from database.local import CrowdinActivityRecords

from config import Config
from core.builtins import Plain, Embed, EmbedField
from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import Scheduler, IntervalTrigger
from core.utils.html2text import html2text
from core.utils.http import get_url

first = True

filter_words = ['Mojang']
base_url = 'https://crowdin.com/'


@Scheduler.scheduled_job(IntervalTrigger(seconds=60 if not Config('slower_schedule') else 180))
async def check_crowdin():
    global first
    randstr = 'abcdefghijklmnopqrstuvwxyz'
    random_string = ''.join(random.sample(randstr, 16))
    headers = {'cookie': f'csrf_token={random_string}', 'x-csrf-token': random_string}
    url = f"https://crowdin.com/backend/project_actions/activity_stream?date_from=&date_to=&user_id=0&project_id=3579&language_id=0&type=0&translation_id=0&after_build=0&before_build=0&request=1"
    try:
        get_json: dict = await get_url(url, 200, attempt=1, headers=headers,
                                       fmt='json')
        if get_json:
            if 'error' in get_json:
                raise Exception(get_json['msg'])
            for act in get_json['activity']:
                m = html2text(act["message"], baseurl=base_url).strip()
                # Replace newline characters in urls
                match = re.findall(r'\[.*?]\((.*?)\)', m, re.M | re.S)
                for i in match:
                    m = m.replace(i, i.replace('\n', ''))
                if not any(x in m for x in filter_words):
                    continue
                if act['count'] == 1:
                    identify = f'{act["user_id"]}{str(act['timestamp'])}{m}'
                    if not first and not CrowdinActivityRecords.check(identify):
                        await JobQueue.trigger_hook_all('mc_crowdin', message=[Embed(title='New Crowdin Updates', description=m).to_dict()])
                else:
                    detail_url = f"https://crowdin.com/backend/project_actions/activity_stream_details?request_type=project&type={act["type"]}&timestamp={act["timestamp"]}&offset=0&user_id={act["user_id"]}&project_id={act["project_id"]}&language_id=0&after_build=0&before_build=0"
                    get_detail_json: dict = await get_url(detail_url, 200, attempt=1, headers=headers,
                                                          fmt='json')
                    if get_detail_json:
                        for detail_num in get_detail_json['activity']:
                            identify_ = {}
                            if not isinstance(get_detail_json['activity'][detail_num], list):
                                continue
                            for detail in get_detail_json['activity'][detail_num]:
                                content = detail["content"]
                                if 'icon-thumbs-up' in content:
                                    content = '👍'
                                elif 'icon-thumbs-down' in content:
                                    content = '👎'
                                else:
                                    content = html2text(content, baseurl=base_url).strip()
                                    match = re.findall(r'\[.*?]\((.*?)\)', content, re.M | re.S)
                                    for i in match:
                                        content = content.replace(i, i.replace('\n', ''))
                                identify = {detail['title']: content}
                                identify_.update(identify)
                            identify = f'{act["user_id"]}{str(act['timestamp'])}{m}{
                                "\n".join(f'{i}: {identify_[i]}' for i in identify_)}'

                            if not first and not CrowdinActivityRecords.check(identify):
                                await JobQueue.trigger_hook_all('mc_crowdin', message=[Embed(title='New Crowdin Updates', description=m, color=0x00ff00, fields=[EmbedField(name=k, value=v, inline=True) for k, v in identify_.items()]).to_dict()])
    except Exception:
        if Config('debug'):
            Logger.error(traceback.format_exc())
    if first:
        first = False
