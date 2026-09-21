"""core.builtins.parser 命令解析单元测试。"""

from types import SimpleNamespace

from core.builtins.parser.args import (
    ArgumentPattern,
    DescPattern,
    Template,
    OptionalPattern,
    split_multi_arguments,
    parse_template,
    templates_to_str,
)
from core.builtins.parser.command import CommandParser, _split_command
from core.builtins.parser.message import _build_command_kwargs, _resolve_parsed_value, _unwrap_option_value
from core.builtins.message.elements import MarkdownElement
from core.builtins.bot import Bot
from core.constants.exceptions import InvalidTemplatePattern
from core.tester import func_case, Tester
from core.types import Module
from core.types.module.component_meta import CommandMeta


def _test_argument_pattern():
    try:
        pattern = ArgumentPattern("<name>")
        if pattern.name != "<name>":
            return False
        if "name" not in str(pattern):
            return False
        return True
    except Exception:
        return False


def _test_desc_pattern():
    try:
        pattern = DescPattern("This is a description")
        if pattern.text != "This is a description":
            return False
        if "description" not in str(pattern):
            return False
        return True
    except Exception:
        return False


def _test_template():
    try:
        template = Template([ArgumentPattern("<arg1>"), ArgumentPattern("<arg2>")])
        if len(template.args) != 2:
            return False
        if template.priority != 1:
            return False
        return True
    except Exception:
        return False


def _test_template_priority():
    try:
        template = Template([ArgumentPattern("<arg>")], priority=5)
        if template.priority != 5:
            return False
        return True
    except Exception:
        return False


def _test_optional_pattern():
    try:
        pattern = OptionalPattern("-o", [Template([ArgumentPattern("<output>")])])
        if pattern.flag != "-o":
            return False
        if len(pattern.args) != 1:
            return False
        return True
    except Exception:
        return False


def _test_split_multi_arguments():
    try:
        result = split_multi_arguments(["hello(world|earth)"])
        if set(result) != {"helloworld", "helloearth"}:
            return False

        result = split_multi_arguments(["a(b|c)d(e|f)"])
        expected = {"abde", "abdf", "acde", "acdf"}
        if set(result) != expected:
            return False

        result = split_multi_arguments(["hello"])
        if result != ["hello"]:
            return False

        return True
    except Exception:
        return False


def _test_parse_template_simple():
    try:
        templates = parse_template(["<arg1> <arg2>"])
        if len(templates) != 1:
            return False
        template = templates[0]
        if len(template.args) != 2:
            return False
        if not isinstance(template.args[0], ArgumentPattern):
            return False
        return True
    except Exception:
        return False


def _test_parse_template_optional():
    try:
        templates = parse_template(["<arg> [-o <output>]"])
        if len(templates) != 1:
            return False
        template = templates[0]
        arg_count = sum(1 for a in template.args if isinstance(a, ArgumentPattern))
        opt_count = sum(1 for a in template.args if isinstance(a, OptionalPattern))
        if arg_count != 1:
            return False
        if opt_count != 1:
            return False
        return True
    except Exception:
        return False


def _test_parse_template_rejects_multi_character_short_option():
    try:
        parse_template(["[-abc]"])
    except InvalidTemplatePattern:
        return parse_template(["[-a]"]) and parse_template(["[--abc]"])
    except Exception:
        return False
    return False


def _test_parse_template_description():
    try:
        templates = parse_template(["<arg> {This is a description}"])
        if len(templates) != 1:
            return False
        template = templates[0]
        desc_count = sum(1 for a in template.args if isinstance(a, DescPattern))
        if desc_count != 1:
            return False
        return True
    except Exception:
        return False


def _test_parse_template_variadic():
    try:
        templates = parse_template(["<command> ..."])
        if len(templates) != 1:
            return False
        template = templates[0]
        variadic = [a for a in template.args if isinstance(a, ArgumentPattern) and a.name == "..."]
        if len(variadic) != 1:
            return False
        return True
    except Exception:
        return False


def _test_parse_template_multiple():
    try:
        templates = parse_template(["<arg1>", "<arg1> <arg2>"])
        if len(templates) != 2:
            return False
        return True
    except Exception:
        return False


def _test_templates_to_str():
    try:
        templates = parse_template(["<source> [-o <destination>]"])
        result = templates_to_str(templates)
        if len(result) != 1:
            return False
        if "<source>" not in result[0]:
            return False
        return True
    except Exception:
        return False


def _test_templates_to_str_with_desc():
    try:
        templates = parse_template(["<arg> {Description}"])
        result = templates_to_str(templates, with_desc=True)
        if len(result) != 1:
            return False
        if "Description" not in result[0]:
            return False
        return True
    except Exception:
        return False


def _test_default_command_help_doc():
    module = Module.assign(module_name="self-command", alias=None, recommend_modules=None, developers=None)
    module.command_list.add(CommandMeta())
    parser = CommandParser(module, ["~"], module_name=module.module_name)

    return parser.return_formatted_help_doc() == "~self-command" and parser.return_json_help_doc() == {
        "args": [{"args": "~self-command", "desc": ""}],
        "options": [],
    }


def _test_command_parser_preserves_backslashes():
    module = Module.assign(module_name="parser-test", alias=None, recommend_modules=None, developers=None)
    module.command_list.add(CommandMeta(command_template=parse_template(["add-regex <pattern>"])))
    parser = CommandParser(module, ["~"], module_name=module.module_name)

    unquoted = parser.parse(r"parser-test add-regex https://example\.test/\d+\\suffix")[1]
    quoted = parser.parse(r'parser-test add-regex "https://example\.test/a b"')[1]

    return (
        unquoted["<pattern>"] == r"https://example\.test/\d+\\suffix"
        and quoted["<pattern>"] == r"https://example\.test/a b"
    )


def _test_command_parser_preserves_quotes():
    module = Module.assign(module_name="parser-test", alias=None, recommend_modules=None, developers=None)
    module.command_list.add(CommandMeta(command_template=parse_template(["target data edit <k> <v>"])))
    parser = CommandParser(module, ["~"], module_name=module.module_name)

    double_quoted = parser.parse('parser-test target data edit config {"a": "b"}')[1]
    single_quoted = parser.parse("parser-test target data edit config {'a': 'b'}")[1]
    embedded = parser.parse('parser-test target data edit config a"b"c')[1]
    grouped = parser.parse('parser-test target data edit config "value with space"')[1]

    return (
        double_quoted["<v>"] == '{"a": "b"}'
        and single_quoted["<v>"] == "{'a': 'b'}"
        and embedded["<v>"] == 'a"b"c'
        and grouped["<v>"] == "value with space"
    )


def _build_option_parser():
    module = Module.assign(module_name="parser-test", alias=None, recommend_modules=None, developers=None)
    module.command_list.add(
        CommandMeta(command_template=parse_template(["search <keyword> [-p <page>]", "rc [--legacy]"]))
    )
    return CommandParser(module, ["~"], module_name=module.module_name)


def _test_command_parser_option_terminator():
    parser = _build_option_parser()

    escaped = parser.parse("parser-test search -- -p")[1]
    mixed = parser.parse("parser-test search -p 3 -- -v")[1]
    repeated = parser.parse("parser-test search -- -- -p")[1]

    return (
        escaped["-p"] is False
        and escaped["<keyword>"] == "-p"
        and mixed["-p"] == {"<page>": "3"}
        and mixed["<keyword>"] == "-v"
        and repeated["-p"] is False
        and repeated["<keyword>"] == "-- -p"
    )


def _test_command_parser_option_inline_value():
    parser = _build_option_parser()

    plain = parser.parse("parser-test search hello -p 3")[1]
    short = parser.parse("parser-test search hello -p=3")[1]
    quoted = parser.parse('parser-test search hello -p="5 1"')[1]
    empty = parser.parse("parser-test search hello -p=")[1]

    return (
        short["-p"] == {"<page>": "3"}
        and short["<keyword>"] == "hello"
        and short["-p"] == plain["-p"]
        and quoted["-p"] == {"<page>": "5 1"}
        and quoted["<keyword>"] == "hello"
        and empty["-p"] == {"<page>": ""}
        and empty["<keyword>"] == "hello"
    )


def _test_command_parser_option_missing_value():
    parser = _build_option_parser()

    missing = parser.parse("parser-test search hello -p")[1]
    bool_flag = parser.parse("parser-test rc --legacy")[1]
    bool_inline = parser.parse("parser-test rc --legacy=1")[1]

    return (
        missing["-p"] is False
        and missing["<keyword>"] == "hello -p"
        and bool_flag["--legacy"] is True
        and bool_inline["--legacy"] is False
    )


def _test_split_command_quotes():
    return (
        _split_command('parser-test add-regex "multi word" -t') == ["parser-test", "add-regex", "multi word", "-t"]
        and _split_command('parser-test add-regex {"a": "b"}') == ["parser-test", "add-regex", '{"a":', '"b"}']
        and _split_command('parser-test add-regex a"b"c') == ["parser-test", "add-regex", 'a"b"c']
        and _split_command("parser-test add-regex 'multi word'") == ["parser-test", "add-regex", "multi word"]
        and _split_command('parser-test add-regex "unbalanced') == ["parser-test", "add-regex", '"unbalanced']
        and _split_command(r"parser-test add-regex https://example\.test/\d+")
        == [
            "parser-test",
            "add-regex",
            r"https://example\.test/\d+",
        ]
    )


def _test_split_command_option_quotes():
    return (
        _split_command('parser-test search --foo="a b"') == ["parser-test", "search", "--foo=a b"]
        and _split_command("parser-test search --lang='zh cn'") == ["parser-test", "search", "--lang=zh cn"]
        and _split_command("parser-test search -p='3 1'") == ["parser-test", "search", "-p=3 1"]
        and _split_command('parser-test search --foo="a b"c') == ["parser-test", "search", '--foo="a', 'b"c']
        and _split_command('parser-test search key="a b"') == ["parser-test", "search", 'key="a', 'b"']
        and _split_command("parser-test search --foo='a b") == ["parser-test", "search", "--foo='a", "b"]
    )


async def _test_error_detail_markdown_format():
    session_info = SimpleNamespace(support_markdown=True)
    chain = await Bot.Hook.trigger(
        "parser_errors.format_error_detail",
        session_info=session_info,
        args={"text": "failure: `value`"},
    )
    return (
        len(chain.values) == 1
        and isinstance(chain.values[0], MarkdownElement)
        and chain.values[0].text == "```\nfailure: `value`\n```"
        and chain.values[0].allow_parse is False
    )


def _test_unwrap_option_value():
    return (
        _unwrap_option_value({"<bar>": "baz"}) == "baz"
        and _unwrap_option_value({}) == {}
        and _unwrap_option_value({"<start>": "1", "<end>": "9"}) == {"<start>": "1", "<end>": "9"}
        and _unwrap_option_value(True) is True
        and _unwrap_option_value(False) is False
    )


def _test_resolve_parsed_value():
    cases = [
        ({"<pagename>": "abc"}, "pagename", (True, "abc")),
        ({"list": True}, "list", (True, True)),
        ({"-b": True}, "b", (True, True)),
        ({"-b": False}, "b", (True, False)),
        ({"--foo": {"<bar>": "baz"}}, "foo", (True, "baz")),
        ({"--no-cover": True}, "no_cover", (True, True)),
        ({"--legacy": False}, "legacy", (True, False)),
        ({"-p": {"<page>": "3"}}, "page", (True, "3")),
        ({"-p": {"<page>": "1 3"}}, "page", (True, "1 3")),
        ({}, "missing", (False, None)),
    ]
    for parsed_msg, param_name, expected in cases:
        if _resolve_parsed_value(param_name, parsed_msg) != expected:
            return False
    return True


def _test_build_command_kwargs():

    class FakeBot:
        class MessageSession:
            pass

    async def command(msg: FakeBot.MessageSession, b: bool = False, foo: str | None = None, page: int = 1):
        pass

    async def single(msg: FakeBot.MessageSession):
        pass

    command_meta = SimpleNamespace(function=command)
    single_meta = SimpleNamespace(function=single)

    provided = SimpleNamespace(parsed_msg={"-b": True, "--foo": {"<bar>": "baz"}, "-p": {"<page>": "3"}})
    if _build_command_kwargs(command_meta, provided, FakeBot) != {
        "msg": provided,
        "b": True,
        "foo": "baz",
        "page": 3,
    }:
        return False

    missing = SimpleNamespace(parsed_msg={"-b": False, "--foo": False, "-p": False})
    if _build_command_kwargs(command_meta, missing, FakeBot) != {
        "msg": missing,
        "b": False,
        "foo": None,
        "page": 1,
    }:
        return False

    single_msg = SimpleNamespace(parsed_msg={"-b": True})
    if _build_command_kwargs(single_meta, single_msg, FakeBot) != {"msg": single_msg}:
        return False

    return True


@func_case
async def test_parser_args(tester: Tester):
    """core.builtins.parser.args: 参数解析测试"""
    await tester.test(_test_argument_pattern, "ArgumentPattern 创建测试")
    await tester.test(_test_desc_pattern, "DescPattern 创建测试")
    await tester.test(_test_template, "Template 创建测试")
    await tester.test(_test_template_priority, "Template 优先级测试")
    await tester.test(_test_optional_pattern, "OptionalPattern 创建测试")
    await tester.test(_test_split_multi_arguments, "split_multi_arguments 测试")
    await tester.test(_test_parse_template_simple, "parse_template 简单命令测试")
    await tester.test(_test_parse_template_optional, "parse_template 可选参数测试")
    await tester.test(_test_parse_template_description, "parse_template 描述测试")
    await tester.test(_test_parse_template_variadic, "parse_template 可变长参数测试")
    await tester.test(_test_parse_template_multiple, "parse_template 多个模板测试")
    await tester.test(_test_templates_to_str, "templates_to_str 测试")
    await tester.test(_test_templates_to_str_with_desc, "templates_to_str 带描述测试")
    await tester.test(_test_default_command_help_doc, "无文档模块默认命令帮助测试")
    await tester.test(_test_split_command_quotes, "命令分词引号测试")
    await tester.test(_test_split_command_option_quotes, "命令分词选项内联值引号测试")
    await tester.test(_test_command_parser_preserves_quotes, "命令参数引号保留测试")
    await tester.test(_test_command_parser_option_terminator, "命令选项终止符测试")
    await tester.test(_test_command_parser_option_inline_value, "命令选项内联值测试")
    await tester.test(_test_command_parser_option_missing_value, "命令选项缺少值测试")
    await tester.test(_test_command_parser_preserves_backslashes, "命令参数反斜杠保留测试")
    await tester.test(_test_error_detail_markdown_format, "Markdown 错误详情代码块测试")
    await tester.test(_test_unwrap_option_value, "选项子参数解包测试")
    await tester.test(_test_resolve_parsed_value, "命令参数取值映射测试")
    await tester.test(_test_build_command_kwargs, "命令参数构建与选项注入测试")

    return tester
