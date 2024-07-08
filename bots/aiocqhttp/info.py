from config import Config

client_name = 'QQ'


def qq_frame_type() -> str:
    '''获取正在使用的QQ机器人框架'''
    frame_type = (Config('qq_frame_type', cfg_type=str) or '').lower()

    if frame_type in ['llonebot', 'napcat', 'napcatqq', ] or Config('use_llonebot', False):
        return 'ntqq'
    elif frame_type in ['shamrock', 'openshamrock', ] or Config('use_shamrock', False):
        return 'shamrock'
    else:
        return 'mirai'
