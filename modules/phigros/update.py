import csv
import csv
import os
import re
import shutil
import string
import traceback

import ujson as json

from core.utils.cache import random_cache_path
from core.utils.http import get_url, download_to_cache

assets_path = os.path.abspath('./assets/phigros')
cache_path = os.path.abspath('./cache')
csv_path = os.path.abspath('./services/phigros/difficulty_update.csv')
json_url = 'https://raw.githubusercontent.com/ssmzhn/Phigros/main/Phigros.json'


def remove_punctuations(text):
    punctuations = '！？｡＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～、。〃〈〉《》「」『』【】〒〔〕〖〗〘〙〚〛〜・♫☆×♪↑↓ '
    text = ''.join([char for char in text if char not in string.punctuation and char not in punctuations])
    text = re.sub(' +', ' ', text)
    return text


async def update_difficulty_csv():
    update_json = json.loads(await get_url(json_url, 200))

    gen_csv_path = random_cache_path() + '.csv'
    with open(gen_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        rows = []
        for s in update_json:
            if update_json[s]['song'] == 'Introduction':
                continue
            lst = []
            lst.append(
                remove_punctuations(
                    update_json[s]['song']) +
                '.' +
                remove_punctuations(
                    update_json[s]['composer']))
            for c in update_json[s]['chart']:
                lst.append(update_json[s]['chart'][c]['difficulty'])
            rows.append(lst)
        writer.writerows(rows)
        f.close()
    shutil.copy(gen_csv_path, csv_path)
    return True


async def update_assets():
    illustration_path = os.path.join(assets_path, 'illustration')
    if not os.path.exists(illustration_path):
        os.makedirs(illustration_path, exist_ok=True)
    illustration_list = os.listdir(illustration_path)
    update_json = json.loads(await get_url(json_url, 200))
    for song in update_json:
        song_name = remove_punctuations(update_json[song]['song'])
        if song_name not in illustration_list:
            try:
                download_file = await download_to_cache(update_json[song]['illustration'])
                if download_file:
                    shutil.move(download_file, os.path.join(illustration_path, song_name))
            except Exception:
                traceback.print_exc()
    another_assets_url = 'https://github.com/7aGiven/PhigrosLibrary/archive/refs/heads/master.zip'
    download_file = await download_to_cache(another_assets_url)
    if download_file:
        ca = random_cache_path()
        shutil.unpack_archive(download_file, ca)
        shutil.copytree(
            os.path.join(
                ca,
                'PhigrosLibrary-master',
                'illustration'),
            illustration_path,
            dirs_exist_ok=True)
        os.remove(download_file)
    return True
