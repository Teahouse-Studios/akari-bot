import re

from .ctr_results import modules as ctr_results_modules
from .types import Module, ResultInfo, ConsoleErrorInfo, ConsoleErrorField, \
    BANNED_FIELD, WARNING_COLOR, UNKNOWN_CATEGORY_DESCRIPTION

"""
This file contains all currently known 2DS/3DS support codes.
There may be inaccuracies here; we'll do our best to correct them
when we find out more about them.

A "support" code, in contrast to a result code, is a human-readable string like
002-0102. They're meant to be more user-friendly than result codes, which are
typically integer values.

Note: the "modules" presented here are more like "categories". However, this difference
isn't enough to justify creating a different class with the same logic, so we'll just
refer to them as "modules" from now on.

To add a module/category so the code understands it, simply add a new module number
to the 'modules' dictionary, with a Module variable as the value. If the module
has no known error codes, simply add a dummy Module instead (see the dict for
more info). See the various module variables for a more in-depth example
 on how to make one.

Once you've added a module, or you want to add a new support code to an existing
module, add a new description value (for 3DS it's the 4 digit number after the dash)
as the key, and a ResultInfo variable with a text description of the error or result.
You can also add a second string to the ResultInfo to designate a support URL if
one exists. Not all support codes have known error pages.

Simple example of adding a module with a sample support code:
test = Module('test', {
    5: ResultInfo('test', 'https://example.com')
})

modules = {
    9999: test
}

Sources used to compile this information:
Kurisu's previous err.py module
Ninendo's support knowledgebase at https://en-americas-support.nintendo.com/app/answers
"""

# 001: friends module, parental controls, online services in general?
friends = Module('friends', {
    102: ResultInfo('此错误代表你从网络服务意外掉线。',
                    'https://en-americas-support.nintendo.com/app/answers/detail/a_id/17043'),
    721: ResultInfo('此错误代表监护人已设置严格限制网络功能。', 'https://www.nintendo.com.au/help/3ds-error-codes'),
    803: ResultInfo('This error code indicates that the online play server is currently down.',
                    'https://www.nintendo.co.jp/netinfo/en_US/index.html'),
    811: ResultInfo('This error code indicates that the online play server is undergoing maintenance.',
                    'https://www.nintendo.co.jp/netinfo/en_US/index.html')
})

# 002: bans and other account errors
account = Module('account', {
    102: ResultInfo('此主机已被任天堂永久封禁。', is_ban=True),
    107: ResultInfo('此主机已被任天堂暂时（？）封禁。', is_ban=True),
    110: ResultInfo('当使用已放弃支持的youtube 3ds版时出现。'),
    119: ResultInfo('需要系统更新。这个会在好友模块版本已过时时出现。'),
    120: ResultInfo('游戏或应用需要更新。这个会在你启动的游戏或程序版本已过时时出现。'),
    121: ResultInfo('Local friend code SEED的签证非法。这个应只在其被修改时出现。', is_ban=True),
    123: ResultInfo('此主机已被任天堂永久封禁。', is_ban=True)
})

# 003: connection related errors
internet = Module('internet', {
    299: ResultInfo('无线开关已关闭，请打开无线开关。'),
    399: ResultInfo('接受的EULA版本太低。'),
    1099: ResultInfo('给定SSID的接入点未找到。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4249/kw/003-1099'),
    1101: ResultInfo('错误的接入点密码或配置不兼容3DS'),
    2001: ResultInfo('DNS错误，如果你正在使用自定义DNS服务器，请确保设置正确。'),
    2103: ResultInfo('常见的连接错误（？')
})

# Yet another nim hack. Why does this category have so many redundant errors?
NIM_4069 = ResultInfo('这个错误可能会在eShop不可用时出现。如果此问题一直出现，则可能你需要为主机更换一张内存卡。',
                      'https://en-americas-support.nintendo.com/app/answers/detail/a_id/14413'),

# 005: nim
nim = Module('nim', {
    # 005-2008 is the same as 007-2920 and 009-2920...
    2008: ResultInfo(
        '这个错误通常会在eShop下载错误时发生，或是应用使用了非法的ticket。使用FBI删除这个应用和它的ticket，然后从合法途径重新下载游戏；若是卡带导出的游戏，则建议删除后只使用卡带玩游戏。',
        'https://en-americas-support.nintendo.com/app/answers/detail/a_id/41692'),
    4040: ResultInfo('连接eShop超时。', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4429'),
    4069: NIM_4069,
    # in HTTP range...
    4240: ResultInfo('这个错误可能代表eShop发生了暂时性的服务问题。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/28399'),
    4305: ResultInfo('这个错误常见于你从eShop下载软件的时候连接超时。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4346'),
    4320: ResultInfo('这个错误常见于尝试初始化系统或数据迁移。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/48382'),
    5602: ResultInfo('无法连接至eShop。这个错误通常代表系统区域设置不正确，请在系统设置中重新设置区域，然后再试一次。'),
    5687: ResultInfo('这个错误常见于你无法连接至eShop。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/26251/'),
    # in SOAP range...
    5704: ResultInfo('这个错误常见于你无法连接至eShop。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/26252'),
    5958: ResultInfo('未知的eShop错误，常见于改区后的机子。'),
    5964: ResultInfo('你的NNID已经被eShop封禁。如果你不服，建议去联系任天堂支持。'),
    7545: NIM_4069,
    7550: NIM_4069,
    8025: NIM_4069,
    8026: NIM_4069,
    8029: NIM_4069
})
# 006: online matchmaking and gameplay errors
matchmaking = Module('matchmaking', {
    112: ResultInfo('常见于连接宝可梦银行发生错误。',
                    'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4203/'),
    332: ResultInfo('可能发生于尝试使用关闭的端口进行通讯（？）'),
    (501, 502): ResultInfo('可能发生于网络对在线游戏阻断通讯。',
                           'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4204'),
    612: ResultInfo('这个错误代码可能表示你的网络环境不适合进行端对端通讯，可能与你的网络NAT类型有关。',
                    'https://en-americas-support.nintendo.com/app/answers/detail/a_id/25881'),
    811: ResultInfo('这个错误表示你正在尝试进行的网络请求不可用，因为网络服务此时开始维护。',
                    'https://en-americas-support.nintendo.com/app/answers/detail/a_id/25910/'),
    (800, 899): ResultInfo('常见于配对过程中发生错误且你无法连接到身份验证服务器时。',
                           'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4328/')
})

# 007: errors related to (presumably) the eShop API
eshop_mint = Module(
    'eshop (mint/api?)',
    {
        200: ResultInfo(
            '无法访问SD卡。',
            'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4234'),
        1221: ResultInfo(
            '你输入的下载码只能用来在对应程序兑换。它不能在eShop兑换。',
            'https://en-americas-support.nintendo.com/app/answers/detail/a_id/14600'),
        2001: ResultInfo('当你改区后访问eShop就会发生此错误，目前解决它的唯一办法就是改回去。'),
        2100: ResultInfo(
            '连接eShop超时。此错误代码通常出现于网络连接质量较差或受到了某网络组织的干扰。',
            '参见支持页面：https://en-americas-support.nintendo.com/app/answers/detail/a_id/4432\n或任天堂网络状态：https://support.nintendo.com/networkstatus'),
        2670: ResultInfo(
            '尝试连接时发生错误。',
            'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4383'),
        2720: ResultInfo('eShop SSL证书错误。'),
        2913: ResultInfo(
            '服务器可能离线，稍后再试。',
            'https://en-americas-support.nintendo.com/app/answers/detail/a_id/10425'),
        2916: ResultInfo(
            '常见于从eShop下载软件时错误。',
            'https://en-americas-support.nintendo.com/app/answers/detail/a_id/6557'),
        2920: ResultInfo(
            '这个错误通常会在eShop下载错误时发生，或是应用使用了非法的ticket。使用FBI删除这个应用和它的ticket，然后从合法途径重新下载游戏；若是卡带导出的游戏，则建议删除后只使用卡带玩游戏。',
            'https://en-americas-support.nintendo.com/app/answers/detail/a_id/41692'),
        2924: ResultInfo('出现于使用无效的语言设置打开eShop。'),
        3049: ResultInfo(
            'eShop已停服维护。',
            'https://support.nintendo.com/networkstatus/'),
        6106: ResultInfo('常见于从eShop重新下载带有非法或无效ticket的软件时。')})

# 009: errors related to (presumably) the eShop application itself
eshop_app = Module('eshop (app?)', {
    # 1001: ResultInfo('The eShop is down for maintenance.',
    # 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/45399'),
    1000: ResultInfo('需要系统更新（好友模块？）。'),
    1001: eshop_mint.data[3049],
    2705: ResultInfo('此错误经常于eShop网络连接超时或丢失时出现。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/14478'),
    2913: ResultInfo('一个位于eShop或游戏内的DLC下载失败（或服务器离线）。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/7243'),
    2916: eshop_mint.data[2916],
    2920: eshop_mint.data[2920],
    2924: eshop_mint.data[2924],
    2923: ResultInfo('你无法使用需要联网的功能，例如软件更新和初始化主机。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/17014'),
    2995: ResultInfo('这个错误可能出现于下载码输入错误（已激活、失效、输错和区域不对等）。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/13515'),
    4077: ResultInfo(
        '无法开始或继续eShop下载。会在SD卡没有充足空间的时候出现。'),
    4079: ResultInfo('无法访问内存卡。'),
    4998: ResultInfo('本地内容比服务器的更新，鬼知道为什么会这样。'),
    6106: ResultInfo('NIM的AM报错，可能是坏ticket惹的祸。'),
    8401: ResultInfo('升级数据错误，删了然后重新下载它。'),
    9001: ResultInfo('主机电量不足的时候尝试下载内容时出现。')
})

# 011: eshop website, or other misc/overlapping errors
eshop_site = Module('eshop (website?)', {
    3010: ResultInfo('由于用户不活跃导致的服务器响应超时。'),
    3021: ResultInfo('无法在eShop找到这个应用（错误的区域或者这个东西就根本不存在）'),
    3136: ResultInfo('eShop不可用，等会再试。'),
    5998: ResultInfo('任天堂eShop正在维护中。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/24326/'),
    6901: ResultInfo('此主机已被任天堂永久封禁（由于某种原因只显示日文）。', is_ban=True)
})

# 014: system transfers?
data_transfer = Module('system transfer', {
    13: ResultInfo('尝试使用无效的语言设定时进行数据迁移。'),
    16: ResultInfo('两个主机拥有同样的movable.sed，初始化准备迁移数据到的主机然后再试一次。'),
    62: ResultInfo('数据迁移时发生了错误，将它们靠近路由器然后再试。',
                   'https://en-americas-support.nintendo.com/app/answers/detail/a_id/15664')
})
# 012: a category related to the web browser or ssl module considered 1511
browser1 = Module('browser (?)', {
    1004: ResultInfo('SSL连接失败。'),
    1511: ResultInfo('证书警告。')
})

# 032: a second category related to the web browser
browser2 = Module('browser (?)', {
    1820: ResultInfo('于你想访问一个危险的网站时出现。如果你是秋名山车神就直接确认。')
})

# 022: more account stuff?
account2 = Module('account', {
    2452: ResultInfo('在你打开了UNITINFO补丁后访问eShop时出现，在Luma设置中关闭。'),
    2501: ResultInfo(
        'NNID已绑定到另外一台主机，可能是由于使用了数据迁移（与系统关联的NNID都已被移动至新主机）后将备份的NAND还原并尝试进入需要NNID的程序。'),
    2511: ResultInfo('需要系统更新（可能出现于Miiverse？）。'),
    2591: ResultInfo(
        'NNID已绑定到另外一台主机，可能是由于使用了数据迁移（与系统关联的NNID都已被移动至新主机）后将备份的NAND还原并尝试进入需要NNID的程序。'),
    2613: ResultInfo('绑定NNID时输入了错误的邮箱或密码，或是在没有绑定NNID的情况下从eShop下载软件时出现。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4314/kw/022-2613'),
    2631: ResultInfo('你输入的NNID已被注销，或是因为数据迁移不可用。数据迁移后NNID只会在迁入的主机可用。',
                     'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4285/kw/022-2631'),
    2633: ResultInfo('NNID已因过多的错误密码尝试而被暂时锁定。稍后再试。'),
    2634: ResultInfo('NNID没有正确绑定主机。',
                     '如果你想修复它，使用这个教程：https://3ds.hacks.guide/zh_CN/godmode9-usage#%E5%9C%A8%E4%B8%8D%E5%88%9D%E5%A7%8B%E5%8C%96%E4%B8%BB%E6%9C%BA%E7%9A%84%E6%83%85%E5%86%B5%E4%B8%8B%E6%B8%85%E9%99%A4-nnid'),
    2812: ResultInfo('此主机由于在宝可梦日月发售日前偷跑联网而被永久封禁。', is_ban=True),
    2815: ResultInfo('此主机的Miiverse功能已被任天堂封禁。'),
    5363: ResultInfo('出现于设置了无效的语言后加载NNID设置。'),
    5515: ResultInfo('网络连接超时。'),
})

# 090: application defined?
unknown1 = Module('unknown', {
    212: ResultInfo('此游戏的PGL功能已因使用了修改或非法的存档而被永久封禁。', is_ban=True)
})

# We have some modules partially documented, those that aren't return None.
# These category names are largely made up based on the types of known errors they have,
# or based on their Wii U-equivalent, because Wii U is better documented.
modules = {
    1: friends,
    2: account,
    3: internet,
    5: nim,
    6: matchmaking,
    7: eshop_mint,
    9: eshop_app,
    11: eshop_site,
    12: browser1,
    14: data_transfer,
    22: account2,
    32: browser2,
    90: unknown1
}

RE = re.compile(r'0\d{2}-\d{4}')

CONSOLE_NAME = 'Nintendo 2DS/3DS'

# Suggested color to use if displaying information through a Discord bot's embed
COLOR = 0xCE181E


def is_valid(error: str):
    return RE.match(error)


def construct_result(ret, mod, desc):
    module = ctr_results_modules.get(mod, Module(''))
    ret.add_field(ConsoleErrorField('模组', message_str=module.name, supplementary_value=mod))
    description = module.get_error(desc)
    if not description or not description.description:
        description = ctr_results_modules[0].get_error(desc)
        if not description or not description.description:
            ret.add_field(ConsoleErrorField('描述', supplementary_value=desc))
        else:
            ret.add_field(ConsoleErrorField('描述', message_str=description.description, supplementary_value=desc))
    else:
        ret.add_field(ConsoleErrorField('描述', message_str=description.description, supplementary_value=desc))

    return ret


def construct_result_range(ret, mod, range_desc):
    module = ctr_results_modules.get(mod, Module(''))
    ret.add_field(ConsoleErrorField('模组', message_str=module.name, supplementary_value=mod))
    found_descs = []
    unknown_descs = []
    for desc in range_desc:
        if desc < 0 or desc > 1023:
            continue

        description = module.get_error(desc)
        if not description or not description.description:
            description = ctr_results_modules[0].get_error(desc)
            if not description or not description.description:
                unknown_descs.append(str(desc))
            else:
                found_descs.append(
                    ConsoleErrorField('描述', message_str=description.description, supplementary_value=desc).message)
        else:
            found_descs.append(
                ConsoleErrorField('描述', message_str=description.description, supplementary_value=desc).message)

    if found_descs:
        ret.add_field(ConsoleErrorField('可能已知描述', message_str='\n'.join(found_descs)))
    if unknown_descs:
        ret.add_field(ConsoleErrorField('可能未知描述', message_str=', '.join(unknown_descs)))

    return ret


def construct_support(ret, mod, desc):
    category = modules.get(mod, Module(''))
    if category.name:
        ret.add_field(ConsoleErrorField('分类', message_str=category.name))
    else:
        ret.add_field(ConsoleErrorField('分类', supplementary_value=mod))
    description = category.get_error(desc)
    if description and description.description:
        ret.add_field(ConsoleErrorField('描述', message_str=description.description))
        if description.support_url:
            ret.add_field(ConsoleErrorField('更多描述', message_str=description.support_url))
        if description.is_ban:
            ret.add_field(BANNED_FIELD)
            ret.color = WARNING_COLOR
    else:
        ret.add_field(UNKNOWN_CATEGORY_DESCRIPTION)
    return ret


def nim_handler(ret, description):
    """
    Parses 3ds nim error codes in the following ranges:
    005-2000 to 005-3023:
     - NIM got a result of its own. Took description and added by 52000.
    005-4200 to 005-4399:
     - NIM got an HTTP result. Took description and added by 54200, cutting out at 54399 if it was beyond that.
    005-4400 to 005-4999:
     - Range of HTTP codes, however, can suffer collision.
    005-5000 to 005-6999:
     - SOAP Error Code range, when <ErrorCode> is not 0 on the SOAP responses.
    005-7000 to 005-9999:
     - Non specific expected results are formatted to an error code in nim by taking result module and shifting right by 5, and taking the result description and masked with 0x1F, then added both together along with 57000.
    """
    # If we have a specific description for it in our knowledgebase,
    # show it instead of doing the rest of the processing.
    error = nim.get_error(description)
    if error and error.description:
        return construct_support(ret, 5, description)

    elif 2000 <= description < 3024:
        description -= 2000
        return construct_result(ret, 52, description)  # nim result module, not support category

    elif 4200 <= description < 4400:
        description -= 4200
        construct_result(ret, 40, description)  # http result module, not support category
        if description == 199:
            ret.add_field(ConsoleErrorField('扩展信息', message_str='或者超过199的http描述会被NIM截断为199。'))

    elif 4400 <= description < 5000:
        description -= 4400
        ret.add_field(ConsoleErrorField('分类', message_str='nim'))
        if description < 100:
            ret.add_field(ConsoleErrorField('HTTP状态码', message_str=f'{description + 100}'))
        elif 100 <= description < 500:
            ret.add_field(
                ConsoleErrorField('HTTP状态码', message_str=f'{description + 100}或{description}由于NIM中的编程错误。'))
        else:
            ret.add_field(ConsoleErrorField('HTTP状态码', message_str=f'{description}'))

    elif 5000 <= description < 7000:
        description -= 5000
        ret.add_field(ConsoleErrorField('分类', message_str='nim'))
        ret.add_field(ConsoleErrorField('描述', message_str=f'NIM活动时SOAP消息返回了状态码{description}'))

    # >= 7000 range is compacted
    elif description >= 7000:
        description -= 7000
        module = description >> 5
        # There are way more than 0x1F descriptions, but this is how Nintendo does it...
        description = description & 0x1F
        return construct_result_range(ret, module, range(0 + description, 1024 + description, 32))

    else:
        ret.add_field(ConsoleErrorField('分类', message_str='nim'))
        ret.add_field(UNKNOWN_CATEGORY_DESCRIPTION)

    return ret


def get(error: str):
    mod = int(error[:3])
    desc = int(error[4:])
    ret = ConsoleErrorInfo(error, CONSOLE_NAME, COLOR)
    if mod == 5:  # 5 is NIM
        return nim_handler(ret, desc)
    return construct_support(ret, mod, desc)
