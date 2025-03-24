import base64
import re
import traceback
from html import escape
from io import BytesIO
from typing import Any, List, Union

import orjson as json
from PIL import Image as PILImage
from tabulate import tabulate

from core.constants.info import Info
from core.joke import shuffle_joke as joke
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.http import download
from core.utils.web_render import webrender


class ImageTable:
    """
    图片表格。

    :param data: 表格内容，表格行数需与表格标头的数量相符。
    :param headers: 表格表头。
    """

    def __init__(self, data: List[List[Any]], headers: List[str]):
        self.data = data
        self.headers = headers


async def image_table_render(
    table: Union[ImageTable, List[ImageTable]],
    save_source: bool = True,
    use_local: bool = True,
) -> Union[List[PILImage.Image], bool]:
    """
    使用WebRender渲染图片表格。

    :param table: 要渲染的表格。
    :param save_source: 是否保存源文件。
    :param use_local: 是否使用本地WebRender渲染。
    :return: 图片的PIL对象。
    """
    if not Info.web_render_status:
        return False
    if not Info.web_render_local_status:
        use_local = False
    pic = False

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
                    c = joke(c)
                    cs.append(re.sub(r"\n", "<br>", escape(c)))
                d.append(cs)
            headers = [joke(header) for header in tbl.headers]
            w = len(headers) * 500
            if w > max_width:
                max_width = w
            tblst.append(
                re.sub(
                    r"<table>|</table>", "", tabulate(d, headers, tablefmt="unsafehtml")
                )
            )
        tblst = "<table>" + "\n".join(tblst) + "</table>"
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
        html = {"content": tblst + css, "width": w, "mw": False}
        if save_source:
            fname = f"{random_cache_path()}.html"
            with open(fname, "w", encoding="utf-8") as fi:
                fi.write(tblst + css)

        try:
            pic = await download(
                webrender(use_local=use_local),
                method="POST",
                post_data=json.dumps(html),
                request_private_ip=True,
                headers={
                    "Content-Type": "application/json",
                },
            )
        except Exception:
            if use_local:
                try:
                    pic = await download(
                        webrender(use_local=False),
                        method="POST",
                        post_data=json.dumps(html),
                        request_private_ip=True,
                        headers={
                            "Content-Type": "application/json",
                        },
                    )
                except Exception:
                    Logger.error("Generation failed.")
                    return False
            else:
                Logger.error("Generation failed.")
                return False
    except Exception:
        Logger.error(traceback.format_exc())
        return False
    with open(pic, "rb") as read:
        load_img = json.loads(read.read())
    img_lst = []
    for x in load_img:
        b = base64.b64decode(x)
        bio = BytesIO(b)
        bimg = PILImage.open(bio)
        img_lst.append(bimg)
    return img_lst


__all__ = ["ImageTable", "image_table_render"]
