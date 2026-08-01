# ----------------------- 导入 -----------------------
from base64 import b64decode, b64encode
from datetime import datetime, timezone
from hashlib import md5
from json import dumps
from typing import Optional, Union
from urllib.parse import urlencode

from httpx import AsyncClient, Response

from .ActionLib import DEFAULT_TIMEOUT, checkSessionToken
from .Structure import Reader, Writer, summary
from .logger import logger


# ---------------------- 定义 ----------------------


def getSaveModifiedAt(record: dict) -> datetime:
    """取存档记录的修改时间，用于在多条记录中挑出最新的一条

    优先使用 modifiedAt.iso，缺失时回退到 updatedAt。两者都取不到或格式无法解析时
    返回可表示的最早时间，使该记录排在最后。

    参数:
        record (dict): 存档记录原始数据

    返回:
        (datetime): 记录的修改时间
    """
    modified = record.get("modifiedAt")
    iso = modified.get("iso") if isinstance(modified, dict) else None

    if not iso:
        iso = record.get("updatedAt")

    if isinstance(iso, str):
        try:
            # LeanCloud 返回的是以 Z 结尾的 UTC 时间
            return datetime.fromisoformat(iso.replace("Z", "+00:00"))

        except ValueError:
            logger.warning(f"无法解析存档记录的修改时间：{iso}")

    return datetime.min.replace(tzinfo=timezone.utc)


class PigeonRequest:
    def __init__(
        self,
        sessionToken: Optional[str] = None,
        isInternational: bool = False,
        client: Optional[AsyncClient] = None,
        headers: Optional[dict] = None,
    ):
        if headers:
            self.headers = headers
        else:
            self.headers = {
                "X-LC-Id": "rAK3FfdieFob2Nn8Am" if not isInternational else "kviehleldgxsagpozb",
                "X-LC-Key": "Qr9AEqtuoSVS3zeD6iVbM4ZC0AtkJcQ89tywVyi0"
                if not isInternational
                else "tG9CTm0LDD736k9HMM9lBZrbeBGRmUkjSfNLDNib",
                "User-Agent": "LeanCloud-CSharp-SDK/1.0.3",
                "Accept": "application/json",
            }

            # httpx 不接受值为 None 的请求头，而 requests 会自动跳过，
            # 因此仅在 sessionToken 存在时才写入该头
            if sessionToken is not None:
                self.headers["X-LC-Session"] = sessionToken

        if client:
            # 仅加固 follow_redirects：这是本库能正常工作的前提——存档下载走 CDN
            # 直链，遇到 302 时若不跟随，request() 中的 raise_for_status() 会把
            # 重定向当错误抛出。timeout 不在此列，调用方显式设置的超时属于调用方
            client.follow_redirects = True
            self.client = client
        else:
            # httpx 默认不跟随重定向，requests 默认跟随。存档下载走 CDN 直链，
            # 可能存在重定向，因此显式开启
            self.client = AsyncClient(
                follow_redirects=True,
                timeout=DEFAULT_TIMEOUT,
            )

    async def request(self, method: str, url: str, headers: Optional[dict] = None, **kwargs) -> Response:
        method = method.upper()

        if headers is None:
            headers = self.headers

        resp = await self.client.request(method, url, headers=headers, **kwargs)

        logger.debug(f"请求方法：{method}")
        logger.debug(f"请求 URL：{url}")
        logger.debug(f"请求头：{resp.request.headers}")
        logger.debug(f"状态码：{resp.status_code}")

        # httpx 的 Request.content 恒为 bytes，无请求体时为 b""
        body = resp.request.content
        if not body:
            logger.debug("请求数据：无")
        else:
            try:
                logger.debug(f"请求数据：{body.decode()}")
            except UnicodeDecodeError:
                logger.debug(f"请求数据：{len(body)} 字节")

        if not resp.content:
            logger.debug("返回数据：无")
        else:
            try:
                logger.debug(f"返回数据：{resp.content.decode()}")
            except UnicodeDecodeError:
                logger.debug(f"返回数据：{len(resp.content)} 字节")

        resp.raise_for_status()

        return resp

    async def get(self, url: str, headers: Optional[dict] = None) -> Response:
        return await self.request("GET", url, headers)

    async def post(
        self,
        url: str,
        content: Optional[Union[str, bytes]] = None,
        headers: Optional[dict] = None,
    ) -> Response:
        return await self.request("POST", url, headers, content=content)

    async def put(
        self,
        url: str,
        content: Optional[Union[str, bytes]] = None,
        headers: Optional[dict] = None,
    ) -> Response:
        return await self.request("PUT", url, headers, content=content)

    async def delete(self, url: str, headers: Optional[dict] = None) -> Response:
        return await self.request("DELETE", url, headers)

    async def aclose(self):
        await self.client.aclose()


class PhigrosCloud:
    def __init__(
        self,
        sessionToken: str,
        isInternational: bool = False,
        client: Optional[AsyncClient] = None,
    ):
        # 校验失败时 checkSessionToken 会直接抛出异常，因此无需再用条件分支包裹。
        # 原实现将后续赋值全部放在 if 内，一旦校验返回假值，实例将缺失全部属性
        checkSessionToken(sessionToken)

        # 仅当客户端由本类创建时才负责关闭，外部传入的客户端由调用方管理
        self.create_client = client is None
        self.request = PigeonRequest(sessionToken, isInternational, client)
        # 客户端只保留一个来源。原实现中本类与 PigeonRequest 各自创建了一个 Session，
        # 本类持有的那个从未被使用，而 PigeonRequest 持有的那个从未被关闭
        self.client = self.request.client

        if isInternational:
            self.baseUrl = "https://kviehlel.cloud.ap-sg.tapapis.com/1.1/"
        else:
            self.baseUrl = "https://rak3ffdi.cloud.tds1.tapapis.cn/1.1/"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.create_client:
            await self.aclose()

    async def aclose(self):
        await self.client.aclose()

    async def getNickname(self) -> str:
        """获取玩家昵称

        返回:
            (str): 玩家昵称
        """
        logger.debug("调用函数：getNickname()")

        return_data = (await self.request.get(self.baseUrl + "users/me")).json()["nickname"]

        logger.debug(f'函数 "getNickname()" 返回：{return_data}')
        return return_data

    async def getSaveInfo(self) -> dict:
        """获取当前 sessionToken 名下最新的一条存档记录

        _GameSave 中存放的是全部玩家的存档记录，因此查询时必须以 user 指针过滤，
        否则服务端会返回该 class 中的任意一条记录，取到他人的存档。

        同一账号也可能存在多条记录，故取回全部后按 modifiedAt 降序排序，
        只使用最新的一条。

        返回:
            (dict): 存档记录的原始数据

        异常:
            ValueError: 当前账号名下没有可用的存档记录，或服务端返回了他人的记录
        """
        logger.debug("调用函数：getSaveInfo()")

        userObjectId = (await self.request.get(self.baseUrl + "users/me")).json()["objectId"]

        # where 条件必须存在，这是本函数正确性的前提
        query = urlencode(
            {
                "skip": "0",
                "limit": "100",
                "where": dumps(
                    {
                        "user": {
                            "__type": "Pointer",
                            "className": "_User",
                            "objectId": userObjectId,
                        }
                    },
                    separators=(",", ":"),
                ),
            }
        )

        results = (await self.request.get(self.baseUrl + f"classes/_GameSave?{query}")).json()["results"]

        # 不含 gameFile 的记录没有存档文件，无法使用
        saves = [record for record in results if record.get("gameFile")]

        if not saves:
            logger.error("当前账号名下没有包含存档文件的记录。")
            raise ValueError("当前账号名下没有可用的存档记录，请先在游戏内将存档同步至云端。")

        saves.sort(key=getSaveModifiedAt, reverse=True)

        if len(saves) > 1:
            logger.debug(f"账号名下有 {len(saves)} 条存档记录，使用最新的一条。")

        return_data = saves[0]

        # 二次校验。即使 where 条件因故失效，也不允许把他人的存档交给调用方
        owner = (return_data.get("user") or {}).get("objectId")
        if owner != userObjectId:
            logger.error(f"服务端返回的存档不属于当前账号，归属：{owner}")
            raise ValueError(f"服务端返回的存档不属于当前账号，归属：{owner}，当前账号：{userObjectId}")

        logger.debug(f'函数 "getSaveInfo()" 返回存档：{return_data.get("objectId")}')
        return return_data

    async def getSummary(self) -> dict:
        """获取玩家 summary

        返回:
            (dict): 玩家 summary 数据
        """
        logger.debug("调用函数：getSummary()")

        result = await self.getSaveInfo()
        summary_data = b64decode(result["summary"])

        summary_dict = Reader(summary_data).parseStructure(summary)

        return_data = {
            "checksum": result["gameFile"]["metaData"]["_checksum"],  # 存档的 md5 校验值
            "updateAt": result["updatedAt"],  # 存档更新时间
            "url": result["gameFile"]["url"],  # 存档直链
            "saveVersion": summary_dict["saveVersion"],  # 存档版本
            "challenge": summary_dict["challenge"],  # 课题分
            "rks": summary_dict["rks"],
            "gameVersion": summary_dict["gameVersion"],  # 游戏版本
            "avatar": summary_dict["avatar"],  # 头像
            "EZ": summary_dict["EZ"],  # EZ 难度的评级情况
            "HD": summary_dict["HD"],  # HD 难度的评级情况
            "IN": summary_dict["IN"],  # IN 难度的评级情况
            "AT": summary_dict["AT"],  # AT 难度的评级情况
        }

        logger.debug(f'函数 "getSummary()" 返回：{return_data}')
        return return_data

    async def getSave(self, url: Optional[str] = None, checksum: Optional[str] = None) -> bytes:
        """获取存档数据，返回的是压缩包数据

        参数:
            url (str | None): 存档的 URL。留空则自动获取当前 token 的数据
            checksum (str | None): 存档的 md5 校验值。留空则自动获取当前 token 的数据

        返回:
            (bytes): 存档压缩包数据
        """
        logger.debug("调用函数：getSave()")

        # 局部变量不使用 summary 作为名称，避免遮蔽模块级导入的同名结构类
        if url is None:
            summary_info = await self.getSummary()
            url = summary_info["url"]
            if checksum is None:
                checksum = summary_info["checksum"]

        elif checksum is None:
            checksum = (await self.getSummary())["checksum"]

        save_data = (await self.request.get(url)).content
        if len(save_data) <= 30:
            logger.error(f"获取到的云存档大小不足 30 字节，当前大小：{len(save_data)}")
            logger.error("云存档可能已丢失，请重新将本地存档同步至云端。")
            raise ValueError(f"获取到的云存档大小不足 30 字节，当前大小：{len(save_data)}")

        save_md5 = md5(usedforsecurity=False)
        save_md5.update(save_data)
        actual_checksum = save_md5.hexdigest()
        if checksum != actual_checksum:
            logger.error("存档校验未通过。")
            logger.error("这可能是由不正确地上传存档导致的。")
            raise ValueError(f"存档校验未通过。本地存档 md5：{actual_checksum}，云端存档 md5：{checksum}")

        logger.debug(f'函数 "getSave()" 返回：{len(save_data)} 字节')
        return save_data

    async def refreshSessionToken(self) -> str:
        """刷新 sessionToken

        刷新是即时的，原先的 sessionToken 会立即失效，新的 sessionToken 立即生效。

        返回:
            (str): 新的 sessionToken
        """
        logger.debug("调用函数：refreshSessionToken()")

        objectId = (await self.request.get(self.baseUrl + "users/me")).json()["objectId"]

        new_sessionToken = (await self.request.put(self.baseUrl + f"users/{objectId}/refreshSessionToken")).json()[1][
            "sessionToken"
        ]

        logger.debug(f'函数 "refreshSessionToken()" 返回：{new_sessionToken}')
        return new_sessionToken

    async def uploadNickname(self, name: str):
        """更新玩家昵称

        参数:
            name (str): 要更改的昵称

        返回:
            (None): 无
        """
        logger.debug("调用函数：uploadNickname()")

        response = (await self.request.get(self.baseUrl + "users/me")).json()
        userObjectId = response["objectId"]
        logger.debug(f"userObjectId：{userObjectId}")

        await self.request.put(
            url=self.baseUrl + f"users/{userObjectId}",
            content=dumps({"nickname": name}),
            headers={
                **self.request.headers,
                "Content-Type": "application/json",
            },
        )

        logger.debug('函数 "uploadNickname()" 无返回')

    async def uploadSummary(self, summary_dict: dict):
        """上传 summary

        上传后的 summary 仅供查看，覆盖原有数据后不可恢复，且不影响游戏内的实际数据。

        参数:
            summary_dict (dict): 要上传的 summary

        返回:
            (None): 无
        """
        logger.debug("调用函数：uploadSummary()")

        # 序列化逻辑与 getSummary() 的反序列化保持一致
        _summary: str = b64encode(Writer().buildStructure(summary, summary_dict)).decode()

        save_info = await self.getSaveInfo()

        objectId = save_info["objectId"]
        userObjectId = save_info["user"]["objectId"]
        checksum = save_info["gameFile"]["metaData"]["_checksum"]
        saveSize = save_info["gameFile"]["metaData"]["size"]
        fileObjectId = save_info["gameFile"]["objectId"]

        logger.debug(f"objectId：{objectId}")
        logger.debug(f"userObjectId：{userObjectId}")
        logger.debug(f"checksum：{checksum}")
        logger.debug(f"saveSize：{saveSize}")

        logger.debug(f"现 summary：{save_info['summary']}")
        logger.debug(f"新 summary：{_summary}")

        await self.request.put(
            url=self.baseUrl + f"classes/_GameSave/{objectId}",
            content=dumps(
                {
                    "summary": _summary,
                    "modifiedAt": {
                        "__type": "Date",
                        "iso": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z",
                    },
                    "gameFile": {
                        "__type": "Pointer",
                        "className": "_File",
                        "objectId": fileObjectId,
                    },
                    "ACL": {userObjectId: {"read": True, "write": True}},
                    "user": {
                        "__type": "Pointer",
                        "className": "_User",
                        "objectId": userObjectId,
                    },
                }
            ),
            headers={
                **self.request.headers,
                "Content-Type": "application/json",
            },
        )

        logger.debug('函数 "uploadSummary()" 无返回')
