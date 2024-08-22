from .types import Module, ResultInfo, ConsoleErrorInfo, ConsoleErrorField

"""
This file contains all currently known 2DS/3DS result and error codes (hexadecimal).
There may be inaccuracies here; we'll do our best to correct them
when we find out more about them.

A result code is a 32-bit integer returned when calling various commands in the
3DS's operating system, Horizon. Its breaks down like so:

 Bits | Description
-------------------
00-09 | Description
10-17 | Module
21-26 | Summary
27-31 | Level

Description: A value indicating exactly what happened.
Module: A value indicating who raised the error or returned the result.
Summary: A value indicating a shorter description of what happened.
Level: A value indicating the severity of the issue (fatal, temporary, etc.).

The 3DS makes it simple by providing all of these values directly. Other
consoles, such as the Wii U and Switch do not provide summaries or levels, so
those fields in the ResultInfo class are re-used for other similar purposes.

To add a module so the code understands it, simply add a new module number
to the 'modules' dictionary, with a Module variable as the value. If the module
has no known error codes, simply add a dummy Module instead (see the dict for
more info). See the various module variables for a more in-depth example
 on how to make one.

Once you've added a module, or you want to add a new result code to an existing
module, add a new description value (for 3DS it's the 4 digit number after the dash)
as the key, and a ResultInfo variable with a text description of the error or result.
You can also add a second string to the ResultInfo to designate a support URL if
one exists. Not all results or errors have support webpages.

Simple example of adding a module with a sample result code:
test = Module('test', {
    5: ResultInfo('test', 'https://example.com')
})

modules = {
    9999: test
}

Sources used to compile these results and information:
https://www.3dbrew.org/wiki/Error_codes
Kurisu's previous err.py module

TODO: Add a number of result codes that were in the previous result code Kurisu
used. They were left out for the sake of getting this initial code done faster.
"""

common = Module('common', {
    0: ResultInfo('Success'),
    1000: ResultInfo('无效的选择'),
    1001: ResultInfo('过大'),
    1002: ResultInfo('未授权'),
    1003: ResultInfo('已经完成'),
    1004: ResultInfo('无效大小'),
    1005: ResultInfo('无效枚举值'),
    1006: ResultInfo('无效组合'),
    1007: ResultInfo('无数据'),
    1008: ResultInfo('忙碌'),
    1009: ResultInfo('位址偏移'),
    1010: ResultInfo('大小偏移'),
    1011: ResultInfo('内存溢出'),
    1012: ResultInfo('未生效'),
    1013: ResultInfo('无效地址'),
    1014: ResultInfo('无效指针'),
    1015: ResultInfo('无效标头'),
    1016: ResultInfo('未初始化'),
    1017: ResultInfo('已初始化'),
    1018: ResultInfo('未找到'),
    1019: ResultInfo('请求取消'),
    1020: ResultInfo('已存在'),
    1021: ResultInfo('数组越界'),
    1022: ResultInfo('超时'),
    1023: ResultInfo('无效结果')
})

kernel = Module('kernel', {
    2: ResultInfo('无效的内存权限。')
})

os = Module('os', {
    10: ResultInfo('内存不足。'),
    26: ResultInfo('远端关闭了会话。'),
    47: ResultInfo('非法的命令标头。')
})

fs = Module('fs', {
    101: ResultInfo('档案未挂载或挂载点未找到。'),
    120: ResultInfo('应用或对象未找到。'),
    141: ResultInfo('卡带未插入。'),
    230: ResultInfo('非法的开启标识或权限。'),
    391: ResultInfo('NCCH hash检查失败。'),
    302: ResultInfo('RSA或AES-MAC校验失败。'),
    395: ResultInfo('RomFS或Savedata hash检查失败。'),
    630: ResultInfo('命令未被允许或缺失权限。'),
    702: ResultInfo('无效路径。'),
    761: ResultInfo('不正确的ExeFS读取大小。'),
    (100, 179): ResultInfo('[媒体]未找到。'),
    (180, 199): ResultInfo('已存在。'),
    (200, 219): ResultInfo('空间不足。'),
    (220, 229): ResultInfo('无效档案。'),
    (230, 339): ResultInfo('不允许或写保护。'),
    (360, 389): ResultInfo('格式错误。'),
    (390, 399): ResultInfo('校验失败。'),
    (600, 629): ResultInfo('资源溢出。'),
    (630, 660): ResultInfo('权限不足。'),
    (700, 729): ResultInfo('无效参数。'),
    (730, 749): ResultInfo('未初始化。'),
    (750, 759): ResultInfo('已初始化。'),
    (760, 779): ResultInfo('不支持。')
})

srv = Module('srv', {
    5: ResultInfo('无效的文字长度（服务名称需要在0-8个字符之间）。'),
    6: ResultInfo('访问服务权限不足（有一个程序的服务没有得到对应的权限）。'),
    7: ResultInfo('文字长度不匹配内容（服务名称包含意料之外的未知字符）。')
})

nwm = Module('nwm', {
    2: ResultInfo('这个错误经常在无线模块（快/已）坏掉时出现。')
})

am = Module('am', {
    4: ResultInfo('非法的ticket版本。'),
    32: ResultInfo('空CIA。'),
    37: ResultInfo('无效的NCCH。'),
    39: ResultInfo('无效的程序版本，'),
    43: ResultInfo('数据库不存在或打开失败。'),
    44: ResultInfo('尝试卸载系统程序。'),
    106: ResultInfo('无效的签名/CIA。'),
    393: ResultInfo('无效的数据库。'),
})

http = Module('http', {
    105: ResultInfo('请求超时。')
})

nim = Module('nim', {
    1: ResultInfo('无效的IPC字符串参数（非null终止于其指示的长度）。'),
    12: ResultInfo('CFG模块在读取配置的0xB0000时返回了无效的地区代码。'),
    13: ResultInfo('CFG的SecureInfoGetSerialNo返回了零字符长度的序列号或“000000000000000”'),
    18: ResultInfo('读取在系统存档里的NIM的.dat文件发生了错误，数据损坏或数据长度不正确。'),
    22: ResultInfo('任天堂服务器返回了无效的数据或无效的数据长度。（仅适用某些操作）'),
    25: ResultInfo(
        'IntegrityVerificationSeed正在等待服务器同步主机。如果未先通过IPC请求完成同步，则无法于在线服务进行处理。'),
    26: ResultInfo(
        '任天堂服务器存有不可用/不允许的IntegrityVerificationSeed。可能在完成系统迁移后，NIM向服务器请求导入IntegrityVerificationSeed时出现。'),
    27: ResultInfo('CFG模块在读取配置的0xA0002时返回了无效的地区代码。'),
    37: ResultInfo('服务处于备用模式。（eShop封禁？常规服务离线？这于一服务器回应账户信息时出现。此账户和NNID不相关。'),
    39: ResultInfo('HTTP状态码非200。（仅适用某些操作）'),
    40: ResultInfo('处理自动传递XML时写入/读取错误。'),
    41: ResultInfo('处理自动传递XML时写入/读取错误。（Stubbed virtual call被调用）'),
    58: ResultInfo('CFG模块在读取配置的0xF0006时返回了无效的NPNS口令。'),
    67: ResultInfo('当下载游戏的seed时得到了404状态码。'),
    68: ResultInfo('当下载游戏的seed时得到了503状态码。')
})

mvd = Module('mvd', {
    271: ResultInfo('无效的配置。')
})

qtm = Module('qtm', {
    8: ResultInfo('相机正在工作或忙碌。')
})

# This is largely a dummy module, but FBI errors often get passed through the bot
# which return incorrect error strings. Since there's not really a feasible way to figure out the
# application which is throwing the error, this is the best compromise without giving the user
# false information.
application = Module('application-specific error', {
    (0, 1023): ResultInfo('程序抛出了错误。请向其他人请教源代码的问题或者向程序的作者发送报告。')
})

# We have some modules partially documented, those that aren't have dummy Modules.
modules = {
    0: common,
    1: kernel,
    2: Module('util'),
    3: Module('file server'),
    4: Module('loader server'),
    5: Module('tcb'),
    6: os,
    7: Module('dbg'),
    8: Module('dmnt'),
    9: Module('pdn'),
    10: Module('gsp'),
    11: Module('i2c'),
    12: Module('gpio'),
    13: Module('dd'),
    14: Module('codec'),
    15: Module('spi'),
    16: Module('pxi'),
    17: fs,
    18: Module('di'),
    19: Module('hid'),
    20: Module('cam'),
    21: Module('pi'),
    22: Module('pm'),
    23: Module('pm_low'),
    24: Module('fsi'),
    25: srv,
    26: Module('ndm'),
    27: nwm,
    28: Module('soc'),
    29: Module('ldr'),
    30: Module('acc'),
    31: Module('romfs'),
    32: am,
    33: Module('hio'),
    34: Module('updater'),
    35: Module('mic'),
    36: Module('fnd'),
    37: Module('mp'),
    38: Module('mpwl'),
    39: Module('ac'),
    40: http,
    41: Module('dsp'),
    42: Module('snd'),
    43: Module('dlp'),
    44: Module('hio_low'),
    45: Module('csnd'),
    46: Module('ssl'),
    47: Module('am_low'),
    48: Module('nex'),
    49: Module('friends'),
    50: Module('rdt'),
    51: Module('applet'),
    52: nim,
    53: Module('ptm'),
    54: Module('midi'),
    55: Module('mc'),
    56: Module('swc'),
    57: Module('fatfs'),
    58: Module('ngc'),
    59: Module('card'),
    60: Module('cardnor'),
    61: Module('sdmc'),
    62: Module('boss'),
    63: Module('dbm'),
    64: Module('config'),
    65: Module('ps'),
    66: Module('cec'),
    67: Module('ir'),
    68: Module('uds'),
    69: Module('pl'),
    70: Module('cup'),
    71: Module('gyroscope'),
    72: Module('mcu'),
    73: Module('ns'),
    74: Module('news'),
    75: Module('ro'),
    76: Module('gd'),
    77: Module('card spi'),
    78: Module('ec'),
    79: Module('web browser'),
    80: Module('test'),
    81: Module('enc'),
    82: Module('pia'),
    83: Module('act'),
    84: Module('vctl'),
    85: Module('olv'),
    86: Module('neia'),
    87: Module('npns'),
    90: Module('avd'),
    91: Module('l2b'),
    92: mvd,
    93: Module('nfc'),
    94: Module('uart'),
    95: Module('spm'),
    96: qtm,
    97: Module('nfp'),
    254: application,
}

levels = {
    0: 'Success',
    1: 'Info',
    25: 'Status',
    26: 'Temporary',
    27: 'Permanent',
    28: 'Usage',
    29: 'Reinitialize',
    30: 'Reset',
    31: 'Fatal'
}

summaries = {
    0: 'Success',
    1: 'Nothing happened',
    2: 'Would block',
    3: 'Out of resource',
    4: 'Not found',
    5: 'Invalid state',
    6: 'Not supported',
    7: 'Invalid argument',
    8: 'Wrong argument',
    9: 'Canceled',
    10: 'Status changed',
    11: 'Internal',
    63: 'Invalid result value'
}

CONSOLE_NAME = 'Nintendo 2DS/3DS'

# Suggested color to use if displaying information through a Discord bot's embed
COLOR = 0xCE181E


def is_valid(error: str):
    try:
        err_int = int(error, 16)
    except ValueError:
        return False
    return err_int >= 0 and err_int.bit_length() <= 32


def hexinfo(error: str):
    error.strip()
    err = int(error[2:], 16)
    desc = err & 0x3FF
    mod = (err >> 10) & 0xFF
    summary = (err >> 21) & 0x3F
    level = (err >> 27) & 0x1F
    return mod, summary, level, desc


def construct_result(ret, mod, summary, level, desc):
    module = modules.get(mod, Module(''))
    ret.add_field(ConsoleErrorField('Module', message_str=module.name, supplementary_value=mod))
    ret.add_field(ConsoleErrorField('Summary', message_str=summaries.get(summary, ''), supplementary_value=summary))
    ret.add_field(ConsoleErrorField('Level', message_str=levels.get(level, ''), supplementary_value=level))
    description = module.get_error(desc)
    if not description:
        description = common.get_error(desc)
        if not description:
            ret.add_field(ConsoleErrorField('Description', supplementary_value=desc))
        else:
            ret.add_field(
                ConsoleErrorField('Description', message_str=description.description, supplementary_value=desc))
    else:
        ret.add_field(ConsoleErrorField('Description', message_str=description.description, supplementary_value=desc))

    return ret


def get(error: str):
    ret = ConsoleErrorInfo(error, CONSOLE_NAME, COLOR)
    mod, summary, level, desc = hexinfo(error)
    return construct_result(ret, mod, summary, level, desc)
