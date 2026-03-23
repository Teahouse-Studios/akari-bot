"""
配置装饰器模块。

该模块提供了一个配置装饰器，用于将 Python 类自动转换为配置对象。
装饰器会自动处理配置文件的生成和加载，使得定义配置变得简单直观。

主要功能：
- 为类自动生成配置文件
- 支持类型注解和类型检查
- 支持敏感信息加密存储
- 自动生成 __init__ 和 __repr__ 方法
"""

import inspect
from typing import Any, Literal, TypeVar, get_args
from types import UnionType


from core.exports import add_export
from . import CFGManager, ALLOWED_TYPES

# 类型变量，用于泛型支持
T = TypeVar("T")


def _process_class(cls: type[T], table_name, secret=False) -> type[T]:
    """处理类并转换为配置对象。

    该函数是核心的转换逻辑，它会：
    1. 提取类的所有注解（类型提示）
    2. 为类生成自定义的 __init__ 和 __repr__ 方法
    3. 自动生成和管理配置文件

    :param cls: 要处理的类对象
    :param table_name: 配置表名称，用于在配置文件中标识该配置块
    :param secret: 是否将该配置的值视为敏感信息进行加密存储（默认 False）
    :return: 处理后的类对象，具有自动生成的初始化和字符串表示方法
    """
    # 获取类的所有类型注解（排除私有属性）
    cls_annotations = {k: v for k, v in inspect.get_annotations(cls).items() if not k.startswith("__")}
    # 如果没有注解，则使用类属性本身作为注解
    if not cls_annotations:
        cls_annotations = {k: Any for k, _ in vars(cls).items() if not k.startswith("__")}

    def __init__(self, **kwargs):
        """自动生成的初始化方法。

        支持通过关键字参数初始化所有字段。任何未提供的字段会使用类注解中的默认值。

        :param **kwargs: `<字段名>=<值>` 的键值对，用于初始化对象属性
        """
        for field_name, _ in cls_annotations.items():
            # 从类注解中获取该字段的类型（用作默认值）
            default_value = cls_annotations.get(field_name, None)
            # 优先使用 kwargs 中提供的值，否则使用默认值
            # 这样可以在创建实例时选择性地覆盖默认值
            __value = kwargs.get(field_name, default_value)
            # 将值设置为对象的属性
            setattr(self, field_name, __value)

    def __repr__(self):
        """自动生成的字符串表示方法。

        返回一个形如"ClassName(field1=value1, field2=value2, ...)"的字符串，
        便于调试和日志记录。

        :return: 对象的字符串表示
        """
        # 遍历所有字段，构建"field=value"的字符串列表
        # 使用 `repr()`` 函数获取值的完整字符串表示（包括引号）
        fields_str = ", ".join(f"{name}={getattr(self, name)!r}" for name in cls_annotations)
        # 返回标准的 Python 对象表示格式：ClassName(...)
        return f"{cls.__name__}({fields_str})"

    def __generate_config_file():
        """生成配置文件。

        遍历所有类字段，为每个字段在配置文件中创建对应的配置项。
        该函数会：
        1. 检查字段类型是否为允许的类型
        2. 从现有配置中加载数据
        3. 如果配置项不存在，则创建新的配置项
        4. 保存配置文件

        处理的类型包括：
        - ALLOWED_TYPES 中定义的基本类型
        - Union 类型（只要所有分支都在 ALLOWED_TYPES 中）
        """
        for attr_name, attr_type in cls_annotations.items():
            # 跳过私有属性（以 `__` 开头的属性）
            if not attr_name.startswith("__"):
                # 从类定义中获取该属性的默认值
                __attr = getattr(cls, attr_name)
                __attr_type = attr_type

                # 检查类型是否在允许列表中
                # 对于 Union 类型（如 str | int），需要检查其所有分支是否都被允许
                # 如果类型不被允许，则将其设置为 None
                if __attr_type not in ALLOWED_TYPES and (
                    isinstance(__attr_type, UnionType) and any(k not in ALLOWED_TYPES for k in get_args(__attr_type))
                ):
                    __attr_type = None

                # 检查配置项是否已存在于 CFGManager 中
                # 如果不存在，则创建新的配置项
                if attr_name not in CFGManager.values:
                    # 从持久化存储中加载现有配置
                    CFGManager.load()
                    # 创建新的配置项
                    CFGManager.get(
                        attr_name,
                        __attr if __attr != "" else None,  # 默认值：使用类属性值或None
                        get_args(__attr_type) if isinstance(__attr_type, UnionType) else attr_type,  # 类型信息
                        secret,  # 敏感信息标志
                        table_name,  # 配置表名
                        _generate=True,  # 生成模式标志
                    )
                    # 保存修改到配置文件
                    CFGManager.save()

    # 执行配置文件生成，为该类创建配置项
    __generate_config_file()

    # 用自动生成的方法替换类的原始方法
    # 这样可以确保所有通过该类创建的实例都使用生成的初始化和表示方法
    cls.__repr__ = __repr__
    cls.__init__ = __init__

    # 返回处理后的类，保持了原有的类名和属性，但添加了配置管理功能
    return cls


def on_config(table_name: str, table_type: Literal["module", "bot", ""] = "", secret: bool = False):
    """配置装饰器工厂函数。

    这是一个装饰器工厂，返回实际的装饰器函数。

    示例:
    ```
        @on_config("my_config", table_type="module")
        class MyConfig:
            api_key: str = "default_key"
            timeout: int = 30
            enable_debug: bool = False
    ```

    该装饰器会自动：
    1. 为 MyConfig 类生成 __init__ 和 __repr__ 方法
    2. 在配置文件中创建 `module_my_config` 表
    3. 为所有类属性创建配置项

    :param table_name: 配置表的基本名称。最终的表名为 "table_type_table_name" 的形式
                   例如：`table_type="module", table_name="myconfig" -> "module_myconfig"`
    :param table_type: 配置表的类型，用于分类和命名空间隔离（默认""）
                   - "module": 模块配置
                   - "bot": 机器人配置
                   - "": 空字符串表示不添加前缀
    :param secret: 是否将此配置中的所有值视为敏感信息进行加密存储（默认 False）。
               设置为 True 时，配置值会被加密存储在配置文件中。

    :return: 装饰器函数，接收一个类并返回处理后的类
    """

    def wrap(cls: type[T]):
        """实际的装饰器函数。

        构造完整的表名并调用_process_class进行处理。

        :param cls: 要装饰的配置类

        :return: 处理后的类，具有自动生成的配置管理功能
        """
        # 构造表名：如果 table_type 不为空，则添加前缀和下划线分隔符
        __type = table_type + "_" if table_type != "" else table_type
        return _process_class(cls, __type + table_name, secret)

    return wrap


# 将 _process_class 函数导出到系统模块导出表中，使其可被其他模块导入使用
add_export(_process_class)
