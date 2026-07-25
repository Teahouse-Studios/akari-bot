"""core.builtins.parser 命令解析单元测试。"""

from core.builtins.parser.args import (
    ArgumentPattern,
    DescPattern,
    Template,
    OptionalPattern,
    split_multi_arguments,
    parse_template,
    templates_to_str,
)
from core.tester import func_case, Tester


def _test_argument_pattern():
    """测试 ArgumentPattern 创建"""
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
    """测试 DescPattern 创建"""
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
    """测试 Template 创建"""
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
    """测试 Template 优先级"""
    try:
        template = Template([ArgumentPattern("<arg>")], priority=5)
        if template.priority != 5:
            return False
        return True
    except Exception:
        return False


def _test_optional_pattern():
    """测试 OptionalPattern 创建"""
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
    """测试 split_multi_arguments 函数"""
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
    """测试 parse_template 简单命令"""
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
    """测试 parse_template 可选参数"""
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


def _test_parse_template_description():
    """测试 parse_template 描述"""
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
    """测试 parse_template 可变长参数"""
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
    """测试 parse_template 多个模板"""
    try:
        templates = parse_template(["<arg1>", "<arg1> <arg2>"])
        if len(templates) != 2:
            return False
        return True
    except Exception:
        return False


def _test_templates_to_str():
    """测试 templates_to_str 函数"""
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
    """测试 templates_to_str 带描述"""
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

    return tester
