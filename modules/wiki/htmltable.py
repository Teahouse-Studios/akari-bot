import os
import traceback
import uuid

import ujson as json

import aiohttp
from tabulate import tabulate

from config import Config

infobox_render = Config('infobox_render')


async def image_table_render(table, headers=None):
    if not infobox_render:
        return False
    try:
        convert_to_html = tabulate(table, headers, tablefmt="html")
        css = """
        <style>table {
            border-collapse: collapse;
          }
          
          table, th, td {
            border: 1px solid black;
          }
          th, td {
          padding: 15px;
          text-align: left;
        }
          tr:nth-child(even) {background-color: #f2f2f2;}</style>"""
        html = {'content': convert_to_html + css}
        picname = os.path.abspath(f'./cache/{str(uuid.uuid4())}.jpg')
        if os.path.exists(picname):
            os.remove(picname)
        async with aiohttp.ClientSession() as session:
            async with session.post(infobox_render, headers={
                'Content-Type': 'application/json',
            }, data=json.dumps(html)) as resp:
                with open(picname, 'wb+') as jpg:
                    jpg.write(await resp.read())
        return picname
    except Exception:
        traceback.print_exc()
        return False
