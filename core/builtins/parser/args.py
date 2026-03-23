"""
参数解析模块 - 定义命令参数的模式和匹配结果。

该模块提供了用于定义和解析命令参数模式的各种类，包括
参数模式、可选模式、模板等，是命令解析系统的基础。
"""

import re
import traceback

from core.constants.exceptions import InvalidTemplatePattern, InvalidCommandFormatError

# 最大嵌套深度限制 - 防止无限递归
MAX_NEST_DEPTH = 10


class ArgumentPattern:
    """
    参数模式类 - 表示命令中的一个参数占位符。

    用于在命令模板中定义一个需要解析的参数位置。

    :param name: 参数的名称，用于标识和匹配结果中引用
    """

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return f'ArgumentPattern("{self.name}")'

    def __repr__(self):
        return self.__str__()


class DescPattern:
    """
    描述模式类 - 用于在命令模板中添加文本描述。

    不进行参数匹配，仅用于帮助文档和提示。

    :param text: 描述文本
    """

    def __init__(self, text: str):
        self.text = text

    def __str__(self):
        return f'DescPattern("{self.text}")'

    def __repr__(self):
        return self.__str__()


class Template:
    """
    命令模板类 - 定义一个命令的完整参数结构。

    模板由一系列参数模式组成，用于匹配和解析用户输入。

    :param args: 参数模式列表，可包含 ArgumentPattern、OptionalPattern、DescPattern
    :param priority: 优先级（用于多个模板匹配时的选择，数值越大优先级越高）
    """

    def __init__(
        self,
        args: "list[ArgumentPattern | OptionalPattern | DescPattern]",
        priority: int = 1,
    ):
        # 参数列表
        self.args_ = args
        # 模板优先级
        self.priority = priority

    @property
    def args(self):
        """获取参数列表"""
        return self.args_

    def __str__(self):
        return f"Template({self.args})"

    def __repr__(self):
        return self.__str__()


class OptionalPattern:
    """
    可选模式类 - 表示可选的命令参数或选项。

    :param flag: 可选标志，如 "option" 或 "o"
    :param args: 该选项下的模板列表（支持多个可选变体）
    """

    def __init__(self, flag: str, args: list[Template]):
        # 选项标志
        self.flag = flag
        # 该选项的模板列表
        self.args = args

    def __str__(self):
        return f'OptionalPattern("{self.flag}", {self.args})'

    def __repr__(self):
        return self.__str__()


class Argument:
    """
    参数类 - 表示解析后的单个参数值。

    :param value: 参数值
    """

    def __init__(self, value: str):
        self.value = value


class Optional:
    """
    可选项类 - 表示解析后的可选参数。

    :param args: 可选项的参数字典
    :param flagged: 是否已被设置（有值）
    """

    def __init__(self, args: dict[str, dict], flagged=False):
        # 标志此选项是否被使用
        self.flagged = flagged
        # 选项的参数
        self.args = args


class MatchedResult:
    """
    匹配结果类 - 表示命令匹配后的结果。

    包含解析出的所有参数和匹配的原始模板信息。

    :param args: 解析出的参数字典
    :param original_template: 匹配的原始模板对象
    :param priority: 匹配的优先级
    """

    def __init__(self, args: dict, original_template, priority: int = 1):
        # 解析出的参数字典
        self.args = args
        # 原始模板引用
        self.original_template = original_template
        # 优先级（用于多模板匹配时排序）
        self.priority = priority

    def __str__(self):
        return f"MatchedResult({self.args}, {self.priority})"

    def __repr__(self):
        return self.__str__()


def split_multi_arguments(lst: list):
    """
    分割包含多个选项的参数字符串。

    该函数处理形如 "hello(world|everyone)" 的字符串，将其展开为多个变体：
    ["hello world", "hello everyone"]

    支持嵌套的括号和多个选择组。使用递归处理多层嵌套。

    示例:
    ```
        >>> split_multi_arguments(["hello(world|earth)"])
        ["hello world", "hello earth"]
        >>> split_multi_arguments(["a(b|c)d(e|f)"])
        ["abde", "abdf", "acde", "acdf"]
    ```

    :param lst: 包含参数字符串的列表，字符串中可能包含 (option1|option2) 形式的选择组
    :return: 展开后的参数列表，每个变体为一个独立的字符串
    """
    new_lst = []

    # 处理列表中的每一个字符串
    for x in lst:
        # 使用正则表达式分割括号部分
        # (\(.*?\)) 用于匹配最短的括号内容（非贪婪匹配）
        spl = list(filter(None, re.split(r"(\(.*?\))", x)))

        # 如果分割后有多个部分（包含括号）
        if len(spl) > 1:
            # 遍历每个部分
            for y in spl:
                index_y = spl.index(y)
                # 检查该部分是否是括号内的选择
                mat = re.match(r"\((.*?)\)", y)
                if mat:
                    # 提取括号内的内容并按 | 分割
                    spl1 = mat.group(1).split("|")
                    # 为每个选项创建一个完整的变体
                    for s in spl1:
                        cspl = spl.copy()
                        cspl.insert(index_y, s)
                        del cspl[index_y + 1]
                        new_lst.append("".join(cspl))
        else:
            # 只有一个部分的情况
            mat = re.match(r"\((.*?)\)", spl[0])
            if mat:
                # 括号内的选择
                spl1 = mat.group(1).split("|")
                for s in spl1:
                    new_lst.append(s)
            else:
                # 没有括号，直接添加
                new_lst.append(spl[0])

    # 检查是否还有未处理的括号（嵌套情况）
    split_more = False
    for n in new_lst:
        if re.match(r"\((.*?)\)", n):
            split_more = True

    # 如果还有括号，递归处理
    if split_more:
        return split_multi_arguments(new_lst)

    # 返回去重后的列表
    return list(set(new_lst))


def parse_template(argv: list[str], depth: int = 0) -> list[Template]:
    """
    解析命令模板字符串为 Template 对象列表。

    该函数是命令解析系统的核心，将用户定义的模板字符串转换为可用于匹配的
    Template 对象。支持递归处理嵌套的可选参数。

    模板语法:
        - <arg>: 必需参数，用 < > 包括
        - [option]: 可选参数，用 [ ] 包括
        - [flag <arg>]: 带标志的可选参数
        - {description}: 描述信息，用于生成帮助文本

    示例:
    ```
        > parse_template(["<source> [-o <destination>] {Copy a file}"])
        [Template([ArgumentPattern('source'),
        OptionalPattern('-o', [Template([ArgumentPattern('destination')])]),
         DescPattern('Copy a file')])]
    ```

    :param argv: 包含模板字符串的列表
    :param depth: 递归深度，用于防止无限递归（最大深度由 MAX_NEST_DEPTH 定义）
    :return: 解析后的 Template 对象列表
    :raises InvalidTemplatePattern: 如果模板格式不合法
    """
    # 防止无限递归（嵌套过深）
    if depth > MAX_NEST_DEPTH:
        raise InvalidTemplatePattern("Template nesting too deep")

    templates = []
    argv_ = []

    # 预处理输入参数
    for a in argv:
        if isinstance(a, str):
            a = a.strip()
            # 跳过空字符串
            if not a:
                continue
            # 分割包含多个选项的参数（如 "a(b|c)" -> ["ab", "ac"]）
            spl = split_multi_arguments([a])
            for split in spl:
                argv_.append(split)

    try:
        # 主处理循环：处理每一个模板字符串
        for a in argv_:
            # 检查非法的括号嵌套（如 <[ >{  等）
            if any(x in a for x in ["<[", ">{", "{<", "[{", "{["]):
                raise InvalidTemplatePattern(f"Illegal mixed bracket nesting: {a}")

            # 创建新的模板对象
            template = Template([])

            # 使用正则表达式分割模板字符串，分离出各种模式：
            # (\[.*?]) - 可选参数块 [...]
            # (<.*?>) - 参数块 <...>
            # (\{.*}) - 描述块 {...}
            # 空格作为分隔符
            patterns = list(filter(None, re.split(r"(\[.*?])|(<.*?>)|(\{.*})| ", a)))

            # 跟踪已使用的参数名称（用于检查重复）
            arg_names: set[str] = set()

            # 跟踪最后一个处理的模式类型（用于检查顺序合法性）
            # 可能的值: "argument", "optional", "optional_no_flag", "desc", "variadic"
            last_type = None

            # 标志是否已经出现过描述块
            seen_desc = False

            # 标志是否已经出现过可变长参数 (...)
            seen_variadic = False

            # 逐个处理每个分割出的模式
            for p in patterns:
                strip_pattern = p.strip()
                if not strip_pattern:
                    continue

                # ========== 处理可选参数块 [...]  ==========
                if strip_pattern.startswith("["):
                    # 验证括号完整性
                    if not strip_pattern.endswith("]"):
                        raise InvalidTemplatePattern(f"Broken optional block: {p}")

                    # 提取括号内的内容
                    inner = strip_pattern[1:-1].strip()
                    if not inner:
                        raise InvalidTemplatePattern("Empty optional block [] not allowed")

                    # 分割可选参数内容（空格分隔）
                    optional_patterns = inner.split(" ")
                    flag = None  # 可选参数的标志（如 "-o"）
                    args = []  # 可选参数包含的参数列表

                    # 判断第一个元素是参数还是标志
                    # 如果以 < 开头，说明是参数；否则是标志名称
                    if optional_patterns[0].startswith("<"):
                        # 第一个是参数：如 [<file>] 或 [<file> <mode>]
                        if not optional_patterns[0].endswith(">"):
                            raise InvalidTemplatePattern(f"Broken argument block: {p}")
                        if not optional_patterns[0][1:-1].strip():
                            raise InvalidTemplatePattern("Empty argument block <> not allowed")
                        args += optional_patterns  # 所有元素都是参数
                    else:
                        # 第一个是标志：如 [-o <output>]
                        flag = optional_patterns[0]  # 标志名称
                        args += optional_patterns[1:]  # 后续元素是该标志的参数

                    # 标志不能是描述（描述应该单独使用）
                    if flag and flag.startswith("{"):
                        raise InvalidTemplatePattern(f"Optional flag cannot be description: {flag}")

                    # 检查该可选参数内是否有重复的参数名
                    arg_names_ = set()
                    for arg in args:
                        if arg in arg_names_:
                            raise InvalidTemplatePattern(f'Duplicate argument in optional flag "{flag}": {arg}')
                        arg_names_.add(arg)

                    # 如果没有标志（无标志可选参数），检查是否与已有参数重复
                    if not flag:
                        for arg in args:
                            if arg in arg_names:
                                raise InvalidTemplatePattern(f"Duplicate required argument: {arg}")
                            arg_names.add(arg)

                    # ========== 顺序验证 ==========
                    # 描述块必须在最后
                    if last_type == "desc":
                        raise InvalidTemplatePattern(f"Optional argument cannot follow description: {p}")
                    # 不能有两个无标志的可选参数
                    if last_type == "optional_no_flag" and not flag:
                        raise InvalidTemplatePattern(f"Two no-flag optional arguments not allowed: {p}")

                    # 创建 OptionalPattern 对象
                    # 如果有参数，递归解析参数的模板；否则为空
                    template.args.append(
                        OptionalPattern(flag=flag, args=parse_template([" ".join(args)], depth + 1) if args else [])
                    )
                    last_type = "optional" if flag else "optional_no_flag"

                # ========== 处理描述块 {...} ==========
                elif strip_pattern.startswith("{"):
                    # 验证括号完整性
                    if not strip_pattern.endswith("}"):
                        raise InvalidTemplatePattern(f"Broken description block: {p}")

                    # 只允许一个描述块
                    if seen_desc:
                        raise InvalidTemplatePattern(f"Multiple descriptions not allowed: {p}")
                    seen_desc = True

                    # 提取描述文本
                    desc = strip_pattern[1:-1].strip()
                    if not desc:
                        raise InvalidTemplatePattern("Empty description block {} not allowed")

                    # 添加描述模式（用于生成帮助信息）
                    template.args.append(DescPattern(desc))
                    last_type = "desc"

                # ========== 处理必需参数或特殊符号 ==========
                else:
                    # 验证参数块的完整性
                    if strip_pattern.startswith("<"):
                        if not strip_pattern.endswith(">"):
                            raise InvalidTemplatePattern(f"Broken argument block: {p}")
                        if not strip_pattern[1:-1].strip():
                            raise InvalidTemplatePattern("Empty argument block <> not allowed")

                    # ========== 顺序验证 ==========
                    # 参数不能在可选参数之后
                    if last_type in ("optional", "optional_no_flag"):
                        raise InvalidTemplatePattern(f"Argument cannot follow optional block: {p}")
                    # 参数不能在描述之后
                    if last_type == "desc":
                        raise InvalidTemplatePattern(f"Argument cannot follow description: {p}")

                    # 检查参数名称的重复
                    if strip_pattern in arg_names:
                        raise InvalidTemplatePattern(f'Duplicate argument: "{strip_pattern}"')

                    # ========== 处理可变长参数 ... ==========
                    # ... 表示可以接收任意多个参数
                    if strip_pattern == "...":
                        if seen_variadic:
                            raise InvalidTemplatePattern('Duplicate "..." not allowed')
                        seen_variadic = True
                        last_type = "variadic"
                        template.args.append(ArgumentPattern("..."))
                        continue

                    # 添加普通参数
                    arg_names.add(strip_pattern)
                    template.args.append(ArgumentPattern(strip_pattern))
                    last_type = "argument"

            # 完成一个模板的解析，添加到结果列表
            templates.append(template)

        return templates

    except InvalidTemplatePattern as e:
        # 打印异常堆栈用于调试
        traceback.print_exc()
        raise e


def templates_to_str(templates: list[Template], with_desc=False, simplify=True) -> list[str]:
    """
    将 Template 对象列表转换回字符串表示。

    该函数用于生成帮助文本，将解析后的 Template 对象转换为人类可读的字符串格式。

    示例:
    ```
        > template = Template([ArgumentPattern('<source>'), OptionalPattern('-o', [Template([ArgumentPattern('<destination>')])]), DescPattern('Copy a file')])
        > templates_to_str([template])
        ['<source> [-o <destination>] - Copy a file']
    ```

    :param templates: Template 对象列表
    :param with_desc: 是否包含描述信息（用于生成详细帮助）
    :param simplify: 是否简化输出（去除重复的描述）
    :return: 字符串列表，每个字符串代表一个模板的可读形式
    """
    text = []
    last_desc = None  # 用于记录最后的描述，用于简化重复内容

    for template in templates:
        arg_text = []  # 该模板对应的所有参数文本
        sub_arg_text = []  # 当前子模板的参数文本
        has_desc = False  # 标记是否包含描述

        for arg in template.args:
            if isinstance(arg, ArgumentPattern):
                # 参数：直接添加名称
                sub_arg_text.append(arg.name)
            elif isinstance(arg, OptionalPattern):
                # 可选参数：用 [ ] 包括
                t = "["
                if arg.flag:
                    t += arg.flag
                if arg.args:
                    if arg.flag:
                        t += " "
                    # 递归处理嵌套模板
                    t += " ".join(templates_to_str(arg.args, simplify=False))
                t += "]"
                sub_arg_text.append(t)
            elif isinstance(arg, DescPattern):
                # 描述：用于生成帮助文本
                has_desc = True
                sub_arg_text_ = " ".join(sub_arg_text)
                sub_arg_text.clear()

                # 简化模式下，重复的描述只显示一次
                if simplify and last_desc == arg.text:
                    continue

                # 将参数和描述组合
                if with_desc:
                    if sub_arg_text_:
                        arg_text.append(sub_arg_text_ + " - " + arg.text)
                    else:
                        arg_text.append("- " + arg.text)

                last_desc = arg.text

        # 如果没有描述，直接添加参数文本
        if not has_desc:
            arg_text.append(" ".join(sub_arg_text))
            sub_arg_text.clear()

        if arg_text:
            text.append(" ".join(arg_text))

    return text


def parse_argv(argv: list[str], templates: list["Template"]) -> MatchedResult:
    """
    根据给定的模板列表解析命令行参数。

    该函数是参数解析的核心逻辑，尝试用各个模板匹配输入的参数列表。
    采用贪心匹配算法，逐个尝试每个模板直到找到匹配，然后根据优先级选择最佳结果。

    匹配流程：
    1. 逐个尝试所有模板
    2. 对每个模板，按顺序处理可选参数、必需参数和可变长参数
    3. 构建解析结果字典，存储解析后的参数值
    4. 过滤出有效的匹配结果（所有必需参数都被满足）
    5. 对多个有效匹配按优先级进行排序
    6. 返回优先级最高的匹配结果或抛出异常

    优先级计算规则：
    - 基础优先级：来自 Template 的 priority 值
    - 额外优先级：每个被成功匹配的参数加 1 分
    - 多个相同优先级时：再次按有值参数的个数排序

    参数类型说明：
    - `<param>`: 值参数，必须消耗一个参数值，如 <file>、<name>
    - flag: 标志参数，是否存在于参数列表中（True/False），如 -v
    - ...: 可变长参数，可消耗 0 个或多个参数
    - `[flag <param>]`: 可选参数，可能带有标志和子参数

    示例：
    - 模板: Template([ArgumentPattern('<lang>'), OptionalPattern('-v', [...])])
    - 输入: argv = ["python", "-v"]
    - 输出: MatchedResult({"<lang>": "python", "-v": True}, template, priority)

    :param argv: 命令行参数列表（不包括命令名本身）
    :param templates: 可用的模板列表，会逐个尝试匹配
    :return: MatchedResult 对象，包含：
             - args: 解析后的参数字典
             - original_template: 匹配的原始模板对象
             - priority: 最终优先级分数
    :raises InvalidCommandFormatError: 如果无法用任何模板匹配参数
    """
    matched_result = []

    # ========== 步骤 1: 尝试用每个模板进行匹配 ==========
    for template in templates:
        try:
            # 复制 argv 以避免修改原始列表（保护输入数据）
            argv_copy = argv.copy()
            parsed_argv = {}  # 存储解析结果的字典
            original_template = template
            afters = []  # 用于存储可变长参数的处理列表

            # 提取非描述的参数（DescPattern 仅用于文档，不参与解析）
            args = [x for x in template.args if not isinstance(x, DescPattern)]
            if not args:
                # 该模板没有可解析的参数，跳过
                continue

            # ========== 步骤 2: 处理可选参数 ==========
            # 可选参数由 OptionalPattern 表示，可能带有标志（如 --output、-v 等）
            for a in args:  # optional first
                if isinstance(a, OptionalPattern):
                    # 检查是否是无标志的可选参数（如 [<file>] 形式）
                    if not a.flag:
                        # 无标志的可选参数暂时存储到 afters，后续处理
                        afters.append(a.args[0])
                        continue

                    # 初始化该可选参数为未被设置状态
                    parsed_argv[a.flag] = Optional({}, flagged=False)

                    # 检查该标志是否在参数列表中
                    if a.flag in argv_copy:  # if flag is in argv
                        # 标志存在，需要处理其关联的参数
                        if not a.args:
                            # 该可选参数没有子参数，直接标记为已设置并移除标志
                            parsed_argv[a.flag] = Optional({}, flagged=True)
                            argv_copy.remove(a.flag)
                        else:
                            # 该可选参数有子参数，需要递归解析
                            index_flag = argv_copy.index(a.flag)
                            # 计算该可选参数需要的子参数个数
                            len_t_args = len(a.args[0].args)

                            # 检查是否有足够的参数来满足这个可选参数的需求
                            if len(argv_copy[index_flag:]) >= len_t_args:
                                # 提取该可选参数的所有子参数
                                sub_argv = argv_copy[index_flag + 1 : index_flag + len_t_args + 1]

                                # 递归调用 parse_argv 解析可选参数的子参数
                                parsed_argv[a.flag] = Optional(parse_argv(sub_argv, a.args).args, flagged=True)
                                # 从参数列表中删除已处理的部分（标志 + 子参数）
                                del argv_copy[index_flag : index_flag + len_t_args + 1]

            # ========== 步骤 3: 处理必需参数 ==========
            # 必需参数由 ArgumentPattern 表示（不在可选参数中的参数）
            for a in args:
                if isinstance(a, ArgumentPattern):
                    # ========== 处理 <param> 格式（值参数）==========
                    if a.name.startswith("<"):
                        # 值参数：必须消耗一个参数值
                        if len(argv_copy) > 0:
                            # 有可用参数，创建 Argument 对象并消耗该参数
                            parsed_argv[a.name] = Argument(argv_copy[0])
                            del argv_copy[0]
                        else:
                            # 没有可用参数，标记为 False（未满足）
                            parsed_argv[a.name] = False

                    # ========== 处理 ... （可变长参数）==========
                    elif a.name == "...":
                        # 可变长参数：可以消耗 0 个或多个参数
                        # 暂时将其添加到 afters 列表，在剩余参数处理时再处理
                        afters.append(Template([a]))

                    # ========== 处理布尔参数（标志）==========
                    else:
                        # 标志参数：检查是否存在于参数列表中
                        parsed_argv[a.name] = a.name in argv_copy
                        if parsed_argv[a.name]:
                            # 如果标志存在，从参数列表中移除它
                            argv_copy.remove(a.name)

            # ========== 步骤 4: 处理剩余参数（可变长参数和无标志可选参数）==========
            if argv_copy:
                if afters:
                    # 有可变长参数或无标志可选参数需要处理
                    ai = 1
                    for arg in afters:
                        subi = 1
                        for sub_args in arg.args:
                            if isinstance(sub_args, ArgumentPattern):
                                # ========== 处理 <param> 参数 ==========
                                if sub_args.name.startswith("<"):
                                    if len(argv_copy) > 0:
                                        # 检查是否是最后一个参数
                                        if len(afters) == ai and len(arg.args) == subi:
                                            # 最后的参数，消耗所有剩余的参数（用空格连接）
                                            parsed_argv[sub_args.name] = Argument(" ".join(argv_copy))
                                            argv_copy.clear()
                                        else:
                                            # 非最后参数，只消耗一个参数
                                            parsed_argv[sub_args.name] = Argument(argv_copy[0])
                                            del argv_copy[0]
                                    else:
                                        # 没有可用参数，标记为 False
                                        parsed_argv[sub_args.name] = False

                                # ========== 处理 ... 可变长参数 ==========
                                elif sub_args.name == "...":
                                    # 消耗所有剩余参数，每个参数包装为 Argument 对象
                                    parsed_argv[sub_args.name] = [Argument(x) for x in argv_copy]
                                    del argv_copy[:]

                                # ========== 处理布尔标志参数 ==========
                                else:
                                    parsed_argv[sub_args.name] = sub_args.name in argv_copy
                                    if parsed_argv[sub_args.name]:
                                        argv_copy.remove(sub_args.name)
                            subi += 1
                        ai += 1

                # ========== 步骤 5: 处理最后的剩余参数 ==========
                # 如果仍有参数未处理，尝试添加到最后一个值参数
                if argv_copy:
                    template_arguments = [arg for arg in args if isinstance(arg, ArgumentPattern)]
                    if template_arguments:
                        # 检查最后一个参数是否是值参数（< > 格式）
                        if isinstance(template_arguments[-1], ArgumentPattern):
                            if template_arguments[-1].name.startswith("<"):
                                # 最后一个参数是值参数，将剩余参数追加到它（用空格连接）
                                argv_keys = list(parsed_argv.keys())
                                parsed_argv[argv_keys[argv_keys.index(template_arguments[-1].name)]].value += (
                                    " " + " ".join(argv_copy)
                                )
                                del argv_copy[0]

            # 将成功构建的匹配添加到结果列表
            matched_result.append(MatchedResult(parsed_argv, original_template, template.priority))
        except TypeError:
            # 类型错误，说明该模板不适用，跳过继续尝试下一个模板
            traceback.print_exc()
            continue

    # ========== 步骤 6: 转换解析结果，将对象转换为实际值 ==========
    filtered_result = []
    for m in matched_result:  # convert to result dict
        # 标记该匹配是否被过滤（由于缺少必需参数）
        filtered = False
        args_ = m.args
        for keys in args_:
            # ========== 转换 Optional 对象 ==========
            if isinstance(args_[keys], Optional):
                # 如果可选参数未被设置（flagged=False），则值为 False
                if not args_[keys].flagged:
                    args_[keys] = False
                else:
                    # 已设置的可选参数
                    if not args_[keys].args:
                        # 没有子参数，标记为 True
                        args_[keys] = True
                    else:
                        # 有子参数，使用解析后的参数字典
                        args_[keys] = args_[keys].args

            # ========== 转换 Argument 对象 ==========
            elif isinstance(args_[keys], Argument):
                # 提取 Argument 对象中的字符串值
                args_[keys] = args_[keys].value

            # ========== 转换列表参数 ==========
            elif isinstance(args_[keys], list):
                # 处理 [...] 参数列表，提取每个 Argument 的值
                args_[keys] = [v.value for v in args_[keys] if isinstance(v, Argument)]

            # ========== 处理布尔参数 ==========
            elif isinstance(args_[keys], bool):
                # 如果是必需的参数但未被找到（值为 False），标记此匹配为无效
                if not args_[keys]:
                    filtered = True
                    break

        # 只保留有效的匹配结果（所有必需参数都被成功匹配）
        if not filtered:
            filtered_result.append(m)

    # ========== 步骤 7: 优先级选择和排序 ==========
    len_filtered_result = len(filtered_result)

    if len_filtered_result > 1:
        # 多个匹配存在，需要按优先级选择最佳的
        priority_result = {}

        # 第一轮优先级计算：基础优先级 + 参数匹配度
        for f in filtered_result:
            # 基础优先级来自模板的 priority 值
            priority = f.priority  # base priority
            for keys in f.args:
                # 为每个被成功匹配的参数增加优先级分数
                if f.args[keys] is True:  # if argument is not any else
                    priority += 1

            # 按优先级分组
            if priority not in priority_result:
                priority_result[priority] = [f]
            else:
                priority_result[priority].append(f)

        # 选择最高优先级的匹配
        max_ = max(priority_result.keys())

        if len(priority_result[max_]) > 1:
            # 仍有多个相同优先级的匹配，进行二次优先级计算
            new_priority_result = {}
            for p in priority_result[max_]:
                new_priority = p.priority
                for keys in p.args:
                    # 统计有值的参数（非 False、非空的参数）
                    if p.args[keys]:
                        new_priority += 1

                # 按新的优先级分组
                if new_priority not in new_priority_result:
                    new_priority_result[new_priority] = [p]
                else:
                    new_priority_result[new_priority].append(p)

            # 取最高优先级的第一个匹配
            max_ = max(new_priority_result.keys())
            return new_priority_result[max_][0]

        return priority_result[max_][0]

    # ========== 步骤 8: 返回结果或异常 ==========
    if len_filtered_result == 0:
        # 没有任何模板能匹配给定的参数
        raise InvalidCommandFormatError

    # 返回唯一的有效匹配
    return filtered_result[0]
