import math
import csv
import os
import re
import string
import shutil

import ujson as json

from PIL import Image, ImageFilter, ImageEnhance, ImageDraw

from core.logger import Logger
from core.utils.http import get_url
from core.utils.cache import random_cache_path


assets_path = os.path.abspath('./assets')
cache_path = os.path.abspath('./cache')
csv_path = os.path.abspath('./services/phigros/difficulty.csv')
json_url = 'https://raw.githubusercontent.com/ssmzhn/Phigros/main/Phigros.json'


def remove_punctuations(text):
    # 中文和日语标点符号
    punctuations = '！？｡＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～、。〃〈〉《》「」『』【】〒〔〕〖〗〘〙〚〛〜・♫☆×♪↑↓ '

    # 移除所有标点符号
    text = ''.join([char for char in text if char not in string.punctuation and char not in punctuations])

    # 移除多余的空格
    text = re.sub(' +', ' ', text)

    return text


async def update_difficulty_csv():
    update_json = json.loads(await get_url(json_url, 200))

    gen_csv_path = random_cache_path() + '.csv'
    with open(gen_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        rows = []
        for s in update_json:
            lst = []
            lst.append(remove_punctuations(update_json[s]['song']) + '.' + remove_punctuations(update_json[s]['composer']))
            for c in update_json[s]['chart']:
                lst.append(update_json[s]['chart'][c]['difficulty'])
            rows.append(lst)
        writer.writerows(rows)
        f.close()
    shutil.copy(gen_csv_path, csv_path)
    


