# ----------------------- 导入 -----------------------
import ast
from struct import unpack, pack
from typing import Any, Dict, Optional, Union

from ..logger import logger

# ---------------------- 定义 ----------------------


class dataTypeAbstract:
    @staticmethod
    def read(data: bytes, pos: int): ...

    @staticmethod
    def write(data: bytearray, value): ...


class Bit:
    @staticmethod
    def read(data: int, index: int) -> int:
        """
        读取一个整数中指定索引的比特位值

        参数:
            data (int): 要读取的整数值
            index (int): 比特位索引 (0 到 7，其中 0 表示最低位)

        返回:
            (int): 指定索引的比特位值 (1 或 0)
        """
        # return 1 if bool(data & (1 << index)) else 0
        return (data >> index) & 1

    @staticmethod
    def write(data: int, index: int, value: int) -> int:
        """
        修改一个整数中指定索引的比特位值

        参数:
            data (int): 要修改的整数值
            index (int): 比特位索引 (0 到 7，其中 0 表示最低位)
            value (int): 要设置的比特位值 (1 或 0)

        返回:
            (int): 修改后的整数值
        """
        mask = 1 << index
        return (data & ~mask) | ((value & 1) << index)
        # if value == 0:
        #     return data & ~(1 << index)
        # else:
        #     return data | (1 << index)


class Bits(dataTypeAbstract):
    """比特位 (1 字节)"""

    @staticmethod
    def read(data: bytes, pos: int) -> tuple[str, int]:
        """
        读取一个整数的所有比特位值 (1 字节)

        参数:
            data (bytes): 要读取的字节数据
            pos (int): 数据在字节中的位置

        返回:
            (tuple[str, int]): 包含每个比特位的值 (1 或 0) 的列表以及下一个字节的位置
        """
        bits: list[int] = []
        for i in range(8):  # 一个字节有 8 位
            bit = Bit.read(data[pos], i)
            bits.append(bit)

        return str(bits), pos + 1

    @staticmethod
    def write(data: bytearray, value: str) -> bytearray:
        """
        根据给定的比特位值列表构建一个整数

        参数:
            data (bytearray): 存储结果的字节数组
            value (list[int]): 每个比特位的值 (1 或 0) 的列表

        返回:
            (bytearray): 更新后的数据序列
        """
        _value = ast.literal_eval(value)

        if not isinstance(_value, list):
            raise TypeError(f'传入的值无法解析为 list，而被解析为："{_value.__class__.__name__}"')

        byte = 0
        if len(_value) < 8:
            _value.extend([0] * (8 - len(_value)))

        for i, bit in enumerate(_value):
            byte = Bit.write(byte, i, bit)

        data.append(byte)
        return data

    @staticmethod
    def __class_getitem__(key: int):
        return _Bits(key)


class _Bits(dataTypeAbstract):
    """比特位 (1 字节，带长度截取)"""

    def __init__(self, _len: int = 8):
        """比特位 (1 字节，带长度截取)"""
        self._len = _len

    def read(self, data: bytes, pos: int) -> tuple[str, int]:
        """
        读取一个整数的所有比特位值 (1 字节，带长度截取)

        参数:
            data (bytes): 要读取的字节数据
            pos (int): 数据在字节中的位置

        返回:
            (tuple[str, int]): 包含每个比特位的值 (1 或 0) 的列表以及下一个字节的位置
        """
        bits: list[int] = []
        for i in range(self._len):
            bit = Bit.read(data[pos], i)
            bits.append(bit)

        return str(bits), pos + 1

    @staticmethod
    def write(data: bytearray, value: str) -> bytearray:
        """
        根据给定的比特位值列表构建一个整数

        参数:
            data (bytearray): 存储结果的字节数组
            value (str): 每个比特位的值 (1 或 0) 的列表

        返回:
            (bytearray): 更新后的数据序列
        """
        _value = ast.literal_eval(value)

        if not isinstance(_value, list):
            raise TypeError(f'传入的值无法解析为 list，而被解析为："{_value.__class__.__name__}"')

        byte = 0

        if len(_value) < 8:
            _value.extend([0] * (8 - len(_value)))

        for i, bit in enumerate(_value):
            byte = Bit.write(byte, i, bit)

        data.append(byte)
        return data


class Byte(dataTypeAbstract):
    """一个字节 (1 字节)"""

    @staticmethod
    def read(data: bytes, pos: int):
        """
        读取一个字节的数据 (1 字节)

        参数:
            data (bytes): 包含数据的字节序列
            pos (int): 当前数据的字节位置

        返回:
            (tuple[int, int]): 包含读取的字节和下一个数据的位置
        """
        return data[pos], pos + 1

    @staticmethod
    def write(data: bytearray, value):
        """
        将一段字节写入字节序列

        参数:
            data (bytearray): 包含数据的字节序列
            value (Any): 要写入的字节值

        返回:
            (bytearray): 修改后的数据序列
        """
        if isinstance(value, int):
            data.append(value)
        else:
            data.extend(value)

        return data


class ShortInt(dataTypeAbstract):
    """短整型 (2 字节)"""

    @staticmethod
    def read(data: bytes, pos: int):
        """
        读取一个短整型的数据 (2 字节)

        参数:
            data (bytes): 包含数据的字节序列
            pos (int): 当前数据的字节位置

        返回:
            (tuple[int, int]): 包含读取的短整型数据和下一个数据的位置
        """
        return unpack("<H", data[pos : pos + 2])[0], pos + 2

    @staticmethod
    def write(data: bytearray, value: int):
        """
        将短整型数据写入字节序列

        参数:
            data (bytearray): 用于存储数据的字节序列
            value (int): 待写入的短整型数据

        返回:
            (bytearray): 更新后的字节序列
        """
        data.extend(pack("<H", value))

        return data


class Int(dataTypeAbstract):
    """整型 (4 字节)"""

    @staticmethod
    def read(data: bytes, pos: int):
        """
        读取一个整型的数据 (4 字节)

        参数:
            data (bytes): 包含数据的字节序列
            pos (int): 当前数据的字节位置

        返回:
            (tuple[int, int]): 包含读取的整型数据和下一个数据的位置
        """
        return unpack("<I", data[pos : pos + 4])[0], pos + 4

    @staticmethod
    def write(data: bytearray, value: int):
        """
        将一个整型值写入到字节序列

        参数:
            data (bytearray): 存储数据的字节序列
            value (int): 需要写入的整型值

        返回:
            (bytearray): 更新后的字节序列
        """
        data.extend(pack("<I", value))

        return data


class Float(dataTypeAbstract):
    """浮点型 (4 字节)"""

    @staticmethod
    def read(data: bytes, pos: int):
        """
        读取一个浮点型数据 (4 字节)

        参数:
            data (bytes): 包含数据的字节序列
            pos (int): 当前数据的字节位置

        返回:
            (tuple[int, int]): 包含读取的浮点型数据和下一个数据的位置
        """
        return unpack("<f", data[pos : pos + 4])[0], pos + 4

    @staticmethod
    def write(data: bytearray, value: float):
        """
        将浮点型数据写入字节序列

        参数:
            data (bytearray): 存储数据的字节序列
            value (float): 需要写入的浮点型数据

        返回:
            (bytearray): 包含写入数据后的字节序列
        """
        data.extend(pack("<f", value))

        return data


class VarInt(dataTypeAbstract):
    """变长整型 (1-2 字节)"""

    @staticmethod
    def read(data: bytes, pos: int):
        """
        读取一个变长整型数据 (1-2 字节)

        参数:
            data (bytes): 包含数据的字节序列
            pos (int): 当前数据的字节位置

        返回:
            (tuple[int, int]): 包含读取的变长整型数据和下一个数据的位置
        """
        if data[pos] > 127:  # 最高位为 1 表示该整数占两个字节
            pos += 2
            # 低字节取低 7 位，高字节左移 7 位后拼接
            var_int = (data[pos - 2] & 0b01111111) ^ (data[pos - 1] << 7)
        else:
            var_int = data[pos]
            pos += 1

        return var_int, pos

    @staticmethod
    def write(data: bytearray, value: int):
        """
        将变长整型数据写入字节序列

        参数:
            data (bytearray): 用于存储数据的字节序列
            value (int): 需要写入的变长整型数据

        返回:
            (bytearray): 更新后的字节序列
        """
        if value > 127:  # 大于 127 时写入两个字节：先写低 7 位并置延续标记，再写高位字节
            data = Byte.write(data, (value & 0b01111111) | 0b10000000)
            data = Byte.write(data, value >> 7)
        else:
            data = Byte.write(data, value)

        return data


class String(dataTypeAbstract):
    """字符串"""

    @staticmethod
    def read(data: bytes, pos: int):
        """
        读取一个字符串数据

        参数:
            data (bytes): 包含数据的字节序列
            pos (int): 当前数据的字节位置

        返回:
            (tuple[int, int]): 包含读取的字符串和下一个数据的位置
        """
        string_len, pos = VarInt.read(data, pos)  # 读取当前位置的变长整数，代表后续字节长度
        string_val = data[pos : pos + string_len].decode()  # 读取对应长度的字节并以 UTF-8 解码

        return string_val, pos + string_len

    @staticmethod
    def write(data: bytearray, value: str):
        """
        将字符串数据写入字节序列

        参数:
            data (bytearray): 用于存储数据的字节序列
            value (str): 需要写入的字符串数据

        返回:
            (bytearray): 更新后的字节序列
        """
        encoded_string = value.encode("utf-8")
        data = VarInt.write(data, len(encoded_string))
        data.extend(encoded_string)

        return data


class GameKey(dataTypeAbstract):
    @staticmethod
    def read(data: bytes, pos: int):
        all_keys = {}
        reader = Reader(data, pos)
        keySum = reader.type_read(VarInt)  # key 的总数量，决定循环次数

        for _ in range(keySum):
            name = reader.type_read(String)  # key 的名称
            # 数据总长度 (不包含 key 的名称)
            length = reader.type_read(Byte)
            one_key = all_keys[name] = {}  # 存储单个 key 的数据
            # key 的状态标志 (收藏品阅读、单曲解锁、收藏品、背景、头像)
            one_key["type"] = str((reader.type_read(Bits[5])))

            # key 的标记 (长度与 type 中 1 的数量一致，每位值相同，与收藏品碎片收集有关，默认为 1)
            flag = []
            # 前面已读取一个类型标志，此处长度需要减一
            for _ in range(length - 1):
                flag_value, reader.pos = Byte.read(data, reader.pos)
                flag.append(flag_value)
            one_key["flag"] = str(flag)

        return all_keys, reader.pos

    @staticmethod
    def write(data: bytearray, value: dict):
        writer = Writer(data)

        writer.type_write(VarInt, len(value))

        for keys in value.items():
            writer.type_write(String, keys[0])
            writer.type_write(Byte, len(ast.literal_eval(keys[1]["flag"])) + 1)
            writer.type_write(Bits, keys[1]["type"])

            for flag in ast.literal_eval(keys[1]["flag"]):
                writer.type_write(Byte, flag)

        return writer.get_data()


class Money(dataTypeAbstract):
    @staticmethod
    def read(data: bytes, pos: int):
        money = []
        for _ in range(5):
            money_value, pos = VarInt.read(data, pos)
            money.append(money_value)

        return money, pos

    @staticmethod
    def write(data: bytearray, value: list):
        for money_value in value:
            data = VarInt.write(data, money_value)

        return data


class GameRecord(dataTypeAbstract):
    @staticmethod
    def read(data: bytes, pos: int):
        all_record = {}  # 存储解析出来的数据
        diff_list: tuple = ("EZ", "HD", "IN", "AT", "Legacy")

        reader = Reader(data, pos)
        songSum: int = reader.type_read(VarInt)  # 歌曲总数

        for _ in range(songSum):
            songName: str = reader.type_read(String)  # 歌曲名称

            # 存在极少数歌曲 id 不带 .0 后缀，此处额外判断
            if songName.endswith(".0"):
                songName = songName[:-2]

            # 数据总长度 (不包括歌曲名称)
            length: int = reader.type_read(VarInt)
            end_position: int = reader.pos + length  # 单首歌数据结束的字节位置
            unlock: int = reader.type_read(Byte)  # 各难度的解锁情况
            fc: int = reader.type_read(Byte)  # 各难度的 Full Combo 情况
            song = all_record[songName] = {}  # 存储单首歌的成绩数据

            # 依次处理 EZ、HD、IN、AT、Legacy (旧谱) 难度的成绩
            for level in range(5):
                if Bit.read(unlock, level):  # 判断当前难度是否解锁
                    score: int = reader.type_read(Int)  # 分数
                    acc: float = reader.type_read(Float)  # acc

                    song[diff_list[level]] = {  # 按难度存入单首歌的成绩数据
                        "score": score,
                        "acc": acc,
                        "fc": Bit.read(fc, level),  # 是否 Full Combo (FC)
                    }

            if reader.pos != end_position:
                logger.error(f'读取 "{songName}" 的数据时发生错误，当前位置：{reader.pos}')
                logger.error(f"读取字节位置不正确，应为：{end_position}")

        return all_record, reader.pos

    @staticmethod
    def write(data: bytearray, value: dict):
        diff_list: dict = {"EZ": 0, "HD": 1, "IN": 2, "AT": 3, "Legacy": 4}

        writer = Writer(data)
        writer.type_write(VarInt, len(value))

        for name, song in value.items():
            writer.type_write(String, name + ".0")

            # 长度字段必须先于成绩数据写入，其值为：每个难度 4 字节分数加 4 字节 acc，
            # 再加 unlock 与 fc 各 1 字节
            writer.type_write(VarInt, len(song) * (4 + 4) + 1 + 1)
            unlock = ast.literal_eval(Bits.read(b"\x00", 0)[0])
            fc = ast.literal_eval(Bits.read(b"\x00", 0)[0])
            record_writer = Writer()
            for diff, index in diff_list.items():
                if song.get(diff) is not None:
                    unlock[index] = 1
                    record_writer.type_write(Int, song[diff]["score"])
                    record_writer.type_write(Float, song[diff]["acc"])
                    fc[index] = song[diff]["fc"]

            writer.type_write(Bits, str(unlock))
            writer.type_write(Bits, str(fc))
            writer.type_write(Byte, record_writer.get_data())

        return writer.get_data()


class Summary(dataTypeAbstract):
    @staticmethod
    def read(data: bytes, pos: int):
        reader = Reader(data, pos)
        return [reader.type_read(ShortInt) for _ in range(3)], reader.pos

    @staticmethod
    def write(data: bytearray, value: list):
        writer = Writer(data)
        for i in value:
            writer.type_write(ShortInt, i)

        return writer.get_data()


class Reader:
    """反序列化存档数据的操作类"""

    def __init__(self, data: Union[bytes, bytearray], pos: int = 0):
        """
        反序列化存档数据的操作类

        参数:
            data (bytes | bytearray): 要读取的二进制数据
            pos (int): 当前读写位置。默认为 0
        """
        self.data = data
        self.pos = pos
        self.bit_read = [bytes(), False, 0]

        self.read_dict = {}

    def type_read(self, type_class) -> Any:
        """
        使用数据类型提供的 read() 方法反序列化数据

        参数:
            type_class (class): 定义了 read() 方法的数据类型

        返回:
            (Any): 反序列化的数据
        """
        if type_class == Bit:
            if not self.bit_read[1]:
                self.bit_read[0], self.pos = Byte.read(self.data, self.pos)
                self.bit_read[1] = True

            read_data = Bit.read(self.bit_read[0], self.bit_read[2])
            self.bit_read[2] += 1

        else:
            if self.bit_read[1]:
                self.bit_read[1] = False
                self.bit_read[2] = 0

            read_data, self.pos = type_class.read(self.data, self.pos)

        return read_data

    def parseStructure(self, structure) -> Dict[str, Any]:
        """
        按照数据结构类定义的结构反序列化数据

        参数:
            structure (class): 数据结构类

        返回:
            (dict[str, Any]): 反序列化的数据
        """
        obj = structure()

        if not isinstance(obj, dataTypeAbstract):
            for key, type_obj in structure.__annotations__.items():
                if not __debug__:
                    print(key, type_obj)

                self.read_dict[key] = self.type_read(type_obj)

                if not __debug__:
                    print(key, getattr(obj, key))

        else:
            self.read_dict = self.type_read(obj)

        if self.remaining() == 0:
            logger.debug(f'结构 "{obj.__class__.__name__}" 读取完毕，剩余 {self.remaining()} 字节')

        else:
            logger.error(f'结构 "{obj.__class__.__name__}" 尚未读取完毕，剩余 {self.remaining()} 字节')

        return self.read_dict

    def remaining(self) -> int:
        """
        返回剩余未反序列化的数据长度

        返回:
            (int): 剩余未反序列化的数据长度
        """
        return len(self.data) - self.pos


class Writer:
    """序列化存档数据的操作类"""

    def __init__(self, data: Optional[Union[bytearray, bytes]] = None):
        """
        序列化存档数据的操作类

        参数:
            data (bytes | bytearray | None): 若不为空，则基于此数据向后拼接序列化数据
        """
        if data is None:
            self.data = bytearray()

        elif isinstance(data, bytes):
            self.data = bytearray(data)

        elif isinstance(data, bytearray):
            self.data = data

        else:
            raise TypeError(f'传入的数据类型不合法，不应为："{type(data)}"')

        self.bit_temp = [0, False, 0]

    def type_write(self, type_fc, value):
        """
        使用数据类型提供的 write() 方法序列化数据

        参数:
            type_fc (class): 定义了 write() 方法的数据类型
            value (Any): 要序列化的数据
        """
        if type_fc == Bit:
            if not self.bit_temp[1]:
                self.bit_temp[0] = 0
                self.bit_temp[1] = True

            self.bit_temp[0] = Bit.write(self.bit_temp[0], self.bit_temp[2], value)
            self.bit_temp[2] += 1

        else:
            if self.bit_temp[1]:
                self.bit_temp[1] = False
                self.bit_temp[2] = 0
                self.data = Byte.write(self.data, self.bit_temp[0])

            self.data = type_fc.write(self.data, value)

    def buildStructure(self, structure, data: dict) -> bytearray:
        """
        按照数据结构类定义的结构序列化数据

        参数:
            structure (class): 数据结构类

        返回:
            (bytearray): 序列化后的二进制数据
        """
        obj = structure()

        if not isinstance(obj, dataTypeAbstract):
            for key, type_obj in structure.__annotations__.items():
                if not __debug__:
                    print(key, type_obj)

                self.type_write(type_obj, data[key])

                if not __debug__:
                    print(key, getattr(obj, key))

        else:
            self.type_write(obj, data)

        return self.data

    def get_data(self) -> bytearray:
        """
        返回已经序列化的数据

        返回:
            (bytearray): 已序列化的数据
        """
        return self.data
