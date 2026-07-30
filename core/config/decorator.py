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
from types import UnionType
from typing import Any, Literal, TypeVar, get_args

from core.exports import add_export
from . import CFGManager, ALLOWED_TYPES

# 类型变量，用于泛型支持
T = TypeVar("T")


class ConfigMeta(type):
    """配置模板的元类，使类属性访问直接返回配置文件中的当前值。

    模板此前仅靠导入副作用生成配置文件，类本身无人引用，取值代码只得将键名、默认值、类型与表名
    重复声明一次，二者不一致即造成同一配置项存在两个互不相同的默认值。引入本元类后，
    ``AiocqhttpConfig.qq_typing_emoji`` 即为该配置项的当前值，模板成为唯一的定义处。

    必须实现在元类上：类体内的 ``__getattr__`` 只对实例生效，对类属性访问不起作用。
    """

    def __getattr__(cls, name: str):
        """转调 :meth:`CFGManager.get` 读取配置项。

        :param name: 配置项名称。
        :raises AttributeError: 该名称未在模板中声明。
        """
        field = cls.__dict__.get("__config_fields__", {}).get(name)
        if field is None:
            # 未声明的名称照常报错：键名书写有误时立即抛出异常，而非静默返回默认值
            raise AttributeError(f"{cls.__name__} has no config field {name!r}")
        return CFGManager.get(**field)


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
    cls_annotations = {k: v for k, v in inspect.get_annotations(cls).items() if not k.startswith("__")}
    # 未写类型标注时退回类属性本身，使无标注的模板仍能生成配置项
    if not cls_annotations:
        cls_annotations = {k: Any for k, _ in vars(cls).items() if not k.startswith("__")}

    # 各字段传给 CFGManager.get() 的完整参数，既供元类读取配置值，也供 __init__ 取默认值
    config_fields: dict[str, dict[str, Any]] = {}

    def __init__(self, **kwargs):
        """自动生成的初始化方法。

        支持通过关键字参数初始化所有字段。任何未提供的字段会使用模板中声明的默认值。

        :param **kwargs: `<字段名>=<值>` 的键值对，用于初始化对象属性
        """
        for field_name, field in config_fields.items():
            # 默认值须取自字段登记表。cls_annotations 存放的是类型标注而非默认值，
            # 此前从中取值会使实例属性得到类型对象本身（如 <class 'int'>）而非 181
            setattr(self, field_name, kwargs.get(field_name, field["default"]))

    def __repr__(self):
        """自动生成的字符串表示方法，形如 ``ClassName(field1=value1, ...)``。

        :return: 对象的字符串表示
        """
        fields_str = ", ".join(f"{name}={getattr(self, name)!r}" for name in cls_annotations)
        return f"{cls.__name__}({fields_str})"

    def __generate_config_file():
        """登记全部字段，并为配置文件中缺失的项补写默认值。"""
        for attr_name, attr_type in cls_annotations.items():
            if not attr_name.startswith("__"):
                # 仅有类型标注而无赋值，表示该项必填且无默认值：此处取 None 交由下游处理，
                # 生成时将填入 <Replace me with ...> 占位符，在用户填写之前读取该项一律返回 None
                __attr = getattr(cls, attr_name, None)
                __attr_type = attr_type

                # 含不受支持成员的联合类型（如 str | None）一律置空，下游据此填入通用占位符
                if __attr_type not in ALLOWED_TYPES and (
                    isinstance(__attr_type, UnionType) and any(k not in ALLOWED_TYPES for k in get_args(__attr_type))
                ):
                    __attr_type = None

                # 登记该字段传给 CFGManager.get() 的参数，供元类在属性访问时按此取值
                config_fields[attr_name] = {
                    "q": attr_name,
                    "default": __attr,
                    "cfg_type": get_args(__attr_type) if isinstance(__attr_type, UnionType) else __attr_type,
                    "secret": secret,
                    "table_name": table_name,
                }

                # 只读进程不补写配置文件：生成统一在 bot.py 的 pre_init() 中完成，
                # 以免每个子进程重新导入模板时重复补写同一批配置项。
                # 字段登记仍须执行，否则模板类属性无法读取。
                if CFGManager.readonly:
                    continue

                # 检查配置项是否已存在于目标表中，不存在时才补写
                # 注意不可用 attr_name 与 CFGManager.values 比较：后者的键为配置文件名而非配置项键名，
                # 二者不存在交集，该判据将恒为真，使每个属性都触发一次全量重写
                if not CFGManager.has(attr_name, secret, table_name):
                    # 创建新的配置项
                    CFGManager.get(
                        attr_name,
                        __attr if __attr != "" else None,  # 默认值：使用类属性值或None
                        # 须传入已规整的 __attr_type：含不受支持成员的联合类型（如 str | None）在上方已被置空，
                        # 此处若回退为原始的 attr_type，下游将取得不具有 __name__ 的 UnionType 而报错
                        get_args(__attr_type) if isinstance(__attr_type, UnionType) else __attr_type,  # 类型信息
                        secret,  # 敏感信息标志
                        table_name,  # 配置表名
                        _generate=True,  # 生成模式标志
                    )
                    # 保存修改到配置文件
                    CFGManager.save()

    # 执行配置文件生成，为该类创建配置项，同时填充 config_fields
    __generate_config_file()

    # 以 ConfigMeta 为元类重建该类。元类无法在类创建后更换，只能另建一个同名类。
    namespace = {
        k: v
        for k, v in vars(cls).items()
        # 声明字段必须从类命名空间中移除：类属性会先于元类的 __getattr__ 命中，
        # 保留下来读到的将是静态默认值而非配置文件中的当前值。
        # __dict__ 与 __weakref__ 是新建类时自动生成的描述符，一并复制将导致类创建失败。
        if k not in config_fields and k not in ("__dict__", "__weakref__")
    }
    namespace.update({"__config_fields__": config_fields, "__init__": __init__, "__repr__": __repr__})

    new_cls = ConfigMeta(cls.__name__, cls.__bases__, namespace)
    new_cls.__module__ = cls.__module__
    new_cls.__qualname__ = cls.__qualname__
    return new_cls


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


def on_base_config():
    """表外顶层配置项的装饰器工厂函数。

    `config.toml` 中存在少量位于任何表之外的顶层键值对（如 ``default_locale``），
    它们由配置文件的生成与版本迁移直接写入。以 ``on_config("config")`` 声明将把它们移入
    ``[config]`` 表内而改变配置文件结构，故另设本装饰器：不指定表名，
    :meth:`CFGManager.get` 与 :meth:`CFGManager.has` 在表名缺省时会先查找表外的顶层键。

    示例:
    ```
        @on_base_config()
        class BaseConfig:
            default_locale: str = default_locale
    ```

    :return: 装饰器函数，接收一个类并返回处理后的类
    """

    def wrap(cls: type[T]):
        # 表名传 None：这类键不属于 [config]，也不属于任何其它表。
        # 补写路径不支持在表外新建键，键不存在时将被写入 [config] 表。该情形不会出现：
        # 这些键由 core/scripts/config_generate.py 在建立配置文件时写入，
        # 并由 core/config/update.py 的版本迁移保证存在，二者均先于模板的处理执行。
        return _process_class(cls, None, False)

    return wrap


def on_bot_config(bot_name: str, secret: bool = False):
    """平台配置装饰器工厂函数。

    等价于 ``on_config(bot_name, table_type="bot", secret=secret)``，供 ``bots/`` 下的配置模板使用。

    示例:
    ```
        @on_bot_config("onebot")
        class AiocqhttpConfig:
            qq_typing_emoji: int = 181
    ```

    :param bot_name: 平台名称，须与 `bots/` 下的目录名一致：守护进程以 ``bot_<目录名>``
                 的表名查找该平台的 `enable` 配置。最终的表名为 "bot_平台名"
    :param secret: 是否将此配置中的所有值视为敏感信息进行加密存储（默认 False）

    :return: 装饰器函数，接收一个类并返回处理后的类
    """
    return on_config(bot_name, "bot", secret)


def on_module_config(module_name: str, secret: bool = False):
    """模块配置装饰器工厂函数。

    等价于 ``on_config(module_name, table_type="module", secret=secret)``，供 ``modules/`` 下的配置模板使用。

    示例:
    ```
        @on_module_config("dice")
        class DiceConfig:
            dice_limit: int = 100
    ```

    模块的配置模板不应改用 ``Bind.Module.config()`` 声明：后者需要模板反向导入模块对象
    （``from . import dice``），一旦同包内其它文件在顶层读取该模板，
    包的初始化便会与模板互相等待而形成循环导入。本装饰器不依赖模块对象，模板因而是一个叶子模块。

    :param module_name: 模块名称，须与 `module()` 声明的名称一致。最终的表名为 "module_模块名"
    :param secret: 是否将此配置中的所有值视为敏感信息进行加密存储（默认 False）

    :return: 装饰器函数，接收一个类并返回处理后的类
    """
    return on_config(module_name, "module", secret)


# 将 _process_class 函数导出到系统模块导出表中，使其可被其他模块导入使用
add_export(_process_class)
