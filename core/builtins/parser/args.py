"""参数解析模块 - 定义命令参数的模式和匹配结果。"""

import itertools
import re
import traceback

from core.constants.exceptions import InvalidTemplatePattern, InvalidCommandFormatError

# 最大嵌套深度限制 - 防止无限递归
MAX_NEST_DEPTH = 10


class ArgumentPattern:
    """参数模式类 - 表示命令中的一个参数占位符。

    :param name: 参数的名称，用于标识和匹配结果中引用
    """

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return f'ArgumentPattern("{self.name}")'

    def __repr__(self):
        return self.__str__()


class DescPattern:
    """描述模式类 - 用于在命令模板中添加文本描述。

    :param text: 描述文本
    """

    def __init__(self, text: str):
        self.text = text

    def __str__(self):
        return f'DescPattern("{self.text}")'

    def __repr__(self):
        return self.__str__()


class Template:
    """命令模板类 - 定义一个命令的完整参数结构。

    :param args: 参数模式列表，可包含 ArgumentPattern、OptionalPattern、DescPattern
    :param priority: 优先级（用于多个模板匹配时的选择，数值越大优先级越高）
    """

    def __init__(
        self,
        args: "list[ArgumentPattern | OptionalPattern | DescPattern]",
        priority: int = 1,
    ):
        self.args_ = args
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
        self.flag = flag
        self.args = args

    def __str__(self):
        return f'OptionalPattern("{self.flag}", {self.args})'

    def __repr__(self):
        return self.__str__()


class Argument:
    def __init__(self, value: str):
        self.value = value


class Optional:
    """
    可选项类 - 表示解析后的可选参数。

    :param args: 可选项的参数字典
    :param flagged: 是否已被设置（有值）
    """

    def __init__(self, args: dict[str, dict], flagged=False):
        self.flagged = flagged
        self.args = args


class MatchedResult:
    def __init__(self, args: dict, original_template, priority: int = 1):
        self.args = args
        self.original_template = original_template
        self.priority = priority

    def __str__(self):
        return f"MatchedResult({self.args}, {self.priority})"

    def __repr__(self):
        return self.__str__()


def split_multi_arguments(lst: list[str]) -> list[str]:
    """分割包含多个选项的参数字符串。

    :param lst: 包含参数字符串的列表，字符串中可能包含 (option1|option2) 形式的选择组
    :return: 展开后的参数列表，每个变体为一个独立的字符串
    """
    patn = re.compile(r"\((.*?)\)")
    new_lst = []

    for item in lst:
        parts = patn.split(item)

        choices = []
        for i, part in enumerate(parts):
            if i % 2 != 0:
                choices.append(part.split("|"))
            else:
                choices.append([part])

        for combination in itertools.product(*choices):
            new_lst.append("".join(combination))

    return list(set(new_lst))


def parse_template(argv: list[str], depth: int = 0) -> list[Template]:
    """解析命令模板字符串为 Template 对象列表。

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

    for a in argv:
        if isinstance(a, str):
            a = a.strip()
            if not a:
                continue
            spl = split_multi_arguments([a])
            for split in spl:
                argv_.append(split)

    try:
        for a in argv_:
            if any(x in a for x in ["<[", ">{", "{<", "[{", "{["]):
                raise InvalidTemplatePattern(f"Illegal mixed bracket nesting: {a}")

            template = Template([])

            # (\[.*?]) - 可选参数块 [...]
            # (\{.*}) - 描述块 {...}
            patterns = list(filter(None, re.split(r"(\[.*?])|(<.*?>)|(\{.*})| ", a)))

            arg_names: set[str] = set()

            last_type = None

            seen_desc = False

            seen_variadic = False

            for p in patterns:
                strip_pattern = p.strip()
                if not strip_pattern:
                    continue

                if strip_pattern.startswith("["):
                    if not strip_pattern.endswith("]"):
                        raise InvalidTemplatePattern(f"Broken optional block: {p}")

                    inner = strip_pattern[1:-1].strip()
                    if not inner:
                        raise InvalidTemplatePattern("Empty optional block [] not allowed")

                    optional_patterns = inner.split(" ")
                    flag = None
                    args = []

                    if optional_patterns[0].startswith("<"):
                        if not optional_patterns[0].endswith(">"):
                            raise InvalidTemplatePattern(f"Broken argument block: {p}")
                        if not optional_patterns[0][1:-1].strip():
                            raise InvalidTemplatePattern("Empty argument block <> not allowed")
                        args += optional_patterns
                    else:
                        flag = optional_patterns[0]
                        args += optional_patterns[1:]

                    if flag and flag.startswith("-") and not flag.startswith("--") and len(flag) != 2:
                        raise InvalidTemplatePattern(f"Short option must contain exactly one character: {flag}")

                    if flag and flag.startswith("{"):
                        raise InvalidTemplatePattern(f"Optional flag cannot be description: {flag}")

                    arg_names_ = set()
                    for arg in args:
                        if arg in arg_names_:
                            raise InvalidTemplatePattern(f'Duplicate argument in optional flag "{flag}": {arg}')
                        arg_names_.add(arg)

                    if not flag:
                        for arg in args:
                            if arg in arg_names:
                                raise InvalidTemplatePattern(f"Duplicate required argument: {arg}")
                            arg_names.add(arg)

                    if last_type == "desc":
                        raise InvalidTemplatePattern(f"Optional argument cannot follow description: {p}")
                    if last_type == "optional_no_flag" and not flag:
                        raise InvalidTemplatePattern(f"Two no-flag optional arguments not allowed: {p}")

                    template.args.append(
                        OptionalPattern(flag=flag, args=parse_template([" ".join(args)], depth + 1) if args else [])
                    )
                    last_type = "optional" if flag else "optional_no_flag"

                elif strip_pattern.startswith("{"):
                    if not strip_pattern.endswith("}"):
                        raise InvalidTemplatePattern(f"Broken description block: {p}")

                    if seen_desc:
                        raise InvalidTemplatePattern(f"Multiple descriptions not allowed: {p}")
                    seen_desc = True

                    desc = strip_pattern[1:-1].strip()
                    if not desc:
                        raise InvalidTemplatePattern("Empty description block {} not allowed")

                    template.args.append(DescPattern(desc))
                    last_type = "desc"

                else:
                    if strip_pattern.startswith("<"):
                        if not strip_pattern.endswith(">"):
                            raise InvalidTemplatePattern(f"Broken argument block: {p}")
                        if not strip_pattern[1:-1].strip():
                            raise InvalidTemplatePattern("Empty argument block <> not allowed")

                    if last_type in ("optional", "optional_no_flag"):
                        raise InvalidTemplatePattern(f"Argument cannot follow optional block: {p}")
                    if last_type == "desc":
                        raise InvalidTemplatePattern(f"Argument cannot follow description: {p}")

                    if strip_pattern in arg_names:
                        raise InvalidTemplatePattern(f'Duplicate argument: "{strip_pattern}"')

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

            templates.append(template)

        return templates

    except InvalidTemplatePattern as e:
        traceback.print_exc()
        raise e


def templates_to_str(templates: list[Template], with_desc=False, simplify=True) -> list[str]:
    """将 Template 对象列表转换回字符串表示。

    :param templates: Template 对象列表
    :param with_desc: 是否包含描述信息（用于生成详细帮助）
    :param simplify: 是否简化输出（去除重复的描述）
    :return: 字符串列表，每个字符串代表一个模板的可读形式
    """
    text = []
    last_desc = None

    for template in templates:
        arg_text = []
        sub_arg_text = []
        has_desc = False

        for arg in template.args:
            if isinstance(arg, ArgumentPattern):
                sub_arg_text.append(arg.name)
            elif isinstance(arg, OptionalPattern):
                t = "["
                if arg.flag:
                    t += arg.flag
                if arg.args:
                    if arg.flag:
                        t += " "
                    t += " ".join(templates_to_str(arg.args, simplify=False))
                t += "]"
                sub_arg_text.append(t)
            elif isinstance(arg, DescPattern):
                has_desc = True
                sub_arg_text_ = " ".join(sub_arg_text)
                sub_arg_text.clear()

                if simplify and last_desc == arg.text:
                    continue

                if with_desc:
                    if sub_arg_text_:
                        arg_text.append(sub_arg_text_ + " - " + arg.text)
                    else:
                        arg_text.append("- " + arg.text)

                last_desc = arg.text

        if not has_desc:
            arg_text.append(" ".join(sub_arg_text))
            sub_arg_text.clear()

        if arg_text:
            text.append(" ".join(arg_text))

    return text


# POSIX 选项终止符：其后的 token 一律视为操作数，不再作为选项解析
OPTION_TERMINATOR = "--"


def _split_option_terminator(argv: list[str]) -> tuple[list[str], list[str]]:
    if OPTION_TERMINATOR in argv:
        index = argv.index(OPTION_TERMINATOR)
        return argv[:index], argv[index + 1 :]
    return argv[:], []


def _find_option(argv: list[str], flag: str, allow_inline: bool = True) -> tuple[int, str | None] | None:
    if not flag:
        return None

    allow_inline = allow_inline and flag.startswith("-")
    inline_prefix = flag + "="
    for index, token in enumerate(argv):
        if token == flag:
            return index, None
        if allow_inline and token.startswith(inline_prefix):
            return index, token[len(inline_prefix) :]

    return None


def parse_argv(argv: list[str], templates: list["Template"]) -> MatchedResult:
    """根据给定的模板列表解析命令行参数。

    :param argv: 命令行参数列表（不包括命令名本身）
    :param templates: 可用的模板列表，会逐个尝试匹配
    :return: MatchedResult 对象，包含：
             - args: 解析后的参数字典
             - original_template: 匹配的原始模板对象
             - priority: 最终优先级分数
    :raises InvalidCommandFormatError: 如果无法用任何模板匹配参数
    """
    matched_result = []

    for template in templates:
        try:
            # 选项匹配只在 `--` 之前的 token 上进行，`--` 之后的 token 一律按操作数处理
            # 切片返回新列表，因此后续的删除操作不会修改传入的 argv（保护输入数据）
            argv_copy, operand_argv = _split_option_terminator(argv)
            parsed_argv = {}
            original_template = template
            afters = []

            args = [x for x in template.args if not isinstance(x, DescPattern)]
            if not args:
                continue

            for a in args:
                if isinstance(a, OptionalPattern):
                    if not a.flag:
                        afters.append(a.args[0])
                        continue

                    parsed_argv[a.flag] = Optional({}, flagged=False)

                    has_sub_args = bool(a.args)
                    found = _find_option(argv_copy, a.flag, allow_inline=has_sub_args)
                    if found is not None:
                        index_flag, inline_value = found
                        if not has_sub_args:
                            parsed_argv[a.flag] = Optional({}, flagged=True)
                            del argv_copy[index_flag]
                        else:
                            len_t_args = len(a.args[0].args)
                            sub_argv = [] if inline_value is None else [inline_value]
                            needed = len_t_args - len(sub_argv)
                            consumed = 0
                            if needed > 0:
                                following = argv_copy[index_flag + 1 :]
                                consumed = min(needed, len(following))
                                sub_argv.extend(following[:consumed])

                            if sub_argv:
                                parsed_argv[a.flag] = Optional(parse_argv(sub_argv, a.args).args, flagged=True)
                                del argv_copy[index_flag : index_flag + 1 + consumed]

            argv_copy = argv_copy + operand_argv

            for a in args:
                if isinstance(a, ArgumentPattern):
                    if a.name.startswith("<"):
                        if len(argv_copy) > 0:
                            parsed_argv[a.name] = Argument(argv_copy[0])
                            del argv_copy[0]
                        else:
                            parsed_argv[a.name] = False

                    elif a.name == "...":
                        # 可变长参数：可以消耗 0 个或多个参数
                        # 暂时将其添加到 afters 列表，在剩余参数处理时再处理
                        afters.append(Template([a]))

                    else:
                        # 标志参数：仅接受精确匹配，`flag=value` 形式不视为该标志
                        found = _find_option(argv_copy, a.name, allow_inline=False)
                        parsed_argv[a.name] = found is not None
                        if found is not None:
                            # 如果标志存在，从参数列表中移除它
                            del argv_copy[found[0]]

            if argv_copy:
                if afters:
                    # 有可变长参数或无标志可选参数需要处理
                    ai = 1
                    for arg in afters:
                        subi = 1
                        for sub_args in arg.args:
                            if isinstance(sub_args, ArgumentPattern):
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
                                        parsed_argv[sub_args.name] = False

                                elif sub_args.name == "...":
                                    # 消耗所有剩余参数，每个参数包装为 Argument 对象
                                    parsed_argv[sub_args.name] = [Argument(x) for x in argv_copy]
                                    del argv_copy[:]

                                else:
                                    found = _find_option(argv_copy, sub_args.name, allow_inline=False)
                                    parsed_argv[sub_args.name] = found is not None
                                    if found is not None:
                                        del argv_copy[found[0]]
                            subi += 1
                        ai += 1

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
                                # 剩余 token 已并入上一个值参数，清空以避免重复处理
                                argv_copy.clear()

            # 将成功构建的匹配添加到结果列表
            matched_result.append(MatchedResult(parsed_argv, original_template, template.priority))
        except TypeError:
            traceback.print_exc()
            continue

    filtered_result = []
    for m in matched_result:
        filtered = False
        args_ = m.args
        for keys in args_:
            if isinstance(args_[keys], Optional):
                if not args_[keys].flagged:
                    args_[keys] = False
                else:
                    if not args_[keys].args:
                        args_[keys] = True
                    else:
                        args_[keys] = args_[keys].args

            elif isinstance(args_[keys], Argument):
                args_[keys] = args_[keys].value

            elif isinstance(args_[keys], list):
                args_[keys] = [v.value for v in args_[keys] if isinstance(v, Argument)]

            elif isinstance(args_[keys], bool):
                if not args_[keys]:
                    filtered = True
                    break

        if not filtered:
            filtered_result.append(m)

    len_filtered_result = len(filtered_result)

    if len_filtered_result > 1:
        priority_result = {}

        for f in filtered_result:
            priority = f.priority  # base priority
            for keys in f.args:
                if f.args[keys] is True:
                    priority += 1

            if priority not in priority_result:
                priority_result[priority] = [f]
            else:
                priority_result[priority].append(f)

        max_ = max(priority_result.keys())

        if len(priority_result[max_]) > 1:
            new_priority_result = {}
            for p in priority_result[max_]:
                new_priority = p.priority
                for keys in p.args:
                    if p.args[keys]:
                        new_priority += 1

                if new_priority not in new_priority_result:
                    new_priority_result[new_priority] = [p]
                else:
                    new_priority_result[new_priority].append(p)

            max_ = max(new_priority_result.keys())
            return new_priority_result[max_][0]

        return priority_result[max_][0]

    if len_filtered_result == 0:
        raise InvalidCommandFormatError

    return filtered_result[0]
