from core.elements.others import command_prefix
from core.parser.command import CommandParser

c = CommandParser(('~wiki <PageName> {搜索一个Wiki页面}',
                   '~wiki random {从Wiki获取随机页面}',
                   '~wiki set <WikiUrl> {设置起始查询Wiki}',
                   '~wiki iw (add|set) <Interwiki> <WikiUrl> {添加自定义Interwiki}',
                   '~wiki iw (del|delete|remove|rm) <Interwiki> {删除自定义Interwiki}',
                   '~wiki headers add <Headers> {添加自定义headers}',
                   '~wiki headers delete <HeaderKey> {删除一个headers}',
                   '~wiki headers reset {重置headers}'), command_prefixes=command_prefix)

print(c.parse('~wiki iw'))
