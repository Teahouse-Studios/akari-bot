# ----------------------- 导入 -----------------------
from copy import deepcopy
from io import BytesIO
from re import match
from typing import Any, Dict, List, Optional
from zipfile import ZipFile, ZIP_DEFLATED

from .AES import decrypt, encrypt
from .Structure import headGetStructure, getFileHead, Reader, Writer
from .logger import logger


# ---------------------- 定义 ----------------------

DEFAULT_TIMEOUT = 30.0
"""默认请求超时时间，单位为秒。

httpx 的默认超时为 5 秒，而 requests 默认不设超时。文件下载可能超过 5 秒，
因此显式放宽，以对齐替换前的行为。
"""


def checkSessionToken(sessionToken: str, _raise: bool = True) -> bool:
    """检查 sessionToken 格式是否合法

    参数:
        sessionToken (str): 玩家的 sessionToken
        _raise (bool): 是否主动引发错误，若为 False，则会在检测到不合法时返回 False。默认为 True

    返回:
        (bool): sessionToken 是否合法
    """
    # 判断 sessionToken 是否为空
    if sessionToken == "" or sessionToken is None:
        if _raise:
            raise ValueError("sessionToken 为空。")

        else:
            return False

    # 判断 sessionToken 的长度是否为 25 位
    elif len(sessionToken) != 25:
        if _raise:
            raise ValueError(f"sessionToken 长度错误，应为 25 位，而不是 {len(sessionToken)} 位：{sessionToken}")

        else:
            return False

    # 正则匹配判断 sessionToken 是否符合要求
    elif not match(r"^[0-9a-z]{25}$", sessionToken):
        if _raise:
            raise ValueError(f"sessionToken 不合法，应只有数字与小写字母：{sessionToken}")

        else:
            return False

    # 检查全部通过则是合法 sessionToken
    else:
        logger.debug(f"sessionToken 正确：{sessionToken}")
        return True


def unzipFile(zip_data: bytes, file_name: Optional[str] = None) -> Dict[str, bytes]:
    """读取压缩包并解压文件数据

    参数:
        zip_data (bytes): 压缩包数据
        file_name (str | None): 文件名，用于解压单个文件，为 None 时解压所有文件，默认为 None

    返回:
        (dict[str, bytes]): 压缩包文件数据
    """
    files_dict = {}
    # 打开压缩包 (存档本身是一个 zip 压缩包)
    with ZipFile(BytesIO(zip_data)) as zip_file:
        # 如果指定了文件名，那么将尝试解压单个文件
        if file_name is not None:
            # 获取压缩包文件名列表，用来判断指定的文件名是否存在
            file_name_list = [i.filename for i in zip_file.filelist]
            if file_name in file_name_list:
                # 如果文件存在于压缩包中
                with zip_file.open(file_name) as file:
                    files_dict[file_name] = file.read()

            else:
                # 如果文件不存在于压缩包中
                raise FileNotFoundError(f"无法在压缩包中找到文件：{file_name}")

        # 默认解压全部文件
        else:
            # 遍历压缩包所有文件
            for file in zip_file.filelist:
                # 获取压缩包文件名
                filename = file.filename
                logger.debug(f'解压 "{filename}" 文件')
                with zip_file.open(filename) as file:
                    files_dict[filename] = file.read()  # 读取文件数据

    logger.debug("解压完毕。")
    return files_dict


def zipSave(files_dict: Dict[str, Any]) -> bytes:
    """创建压缩包

    参数:
        files_dict (dict[str, Any]): 压缩包文件数据

    返回:
        (bytes): 压缩包数据
    """
    with BytesIO() as file:
        with ZipFile(file, "w", compression=ZIP_DEFLATED) as zip_file:
            for filename, filedata in files_dict.items():
                logger.debug(f'压缩 "{filename}" 文件')
                zip_file.writestr(filename, filedata)

        logger.debug("压缩完毕。")
        return file.getvalue()


def addDifficulty(record_data: dict, difficulty: Dict[str, list]) -> Dict[str, dict]:
    """为所有成绩添加谱面定数信息

    参数:
        record_data (dict): gameRecord/存档 反序列化数据
        difficulty (dict[str, list]): 歌曲谱面定数数据

    返回:
        (dict[str, dict]): 添加谱面定数信息后的 gameRecord/存档 反序列化数据
    """
    # 各难度的映射字典
    diff_list = {"EZ": 0, "HD": 1, "IN": 2, "AT": 3, "Legacy": 4}

    # 为单独传入 gameRecord 反序列化数据和传入存档反序列化数据两种情况提供支持
    if record_data.get("gameRecord") is not None and isinstance(record_data["gameRecord"], dict):
        gameRecord = record_data["gameRecord"]

    else:
        gameRecord = record_data

    # 遍历所有歌曲成绩
    for songName, song in gameRecord.items():
        # 遍历单个歌曲中所有难度的成绩
        for diff in song.keys():
            try:
                # 尝试从定数数据获取该歌曲难度的谱面定数
                record_diff: float = difficulty[songName][diff_list[diff]]

            except KeyError:
                # 如果发生 KeyError，那么就是因为歌曲名不存在于定数数据
                record_diff: float = 0
                logger.warning(f'歌曲 "{songName}" 的 {diff} 定数不存在。')

            except IndexError:
                # 如果出现 IndexError，那么就是因为难度索引超出了范围
                record_diff: float = 0
                logger.warning(f'歌曲 "{songName}" 可能存在旧谱记录。')

            gameRecord[songName][diff].update({"difficulty": record_diff})

    return record_data


def countRks(record_data: dict, difficulty: Dict[str, list], onlyCountRks: bool = False) -> Dict[str, dict]:
    """为反序列化后的 gameRecord 中的每条成绩添加难度定数并计算等效 rks

    参数:
        record_data (dict): gameRecord/存档 反序列化数据
        difficulty (dict): 歌曲定数数据
        onlyCountRks (bool): 是否仅计算 rks，默认为 False，如果为 True 则只会计算等效 rks 而不添加谱面定数

    返回:
        (dict): 处理后的 gameRecord/存档 反序列化数据
    """
    if not onlyCountRks:
        record_data = addDifficulty(record_data, difficulty)

    if record_data.get("gameRecord") is not None and isinstance(record_data["gameRecord"], dict):
        gameRecord = record_data["gameRecord"]

    else:
        gameRecord = record_data

    for songName, song in gameRecord.items():
        for diff in song.keys():
            try:
                record_diff: float = gameRecord[songName][diff]["difficulty"]
                acc = gameRecord[songName][diff]["acc"]
                if acc > 70:
                    rks = (((acc - 55) / 45) ** 2) * record_diff

                else:
                    rks = 0.0

            except KeyError:
                rks: float = 0
                logger.warning(f'歌曲 "{songName}" 的 {diff} 定数不存在。')

            gameRecord[songName][diff].update({"rks": rks})

    return record_data


def getBest(record_data: dict, phi_count: int = 3, best_count: int = 27) -> Dict[str, List[dict]]:
    """获取 best 成绩

    参数:
        record_data (dict): gameRecord/存档 反序列化数据
        phi_count (int): 要返回 phi 榜的前几条成绩，默认为 3
        best_count (int): 要返回 best 榜的前几条成绩，默认为 27

    返回:
        (dict[str, list[dict]]): best 列表
    """
    all_record = []  # 存储所有打歌成绩记录

    if record_data.get("gameRecord") is not None and isinstance(record_data["gameRecord"], dict):
        gameRecord = record_data["gameRecord"]

    else:
        gameRecord = record_data

    # 深度拷贝打歌成绩数据字典 (防止进行 best 排序等操作影响到原数据)
    record = deepcopy(gameRecord)

    for song in record.items():  # 遍历所有歌曲记录
        for song_record in song[1].items():  # 遍历每首歌的所有难度记录
            song_record[1]["name"] = song[0]  # 取歌名添加进原数据中

            # 将难度等级添加进原数据中
            song_record[1]["level"] = song_record[0]
            all_record.append(song_record[1])  # 添加到全部记录列表中

    # 对全部记录以 rks 为准进行排序
    all_record.sort(key=lambda x: x["rks"], reverse=True)
    try:
        # 从按 rks 排序后的记录中取出 AP (score == 1000000) 成绩
        phi_list = list(filter(lambda x: x["score"] == 1000000, all_record))[:phi_count]

    except ValueError:
        logger.warning("记录中不存在 AP 成绩。")
        phi_list = []

    for p in phi_list:
        all_record.remove(p)

    # 返回 best 列表
    return {"phi": phi_list, "best": all_record[:best_count]}


def getB19(records: dict) -> List[dict]:
    """获取 b19 (现在 Phigros 已不使用 b19 进行计算 rks 了，请使用 `getB30()`)

    参数:
        records (dict): gameRecord/存档 反序列化数据

    返回:
        (list[dict]): b19 列表
    """
    best_dict = getBest(records, 1, 19)
    phi, best = best_dict["phi"], best_dict["best"]

    phi.extend(best)
    return phi  # 返回 b19 (准确来说应该得叫 b20)


def getB30(records: dict):
    """获取 b30

    参数:
        records (dict): gameRecord/存档 反序列化数据

    返回:
        (list[dict]): b30 列表
    """
    best_dict = getBest(records, 3, 27)
    phi, best = best_dict["phi"], best_dict["best"]

    phi.extend(best)
    return phi  # 返回 b30


def decryptSave(save_dict: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """反序列化存档原始数据

    参数:
        save_dict (dict[str, Any]): 存档原始数据

    返回:
        (dict[str, dict]): 存档反序列化数据
    """
    file_head = {}  # 存储文件头数据
    # 获取每个文件的文件头 (起始第一个字节)
    for key, value in save_dict.items():
        file_head[key] = value[0].to_bytes()

    # 根据文件头获取反序列化用的结构类
    structure_list = headGetStructure(file_head)

    for key, value in save_dict.items():
        save_dict[key] = decrypt(value[1:])

        reader = Reader(save_dict[key])
        save_dict[key] = reader.parseStructure(structure_list[key])

    return save_dict


def encryptSave(save_dict: Dict[str, Any]):
    """序列化存档数据

    参数:
        save_dict (dict[str, dict]): 存档反序列化数据

    返回:
        (dict[str, bytes]): 存档序列化数据
    """
    file_head = getFileHead(save_dict)
    structure_list = headGetStructure(file_head)

    for key, value in save_dict.items():
        reader = Writer()
        value = reader.buildStructure(structure_list[key], save_dict[key])

        save_dict[key] = file_head[key] + encrypt(value)

    return save_dict


def parseSaveDict(save_data: bytes):
    """反序列化存档原始数据为存档字典数据

    参数:
        save_data (bytes): 存档原始数据

    返回:
        (dict[str, dict[str, Any]]): 存档反序列化数据
    """
    return decryptSave(unzipFile(save_data))


def buildSaveDict(save_dict: Dict[str, dict]):
    """序列化存档字典数据为存档原始数据

    参数:
        save_dict (dict[str, dict]): 存档反序列化数据

    返回:
        (bytes): 存档原始数据
    """
    return zipSave(encryptSave(save_dict))
