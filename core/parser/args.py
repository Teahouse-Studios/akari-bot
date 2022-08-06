import re
import traceback
from typing import List, Union, Dict

from core.exceptions import InvalidTemplatePattern, InvalidCommandFormatError


class Pattern:
    pass


class Template:
    def __init__(self, args: List[Pattern], priority: int = 1):
        self.args = args
        self.priority = priority

    def __str__(self):
        return 'Template({})'.format(self.args)

    def __repr__(self):
        return self.__str__()


class ArgumentPattern(Pattern):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return 'ArgumentPattern("{}")'.format(self.name)

    def __repr__(self):
        return self.__str__()


class OptionalPattern(Pattern):
    def __init__(self, flag: str, args: List[Template]):
        self.flag = flag
        self.args = args

    def __str__(self):
        return 'OptionalPattern("{}", {})'.format(self.flag, self.args)

    def __repr__(self):
        return self.__str__()


class Argument:
    def __init__(self, value: str):
        self.value = value


class Optional:
    def __init__(self, args: Dict[str, dict], flagged=False):
        self.flagged = flagged
        self.args = args


class MatchedResult:
    def __init__(self, args: dict, original_template, priority: int = 1):
        self.args = args
        self.original_template = original_template
        self.priority = priority

    def __str__(self):
        return 'MatchedResult({}, {})'.format(self.args, self.priority)

    def __repr__(self):
        return self.__str__()


def split_multi_arguments(lst: list):
    new_lst = []
    for x in lst:
        spl = list(filter(None, re.split(r"(\(.*?\))", x)))
        if len(spl) > 1:
            for y in spl:
                index_y = spl.index(y)
                mat = re.match(r"\((.*?)\)", y)
                if mat:
                    spl1 = mat.group(1).split('|')
                    for s in spl1:
                        cspl = spl.copy()
                        cspl.insert(index_y, s)
                        del cspl[index_y + 1]
                        new_lst.append(''.join(cspl))
        else:
            mat = re.match(r"\((.*?)\)", spl[0])
            if mat:
                spl1 = mat.group(1).split('|')
                for s in spl1:
                    new_lst.append(s)
            else:
                new_lst.append(spl[0])
    split_more = False
    for n in new_lst:
        if re.match(r"\((.*?)\)", n):
            split_more = True
    if split_more:
        return split_multi_arguments(new_lst)
    else:
        return list(set(new_lst))


def parse_template(argv: List[str]) -> List[Template]:
    templates = []
    argv_ = []
    for a in argv:
        if isinstance(a, str):
            spl = split_multi_arguments([a])
            for split in spl:
                argv_.append(split)

    for a in argv_:
        template = Template([])
        patterns = filter(None, re.split(r'(\[.*?])|(<.*?>)|(\{.*?})| ', a))
        for p in patterns:
            strip_pattern = p.strip()
            if strip_pattern == '':
                continue
            if strip_pattern.startswith('['):
                if not strip_pattern.endswith(']'):
                    raise InvalidTemplatePattern(p)
                optional_patterns = strip_pattern[1:-1].split(' ')
                template.args.append(OptionalPattern(flag=optional_patterns[0],
                                                     args=parse_template([' '.join(optional_patterns[1:]).strip()]) if len(
                                                  optional_patterns) > 1 else []))
            elif strip_pattern.startswith('{'):
                if not strip_pattern.endswith('}'):
                    raise InvalidTemplatePattern(p)
            else:
                if strip_pattern.startswith('<') and not strip_pattern.endswith('>'):
                    raise InvalidTemplatePattern(p)
                template.args.append(ArgumentPattern(strip_pattern))
        templates.append(template)
    return templates


def parse_argv(argv: List[str], templates: List[Template]) -> MatchedResult:
    matched_result = []
    for template in templates:
        try:
            argv_copy = argv.copy()  # copy argv to avoid changing original argv
            parsed_argv = {}
            original_template = template
            for a in template.args:  # optional first
                if isinstance(a, OptionalPattern):
                    parsed_argv[a.flag] = Optional({}, flagged=False)
                    if a.flag in argv_copy:  # if flag is in argv
                        if not a.args:  # no args
                            parsed_argv[a.flag] = Optional({}, flagged=True)
                            argv_copy.remove(a.flag)
                        else:  # has args
                            index_flag = argv_copy.index(a.flag)
                            len_t_args = len(a.args[0].args)
                            if len(argv_copy[index_flag:]) >= len_t_args:
                                sub_argv = argv_copy[index_flag + 1: index_flag + len_t_args + 1]
                                parsed_argv[a.flag] = Optional(parse_argv(sub_argv, a.args).args, flagged=True)
                                del argv_copy[index_flag: index_flag + len_t_args + 1]
                    template.args.remove(a)
            for a in template.args:
                if isinstance(a, ArgumentPattern):
                    if a.name.startswith('<'):
                        if len(argv_copy) > 0:
                            parsed_argv[a.name] = Argument(argv_copy[0])
                            del argv_copy[0]
                        else:
                            parsed_argv[a.name] = False
                    else:
                        parsed_argv[a.name] = a.name in argv_copy
                        if parsed_argv[a.name]:
                            argv_copy.remove(a.name)
            if argv_copy:  # if there are still some argv left
                last_template_arguments = original_template.args[-1]
                if isinstance(last_template_arguments, ArgumentPattern):
                    if last_template_arguments.name.startswith('<'):  # if last arg is variable
                        parsed_argv[list(parsed_argv.keys())[-1]].value += ' ' + ' '.join(argv_copy)
                        del argv_copy[0]
            matched_result.append(MatchedResult(parsed_argv, original_template, template.priority))
        except TypeError:
            traceback.print_exc()
            continue
    filtered_result = []
    for m in matched_result:  # convert to result dict
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
            elif isinstance(args_[keys], bool):
                if not args_[keys]:
                    filtered = True
                    break
        if not filtered:
            filtered_result.append(m)
    if (len_filtered_result := len(filtered_result)) > 1:  # if multiple result, select one by priority
        priority_result = {}
        for f in filtered_result:
            priority = f.priority  # base priority
            for keys in f.args:  # add priority for each argument
                if f.args[keys] is True:  # if argument is not any else
                    priority += 1
            if priority not in priority_result:
                priority_result[priority] = [f]
            else:
                priority_result[priority].append(f)
        return priority_result[max(priority_result.keys())][0]
    elif len_filtered_result == 0:
        raise InvalidCommandFormatError
    else:
        return filtered_result[0]
