import re
from html import escape
from typing import Any, List, Optional, Union

from PIL import Image as PILImage
from tabulate import tabulate

from core.builtins.session.info import SessionInfo
from core.joke import shuffle_joke as joke
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.image import cb64imglst
from core.web_render import web_render, LegacyScreenshotOptions


class ImageTable:
    """
    图片表格。

    :param data: 表格内容，每行的列数需与表头数量相符。
    :param headers: 表格表头。
    """

    def __init__(self, data: List[List[Any]], headers: List[str], session_info: Optional["SessionInfo"] = None):
        if not all(len(row) == len(headers) for row in data):
            raise ValueError("The number of columns of data must match the number of table headers.")

        if session_info:
            localized_data = []
            for row in data:
                translated_row = [
                    session_info.locale.t_str(cell) if isinstance(cell, str) else cell
                    for cell in row
                ]
                localized_data.append(translated_row)
            self.data = localized_data
            self.headers = [session_info.locale.t_str(h) for h in headers]
        else:
            self.data = data
            self.headers = headers


async def image_table_render(
    table: Union[ImageTable, List[ImageTable]],
    save_source: bool = True,
) -> Union[List[PILImage.Image], None]:
    """
    使用WebRender渲染图片表格。

    :param table: 要渲染的表格。
    :param save_source: 是否保存源文件。
    :return: 图片的PIL对象。
    """
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
        if save_source:
            fname = f"{random_cache_path()}.html"
            with open(fname, "w", encoding="utf-8") as fi:
                fi.write(tblst + css)
        image_list = await web_render.legacy_screenshot(
            LegacyScreenshotOptions(content=tblst + css, width=w, mw=False, counttime=False))
    except Exception:
        Logger.exception()
        return None
    if not image_list:
        Logger.error("Image table render failed, no image returned.")
        return None
    return cb64imglst(image_list)


__all__ = ["ImageTable", "image_table_render"]
