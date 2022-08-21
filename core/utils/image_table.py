import os
import re
import traceback
from html import escape
from typing import List, Union

import aiohttp
import ujson as json
from tabulate import tabulate

from config import Config
from core.logger import Logger
from .cache import random_cache_path

web_render = Config('web_render_local')


class ImageTable:
    def __init__(self, data, headers):
        self.data = data
        self.headers = headers


async def image_table_render(table: Union[ImageTable, List[ImageTable]], save_source=False):
    if not web_render:
        return False
    try:
        tblst = []
        if isinstance(table, ImageTable):
            table = [table]
        max_width = 500
        for tbl in table:
            d = []
            for row in tbl.data:
                cs = []
                for c in row:
                    cs.append(re.sub(r'\n', '<br>', escape(c)))
                d.append(cs)
            w = len(tbl.headers) * 500
            if w > max_width:
                max_width = w
            tblst.append(re.sub(r'<table>|</table>', '', tabulate(d, tbl.headers, tablefmt='unsafehtml')))
        tblst = '<table>' + '\n'.join(tblst) + '</table>'
        css = """
        <style>table {
                border-collapse: collapse;
              }
              table, th, td {
                border: 1px solid rgba(0,0,0,0.05);
                font-size: 0.8125rem;
                font-weight: 500;
              }
              th, td {
              padding: 15px;
              text-align: left;
            }</style>"""
        html = {'content': tblst + css, 'width': w}
        if save_source:
            fname = random_cache_path() + '.html'
            with open(fname, 'w') as fi:
                fi.write(tblst + css)
        picname = random_cache_path() + '.jpg'
        if os.path.exists(picname):
            os.remove(picname)
        async with aiohttp.ClientSession() as session:
            async with session.post(web_render, headers={
                'Content-Type': 'application/json',
            }, data=json.dumps(html)) as resp:
                with open(picname, 'wb+') as jpg:
                    jpg.write(await resp.read())
        return picname
    except Exception:
        Logger.error(traceback.format_exc())
        return False


__all__ = ['ImageTable', 'image_table_render', 'web_render']
