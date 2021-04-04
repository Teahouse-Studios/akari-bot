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
    102: ResultInfo('此错误代表你从网络服务意外掉线。', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/17043'),
    721: ResultInfo('此错误代表监护人已设置严格限制网络功能。', 'https://www.nintendo.com.au/help/3ds-error-codes')
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
    299: ResultInfo('The Wireless Connection is currently deactivated. Please activate the wireless connection.'),
    399: ResultInfo('Accepted EULA version is too low'),
    1099: ResultInfo('Access point with given SSID not found.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4249/kw/003-1099'),
    2001: ResultInfo('DNS error. If you\'re using a custom DNS server, make sure the settings are correct.')
})

# Yet another nim hack. Why does this category have so many redundant errors?
NIM_4069 = ResultInfo('This error may appear if the eShop is unavailable. If the issue persists, you might need to replace your console\'s SD card.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/14413'),

# 005: nim
nim = Module('nim', {
    # 005-2008 is the same as 007-2920 and 009-2920...
    2008: ResultInfo('This error is typically displayed when a Nintendo eShop download failed, or when the title has an invalid ticket. Delete the title and/or its ticket in FBI and install it again from a legitimate source like the Nintendo eShop, or from your game cartridges if using cart dumps.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/41692'),
    4040: ResultInfo('The connection timed out when connecting to the eShop.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4429'),
    4069: NIM_4069,
    # in HTTP range...
    4240: ResultInfo('This error code likely indicates a temporary service issue with the Nintendo eShop.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/28399'),
    4305: ResultInfo('A generic error that may be displayed when the connection times out or you are unable to download software from the eShop.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4346'),
    4320: ResultInfo('A generic error that may be displayed when formatting your console or performing a system transfer.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/48382'),
    5602: ResultInfo('Unable to connect to the eShop. This usually occurs when the System\'s region setting is incorrect. Change it in system settings and try connecting again.'),
    5687: ResultInfo('A generic error that displays when you\'re unable to connect to the eShop.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/26251/'),
    # in SOAP range...
    5704: ResultInfo('A generic error that displays when you\'re unable to connect to the eShop.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/26252'),
    5958: ResultInfo('Unknown eShop error. Usually seen on region-changed consoles.'),
    5964: ResultInfo('Your NNID has been banned from accessing the eShop. You will need to contact Nintendo Support if you feel it was unjustified.'),
    7545: NIM_4069,
    7550: NIM_4069,
    8025: NIM_4069,
    8026: NIM_4069,
    8029: NIM_4069
})
# 006: online matchmaking and gameplay errors
matchmaking = Module('matchmaking', {
    112: ResultInfo('Typically displayed when an issue with connecting to Pokémon Bank occurs.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4203/'),
    (501, 502): ResultInfo('This may indicate in issue with the network being used blocking traffic necessary for online play.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4204'),
    612: ResultInfo('This error code generally indicates that your network is not optimal for peer to peer connections, likely due to your network\'s NAT type.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/25881'),
    811: ResultInfo('This error code indicates the service you are attempting to use is currently unavailable due to ongoing maintenance.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/25910/'),
    (800, 899): ResultInfo('These are typically shown when there is an error during the matchmaking process and you were unable to connect to the authentication servers.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4328/')
})

# 007: errors related to (presumably) the eShop API
eshop_mint = Module('eshop (mint/api?)', {
    200: ResultInfo('Could not access the SD card.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4234'),
    1221: ResultInfo('The download code you entered can only be redeemed within the relevant software title. It cannot be redeemed in Nintendo eShop.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/14600'),
    2001: ResultInfo('Error when attempting to access eshop on a region changed console. Fixed by changing back to the console original region.'),
    2100: ResultInfo('The connection to the Nintendo eShop timed out. This error code is often times caused by slow download times due to interference or a slow Internet connection.', 'See [the support page](https://en-americas-support.nintendo.com/app/answers/detail/a_id/4432) or [Nintendo\'s network status](https://support.nintendo.com/networkstatus).'),
    2670: ResultInfo('An error occurred while attempting to connect.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4383'),
    2913: ResultInfo('The server is probably down. Try again later.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/10425'),
    2916: ResultInfo('This is typically displayed when an error occurs while attempting to download a title from the Nintendo eShop.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/6557'),
    2920: ResultInfo('This error is typically displayed when a Nintendo eShop download failed, or when the title has an invalid ticket. Delete the title and/or its ticket in FBI and install it again from a legitimate source like the Nintendo eShop, or from your game cartridges if using cart dumps.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/41692'),
    2924: ResultInfo('Happens when opening eshop with a invalid language setting'),
    3049: ResultInfo('The eShop is down for maintenance.', 'https://support.nintendo.com/networkstatus/'),
    6106: ResultInfo('Occurs when attempting to re-download software from the eshop with an invalid or fake ticket')
})

# 009: errors related to (presumably) the eShop application itself
eshop_app = Module('eshop (app?)', {
    # 1001: ResultInfo('The eShop is down for maintenance.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/45399'),
    1000: ResultInfo('System update required (friends module?).'),
    1001: eshop_mint.data[3049],
    2705: ResultInfo('This error code is often the result of the Internet connection timing out or losing connection with the Nintendo eShop.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/14478'),
    2913: ResultInfo('An eShop or in-game DLC download failed (or the server is down).', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/7243'),
    2916: eshop_mint.data[2916],
    2920: eshop_mint.data[2920],
    2924: eshop_mint.data[2924],
    2923: ResultInfo('You are unable to use a function which requires internet services, such as software updates or formatting the system memory.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/17014'),
    2995: ResultInfo('This error can occur if the download code was entered incorrectly, has not yet been activated, has expired, was entered in the wrong place, or is intended for a region other than your own.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/13515'),
    4079: ResultInfo('Unable to access SD card.'),
    4998: ResultInfo('Local content is newer. Unknown what causes this.'),
    6106: ResultInfo('AM error in NIM. Bad ticket is likely.'),
    8401: ResultInfo('The update data is corrupted. Delete it and reinstall.')
})

# 011: eshop website, or other misc/overlapping errors
eshop_site = Module('eshop (website?)', {
    3021: ResultInfo('Cannot find title on Nintendo eShop (incorrect region, or never existed?).'),
    3136: ResultInfo('Nintendo eShop is currently unavailable. Try again later.'),
    6901: ResultInfo('This console is permanently banned by Nintendo (displayed in Japanese for some reason).', is_ban=True)
})

# 014: system transfers?
data_transfer = Module('system transfer', {
    13: ResultInfo('Attempting to do a system transfer with with a invalid language setting.'),
    16: ResultInfo('Both consoles have the same movable.sed key. Format the target console and system transfer again.'),
    62: ResultInfo('An error occurred during system transfer. Move closer to the wireless router and try again.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/15664')
})
# 012: a category related to the web browser or ssl module considered 1511
browser1 = Module('browser (?)', {
    1004: ResultInfo('SSL connection failed.'),
    1511: ResultInfo('Certificate warning.')
})

# 032: a second category related to the web browser
browser2 = Module('browser (?)', {
    1820: ResultInfo('Displayed when the browser asks if you want to go to to a potentially dangerous website. Press \'yes\' to continue if you feel it is safe.')
})

# 022: more account stuff?
account2 = Module('account', {
    2452: ResultInfo('Tried to access the eShop with UNITINFO patch enabled. Turn it off in Luma\'s options.'),
    (2501, 2591): ResultInfo('NNID is already linked to another system. This can be the result of using System Transfer (where all NNIDs associated with the system are moved, whether they are currently linked or not), restoring the source console\'s NAND, and then attempting to use applications which require an NNID.'),
    2511: ResultInfo('System update required (displayed by Miiverse?).'),
    2613: ResultInfo('Incorrect email or password when attempting to link an existing NNID. Can also happen if the NNID is already linked to another system, or if you attempt to download an application from the eShop without a linked NNID on the console.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4314/kw/022-2613'),
    2631: ResultInfo('The NNID you are attempting to use has been deleted, or is unusable due to a System Transfer. A transferred NNID will only work on the target system.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/4285/kw/022-2631'),
    2633: ResultInfo('NNID is temporarily locked due to too many incorrect password attempts. Try again later.'),
    2634: ResultInfo('NNID is not correctly linked on this console.', '[To fix it, follow these steps. Afterwards, reboot and sign into your NNID again.](https://3ds.hacks.guide/godmode9-usage#removing-an-nnid-without-formatting-your-device)'),
    2812: ResultInfo('This console is permanently banned by Nintendo for playing Pokémon Sun & Moon online before the release date illegally.', is_ban=True),
    2815: ResultInfo('This console is banned from accessing Miiverse by Nintendo.'),
    5363: ResultInfo('Happens when trying to load NNID settings with a invalid language setting.'),
    5515: ResultInfo('Network timeout.'),
})

# 090: application defined?
unknown1 = Module('unknown', {
    212: ResultInfo('Game is permanently banned from Pokémon Global Link for using altered or illegal save data.', is_ban=True)
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
    ret.add_field(ConsoleErrorField('Module', message_str=module.name, supplementary_value=mod))
    description = module.get_error(desc)
    if description is None or not description.description:
        description = ctr_results_modules[0].get_error(desc)
        if description is None or not description.description:
            ret.add_field(ConsoleErrorField('Description', supplementary_value=desc))
        else:
            ret.add_field(ConsoleErrorField('Description', message_str=description.description, supplementary_value=desc))
    else:
        ret.add_field(ConsoleErrorField('Description', message_str=description.description, supplementary_value=desc))

    return ret


def construct_result_range(ret, mod, range_desc):
    module = ctr_results_modules.get(mod, Module(''))
    ret.add_field(ConsoleErrorField('Module', message_str=module.name, supplementary_value=mod))
    found_descs = []
    unknown_descs = []
    for desc in range_desc:
        if desc < 0 or desc > 1023:
            continue

        description = module.get_error(desc)
        if description is None or not description.description:
            description = ctr_results_modules[0].get_error(desc)
            if description is None or not description.description:
                unknown_descs.append(str(desc))
            else:
                found_descs.append(ConsoleErrorField('Description', message_str=description.description, supplementary_value=desc).message)
        else:
            found_descs.append(ConsoleErrorField('Description', message_str=description.description, supplementary_value=desc).message)

    if found_descs:
        ret.add_field(ConsoleErrorField('Possible known descriptions', message_str='\n'.join(found_descs)))
    if unknown_descs:
        ret.add_field(ConsoleErrorField('Possible unknown descriptions', message_str=', '.join(unknown_descs)))

    return ret


def construct_support(ret, mod, desc):
    category = modules.get(mod, Module(''))
    if category.name:
        ret.add_field(ConsoleErrorField('Category', message_str=category.name))
    else:
        ret.add_field(ConsoleErrorField('Category', supplementary_value=mod))
    description = category.get_error(desc)
    if description is not None and description.description:
        ret.add_field(ConsoleErrorField('Description', message_str=description.description))
        if description.support_url:
            ret.add_field(ConsoleErrorField('Further information', message_str=description.support_url))
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
    if error is not None and error.description:
        return construct_support(ret, 5, description)

    elif 2000 <= description < 3024:
        description -= 2000
        return construct_result(ret, 52, description)  # nim result module, not support category

    elif 4200 <= description < 4400:
        description -= 4200
        construct_result(ret, 40, description)  # http result module, not support category
        if description == 199:
            ret.add_field(ConsoleErrorField('Extra note', message_str='Alternatively, any http description beyond 199.\nNIM truncates it to 199.'))

    elif 4400 <= description < 5000:
        description -= 4400
        ret.add_field(ConsoleErrorField('Category', message_str='nim'))
        if description < 100:
            ret.add_field(ConsoleErrorField('HTTP Status Code', message_str=f'{description + 100}'))
        elif 100 <= description < 500:
            ret.add_field(ConsoleErrorField('HTTP Status Code', message_str=f'{description + 100} or {description} due to a programming mistake in NIM.'))
        else:
            ret.add_field(ConsoleErrorField('HTTP Status Code', message_str=f'{description}'))

    elif 5000 <= description < 7000:
        description -= 5000
        ret.add_field(ConsoleErrorField('Category', message_str='nim'))
        ret.add_field(ConsoleErrorField('Description', message_str=f'SOAP message returned result code {description} on a NIM operation.'))

    # >= 7000 range is compacted
    elif description >= 7000:
        description -= 7000
        module = description >> 5
        # There are way more than 0x1F descriptions, but this is how Nintendo does it...
        description = description & 0x1F
        return construct_result_range(ret, module, range(0 + description, 1024 + description, 32))

    else:
        ret.add_field(ConsoleErrorField('Category', message_str='nim'))
        ret.add_field(UNKNOWN_CATEGORY_DESCRIPTION)

    return ret


def get(error: str):
    mod = int(error[:3])
    desc = int(error[4:])
    ret = ConsoleErrorInfo(error, CONSOLE_NAME, COLOR)
    if mod == 5:  # 5 is NIM
        return nim_handler(ret, desc)
    return construct_support(ret, mod, desc)
