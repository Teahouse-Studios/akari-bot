from config import Config


def qq_frame_type() -> str:
    '''获取正在使用的QQ机器人框架'''
    frame_type = Config('qq_frame_type', 'mirai').lower()
    ntqq_lst = ['ntqq', 'lagrange', 'llonebot', 'napcat', 'napcatqq', ]
    shamrock_lst = ['shamrock', 'openshamrock', ]
    mirai_lst = ['mirai', 'gocq', 'gocqhttp', 'go-cqhttp', ]

    if frame_type in ntqq_lst or Config('use_llonebot', False):
        return 'ntqq'
    elif frame_type in shamrock_lst or Config('use_shamrock', False):
        return 'shamrock'
    elif frame_type in mirai_lst:
        return 'mirai'
    else:
        return ''