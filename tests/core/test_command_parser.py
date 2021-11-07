from core.parser.command import CommandParser

def test_command_parser():
    parser = CommandParser(('~wiki <PageName> {搜索一个Wiki页面}',
                   '~wiki random {从Wiki获取随机页面}',
                   '~wiki set <WikiUrl> {设置起始查询Wiki}',
                   '~wiki iw (add|set) <Interwiki> <WikiUrl> {添加自定义Interwiki}',
                   '~wiki iw (del|delete|remove|rm) <Interwiki> {删除自定义Interwiki}',
                   '~wiki headers add <Headers> {添加自定义headers}',
                   '~wiki headers delete <HeaderKey> {删除一个headers}',
                   '~wiki headers reset {重置headers}'))
    assert parser.parse('~wiki iw') == {
            '<HeaderKey>': None,
            '<Headers>': None,
            '<Interwiki>': None,
            '<PageName>': 'iw',
            '<WikiUrl>': None,
            'add': False,
            'del': False,
            'delete': False,
            'headers': False,
            'iw': False,
            'random': False,
            'remove': False,
            'reset': False,
            'rm': False,
            'set': False
        }
