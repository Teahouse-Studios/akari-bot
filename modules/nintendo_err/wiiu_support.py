import re

from .types import Module, ResultInfo, ConsoleErrorInfo, ConsoleErrorField, \
    BANNED_FIELD, WARNING_COLOR, UNKNOWN_CATEGORY_DESCRIPTION

"""
This file contains all currently known Wii U result and error codes.
There may be inaccuracies here; we'll do our best to correct them
when we find out more about them.
A "support" code, in contrast to a result code, is a human-readable string like
102-2811. They're meant to be more user-friendly than result codes, which are
typically integer values.
Note: the "modules" presented here are more like "categories". However, this difference
isn't enough to justify creating a different class with the same logic, so we'll just
refer to them as "modules" from now on.
To add a module so the code understands it, simply add a new module number
to the 'modules' dictionary, with a Module variable as the value. If the module
has no known error codes, simply add a dummy Module instead (see the dict for
more info). See the various module variables for a more in-depth example
 on how to make one.
Once you've added a module, or you want to add a new result code to an existing
module, add a new description value (for Switch it's the final set of 4 digits after any dashes)
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
Sources used to compile this list of results:
https://github.com/Kinnay/NintendoClients/wiki/Wii-U-Error-Codes
"""

fp = Module('fp (friends)', {
    0: ResultInfo('Success.'),
    1: ResultInfo('Session closed.'),
    10: ResultInfo('Programming error.'),
    11: ResultInfo('Not initialized.'),
    12: ResultInfo('Already initialized.'),
    13: ResultInfo('Invalid argument.'),
    14: ResultInfo('Busy.'),
    15: ResultInfo('Network clock is invalid.'),
    16: ResultInfo('Not permitted.'),
    100: ResultInfo('Undefined error.'),
    101: ResultInfo('Reserved error 01.'),
    102: ResultInfo('Unknown error.'),
    103: ResultInfo('Not implemented.'),
    104: ResultInfo('Invalid pointer.'),
    105: ResultInfo('Operation aborted.'),
    106: ResultInfo('Exception occurred.'),
    107: ResultInfo('Access denied.'),
    108: ResultInfo('Invalid handle.'),
    109: ResultInfo('Invalid index.'),
    110: ResultInfo('Out of memory.'),
    111: ResultInfo('Invalid argument.'),
    112: ResultInfo('Timeout.'),
    113: ResultInfo('Initialization failure.'),
    114: ResultInfo('Call initiation failure.'),
    115: ResultInfo('Registration error.'),
    116: ResultInfo('Buffer overflow.'),
    117: ResultInfo('Invalid lock state.'),
    200: ResultInfo('Undefined.'),
    201: ResultInfo('Invalid signature.'),
    202: ResultInfo('Incorrect version.'),
    300: ResultInfo('Undefined.'),
    301: ResultInfo('Connection failure.'),
    302: ResultInfo('Not authenticated.'),
    303: ResultInfo('Invalid username.'),
    304: ResultInfo('Invalid password.'),
    305: ResultInfo('Username already exists.'),
    306: ResultInfo('Account is disabled.'),
    307: ResultInfo('Account is expired.'),
    308: ResultInfo('Concurrent login denied.'),
    309: ResultInfo('Encryption failure.'),
    310: ResultInfo('Invalid PID.'),
    311: ResultInfo('Max connections reached.'),
    312: ResultInfo('Invalid GID.'),
    313: ResultInfo('Invalid thread ID.'),
    314: ResultInfo('Invalid operation in live environment.'),
    315: ResultInfo('Duplicate entry.'),
    316: ResultInfo('Control script failure.'),
    317: ResultInfo('Class not found.'),
    318: ResultInfo('Reserved 18.'),
    319: ResultInfo('Reserved 19.'),
    320: ResultInfo('DDL mismatch.'),
    321: ResultInfo('Reserved 21.'),
    322: ResultInfo('Reserved 22.'),
    400: ResultInfo('Undefined error.'),
    401: ResultInfo('Exception occurred.'),
    402: ResultInfo('Type error.'),
    403: ResultInfo('Index error.'),
    404: ResultInfo('Invalid reference.'),
    405: ResultInfo('Call failure.'),
    406: ResultInfo('Memory error.'),
    407: ResultInfo('Operation error.'),
    408: ResultInfo('Conversion error.'),
    409: ResultInfo('Validation error.'),
    500: ResultInfo('Undefined error.'),
    501: ResultInfo('Unknown error.'),
    502: ResultInfo('Connection failure.'),
    503: ResultInfo('Invalid URL.'),
    504: ResultInfo('Invalid key.'),
    505: ResultInfo('Invalid URL type.'),
    506: ResultInfo('Duplicate endpoint.'),
    507: ResultInfo('I/O error.'),
    508: ResultInfo('Timeout.'),
    509: ResultInfo('Connection reset.'),
    510: ResultInfo('Incorrect remote authentication.'),
    511: ResultInfo('Server request error.'),
    512: ResultInfo('Decompression failure.'),
    513: ResultInfo('Congested end-point.'),
    514: ResultInfo('Reserved 14.'),
    515: ResultInfo('Reserved 15.'),
    516: ResultInfo('Reserved 16.'),
    517: ResultInfo('Reserved 17.'),
    518: ResultInfo('Socket send warning.'),
    519: ResultInfo('Unsupported NAT.'),
    520: ResultInfo('DNS error.'),
    521: ResultInfo('Proxy error.'),
    522: ResultInfo('Data remaining.'),
    523: ResultInfo('No buffer.'),
    524: ResultInfo('Not found.'),
    600: ResultInfo('Undefined error.'),
    700: ResultInfo('Undefined error.'),
    701: ResultInfo('Reserved 1.'),
    702: ResultInfo('Not initialized.'),
    703: ResultInfo('Already initialized.'),
    704: ResultInfo('Not connected.'),
    705: ResultInfo('Connected.'),
    706: ResultInfo('Initialization failure.'),
    707: ResultInfo('Out of memory.'),
    708: ResultInfo('RMC failed.'),
    709: ResultInfo('Invalid argument.'),
    710: ResultInfo('Reserved 10.'),
    711: ResultInfo('Invalid principal ID.'),
    712: ResultInfo('Reserved 12.'),
    713: ResultInfo('Reserved 13.'),
    714: ResultInfo('Reserved 14.'),
    715: ResultInfo('Reserved 15.'),
    716: ResultInfo('Reserved 16.'),
    717: ResultInfo('Reserved 17.'),
    718: ResultInfo('Reserved 18.'),
    719: ResultInfo('Reserved 19.'),
    720: ResultInfo('File I/O error.'),
    721: ResultInfo('P2P internet prohibited.'),
    722: ResultInfo('Unknown error.'),
    723: ResultInfo('Invalid state.'),
    724: ResultInfo('Reservd 24.'),
    725: ResultInfo('Adding a friend is prohibited.'),
    726: ResultInfo('Reserved 26.'),
    727: ResultInfo('Invalid account.'),
    728: ResultInfo('Blacklisted by me.'),
    729: ResultInfo('Reserved 29.'),
    730: ResultInfo('Friend already added.'),
    731: ResultInfo('Friend list limit exceeded.'),
    732: ResultInfo('Requests limit exceeded.'),
    733: ResultInfo('Invalid message ID.'),
    734: ResultInfo('Message is not mine.'),
    735: ResultInfo('Message is not for me.'),
    736: ResultInfo('Friend request blocked.'),
    737: ResultInfo('Not in my friend list.'),
    738: ResultInfo('Friend listed by me.'),
    739: ResultInfo('Not in my blackist.'),
    740: ResultInfo('Incompatible account.'),
    741: ResultInfo('Block setting change not allowed.'),
    742: ResultInfo('Size limit exceeded.'),
    743: ResultInfo('Operation not allowed.'),
    744: ResultInfo('Not a network account.'),
    745: ResultInfo('Notification not found.'),
    746: ResultInfo('Preference not initialized.'),
    747: ResultInfo('Friend request not allowed.'),
    800: ResultInfo('Undefined error.'),
    801: ResultInfo('Account library error.'),
    802: ResultInfo('Token parse error.'),
    803: ResultInfo('Reserved 3.'),
    804: ResultInfo('Reserved 4.'),
    805: ResultInfo('Reserved 5.'),
    806: ResultInfo('Token expired.'),
    807: ResultInfo('Validation failed.'),
    808: ResultInfo('Invalid parameters.'),
    809: ResultInfo('Principal ID unmatched.'),
    810: ResultInfo('Reserved 10.'),
    811: ResultInfo('Under maintenance.'),
    812: ResultInfo('Unsupported version.'),
    813: ResultInfo('Unknown error.')
}, {
    (100, 199): 'Core',
                (200, 299): 'DDL',
                (300, 399): 'Rendezvous',
                (400, 499): 'Python Core',
                (500, 599): 'Transport',
                (600, 699): 'DO Core',
                (700, 799): 'FPD',
                (800, 899): 'Authentication',
                (1100, 1199): 'Ranking',
                (1200, 1299): 'Data Store',
                (1500, 1599): 'Service Item',
                (1800, 1899): 'Matchmaking Referee',
                (1900, 1999): 'Subscriber',
                (2000, 2099): 'Ranking2',
})

act = Module('act (accounts)', {
    0: ResultInfo('Success.'),
    1: ResultInfo('Mail address not confirmed.'),
    500: ResultInfo('Library error.'),
    501: ResultInfo('Not initialized.'),
    502: ResultInfo('Already initialized.'),
    511: ResultInfo('Busy.'),
    591: ResultInfo('Not implemented.'),
    592: ResultInfo('Deprecated.'),
    593: ResultInfo('Development only.'),
    600: ResultInfo('Invalid argument.'),
    601: ResultInfo('Invalid pointer.'),
    602: ResultInfo('Out of range.'),
    603: ResultInfo('Invalid size.'),
    604: ResultInfo('Invalid format.'),
    605: ResultInfo('Invalid handle.'),
    606: ResultInfo('Invalid value.'),
    700: ResultInfo('Internal error.'),
    701: ResultInfo('End of stream.'),
    710: ResultInfo('File error.'),
    711: ResultInfo('File not found.'),
    712: ResultInfo('File version mismatch.'),
    713: ResultInfo('File I/O error.'),
    714: ResultInfo('File type mismatch.'),
    730: ResultInfo('Out of resources.'),
    731: ResultInfo('Buffer is insufficient.'),
    740: ResultInfo('Out of memory.'),
    741: ResultInfo('Out of global heap.'),
    742: ResultInfo('Out of cross-process heap.'),
    744: ResultInfo('Out of MXML heap.'),
    800: ResultInfo('Generic error.'),
    801: ResultInfo('Open error.'),
    802: ResultInfo('Read sys-config error.'),
    810: ResultInfo('Generic error.'),
    811: ResultInfo('Open error.'),
    812: ResultInfo('Get info error.'),
    820: ResultInfo('Generic error.'),
    821: ResultInfo('Initialization failure.'),
    822: ResultInfo('Get country code failure.'),
    823: ResultInfo('Get language code failure.'),
    850: ResultInfo('Generic error.'),
    900: ResultInfo('Generic error.'),
    901: ResultInfo('Open error.'),
    1000: ResultInfo('Management error.'),
    1001: ResultInfo('Not found.'),
    1002: ResultInfo('Slots full.'),
    1011: ResultInfo('Not loaded.'),
    1012: ResultInfo('Already loaded.'),
    1013: ResultInfo('Locked.'),
    1021: ResultInfo('Not a network account.'),
    1022: ResultInfo('Not a local account.'),
    1023: ResultInfo('Not committed.'),
    1101: ResultInfo('Network clock is invalid.'),
    2000: ResultInfo('Authentication error.'),
    # TODO: 2001-2644 (there aren't really that many errors)
    2643: ResultInfo('Authentication is required.'),
    2651: ResultInfo('Confirmation code is expired.'),
    2661: ResultInfo('Mail address is not validated.'),
    2662: ResultInfo('Excessive mail send requests.'),
    2670: ResultInfo('Generic error.'),
    2671: ResultInfo('General failure.'),
    2672: ResultInfo('Declined.'),
    2673: ResultInfo('Blacklisted.'),
    2674: ResultInfo('Invalid credit card number.'),
    2675: ResultInfo('Invalid credit card date.'),
    2676: ResultInfo('Invalid credit card PIN.'),
    2677: ResultInfo('Invalid postal code.'),
    2678: ResultInfo('Invalid location.'),
    2679: ResultInfo('Card is expired.'),
    2680: ResultInfo('Credit card number is wrong.'),
    2681: ResultInfo('PIN is wrong.'),
    2800: ResultInfo('Banned.', is_ban=True),
    2801: ResultInfo('Account is banned.', is_ban=True),
    2802: ResultInfo('Account is banned from all services.', is_ban=True),
    2803: ResultInfo('Account is banned from a particular game.', is_ban=True),
    2804: ResultInfo('Account is banned from Nintendo\'s online service.', is_ban=True),
    2805: ResultInfo('Account is banned from independent services.', is_ban=True),
    2811: ResultInfo('Console is banned.', is_ban=True),
    2812: ResultInfo('Console is banned from all services.', is_ban=True),
    2813: ResultInfo('Console is banned from a particular game.', is_ban=True),
    2814: ResultInfo('Console is banned from Nintendo\'s online service.', is_ban=True),
    2815: ResultInfo('Console is banned from independent services.', is_ban=True),
    2816: ResultInfo(
        'Console is banned for an unknown duration, due to using modified/hacked files in online games like Splatoon.',
        is_ban=True),
    2821: ResultInfo('Account is temporarily banned.', is_ban=True),
    2822: ResultInfo('Account is temporarily banned from all services.', is_ban=True),
    2823: ResultInfo('Account is temporarily banned from a particular game.', is_ban=True),
    2824: ResultInfo('Account is temporarily banned from Nintendo\'s online service.', is_ban=True),
    2825: ResultInfo('Acccount is temporarily banned from independent services.', is_ban=True),
    2831: ResultInfo('Console is temporarily banned.', is_ban=True),
    2832: ResultInfo('Console is temporarily banned from all services.', is_ban=True),
    2833: ResultInfo('Console is temporarily banned from a particular game.', is_ban=True),
    2834: ResultInfo('Console is temporarily banned from Nintendo\'s online service.', is_ban=True),
    2835: ResultInfo('Console is temporarily banned from independent services.', is_ban=True),
    2880: ResultInfo('Service is not provided.'),
    2881: ResultInfo('Service is currently under maintenance.'),
    2882: ResultInfo('Service is closed.'),
    2883: ResultInfo('Nintendo Network is closed.'),
    2884: ResultInfo('Service is not provided in this country.'),
    2900: ResultInfo('Restriction error.'),
    2901: ResultInfo('Restricted by age.'),
    2910: ResultInfo('Restricted by parental controls.'),
    2911: ResultInfo('In-game internet communication/chat is restricted.'),
    2931: ResultInfo('Internal server error.'),
    2932: ResultInfo('Unknown server error.'),
    2998: ResultInfo('Unauthenticated after salvage.'),
    2999: ResultInfo('Unknown authentication failure.'),

}, {
    (0, 499): 'Internal',
    (500, 599): 'Status changed',
    (600, 699): 'Invalid argument',
    (700, 709): 'Internal error',
    (710, 729): 'File error',
    (730, 799): 'Out of resources',
    (800, 809): 'UC',
    (810, 819): 'MCP',
    (820, 849): 'ISO',
    (850, 899): 'MXML',
    (900, 999): 'IOS',
    (1000, 1099): 'Account',
    (2100, 2199): 'HTTP',
    (2500, 2599): 'Account',
    (2670, 2699): 'Credit Card',
    (2800, 2835): 'Banned',
    (2880, 2899): 'Not available',  # not provided/under maintenance/no longer in service
})

nex = Module('nex (game servers)', {
    102: ResultInfo('The reason for the error is unknown.'),
    103: ResultInfo('The operation is currently not implemented.'),
    104: ResultInfo('The operation specifies or accesses an invalid pointer.'),
    105: ResultInfo('The operation was aborted.'),
    106: ResultInfo('The operation raised an exception.'),
    107: ResultInfo(
        'An attempt was made to access data in an incorrect manner. This may be due to inadequate permission or the data, file, etc. not existing.'),
    108: ResultInfo('The operation specifies or accesses an invalid DOHandle.'),
    109: ResultInfo('The operation specifies or accesses an invalid index.'),
    110: ResultInfo(
        'The system could not allocate or access enough memory or disk space to perform the specified operation.'),
    111: ResultInfo('Invalid argument were passed with the operation. The argument(s) may be out of range or invalid.'),
    112: ResultInfo('The operation did not complete within the specified timeout for that operation.'),
    113: ResultInfo('Initialization of the component failed.'),
    114: ResultInfo('The call failed to initialize.'),
    115: ResultInfo('An error occurred during registration.'),
    116: ResultInfo('The buffer is too large to be sent.'),
    117: ResultInfo('Invalid lock state.'),
    118: ResultInfo('Invalid sequence.'),
    301: ResultInfo('Connection was unable to be established, either with the Rendez-Vous back end or a Peer.'),
    302: ResultInfo('The Principal could not be authenticated by the Authentication Service.'),
    303: ResultInfo(
        'The Principal tried to log in with an invalid user name, i.e. the user name does not exist in the database.'),
    304: ResultInfo(
        'The Principal either tried to log in with an invalid password for the provided user name or tried to join a Gathering with an invalid password.'),
    305: ResultInfo('The provided user name already exists in the database. All usernames must be unique.'),
    306: ResultInfo('The Principal\'s account still exists in the database but the account has been disabled.',
                    is_ban=True),
    307: ResultInfo('The Principal\'s account still exists in the database but the account has expired.'),
    308: ResultInfo(
        'The Principal does not have the Capabilities to perform concurrent log ins, i.e. at any given time only one log-in may be maintained.'),
    309: ResultInfo('Data encryption failed.'),
    310: ResultInfo('The operation specifies or accesses an invalid PrincipalID.'),
    311: ResultInfo('Maximum connection number is reached.'),
    312: ResultInfo('Invalid GID.'),
    313: ResultInfo('Invalid Control script ID.'),
    314: ResultInfo('Invalid operation in live/production environment.'),
    315: ResultInfo('Duplicate entry.'),
    346: ResultInfo('NNID is permanently banned.', is_ban=True),
    501: ResultInfo('The reason for the error is unknown.'),
    502: ResultInfo('Network connection was unable to be established.'),
    503: ResultInfo('The URL contained in the StationURL is invalid. The syntax may be incorrect.'),
    504: ResultInfo(
        'The key used to authenticate a given station is invalid. The secure transport layer uses secret-key based cryptography to ensure the integrity and confidentiality of data sent across the network.'),
    505: ResultInfo('The specified transport type is invalid.'),
    506: ResultInfo('The Station is already connected via another EndPoint.'),
    507: ResultInfo(
        'The data could not be sent across the network. This could be due to an invalid message, packet, or buffer.'),
    508: ResultInfo('The operation did not complete within the specified timeout for that operation.'),
    509: ResultInfo('The network connection was reset.'),
    510: ResultInfo('The destination Station did not authenticate itself properly.'),
    511: ResultInfo(
        '3rd-party server or device answered with an error code according to protocol used e.g. HTTP error code.'),
}, {
    (100, 199): 'Core',
    (200, 299): 'DDL',
    (300, 399): 'Rendezvous',
    (400, 499): 'Python Core',
    (500, 599): 'Transport',
    (600, 699): 'DO Core',
    (700, 799): 'FPD',
    (800, 899): 'Authentication',
    (1100, 1199): 'Ranking',
    (1200, 1299): 'Data Store',
    (1500, 1599): 'Service Item',
    (1800, 1899): 'Matchmaking Referee',
    (1900, 1999): 'Subscriber',
    (2000, 2099): 'Ranking2',
})

eshop_api = Module('eshop(api)', {
    3190: ResultInfo('Wishlist is full.')
})

eshop_web = Module('eshop (web)', {
    9000: ResultInfo('Close application (Connection timeout issue?).'),
    9001: ResultInfo('Retriable.'),
    9002: ResultInfo('Online services are undergoing maintenance.'),
    9003: ResultInfo('The online services are discontinued and thus are no longer available.'),
    9100: ResultInfo('Invalid template.')
})

unknown2 = Module('unknown (browser?)', {
    1037: ResultInfo(
        'Incorrect permissions for the default index.html file which prevents the Internet Browser from reading it.',
        '[To fix it, follow these steps.](https://wiiu.hacks.guide/#/fix-errcode-112-1037)'),
    1035: ResultInfo('SSL handshake failed due to cipher mismatch.'),
    1209: ResultInfo('Internet Browser is unable to load a file(?).')
})

olv = Module('olv (miiverse)', {
    1009: ResultInfo('Console is permanently banned from Miiverse.', is_ban=True),
    5004: ResultInfo('The Miiverse service has been discontinued.')
})

eshop_unk = Module('eShop (unknown)', {
    9622: ResultInfo('Error when attempting to add funds. Check that the payment method is correct or try again later.')
})

fs = Module('fs', {
    1031: ResultInfo(
        'The disc could not be read or is unsupported (i.e. not a Wii or Wii U game). Try cleaning the disc or lens if it is a supported title.'),
    2031: ResultInfo(
        'The disc could not be read or is unsupported (i.e. not a Wii or Wii U game). Try cleaning the disc or lens if it is a supported title.'),
    3032: ResultInfo('Error when attempting to read caused by a permission error.')
})

syserr = Module('system error', {
    101: ResultInfo('Generic error. Can happen when formatting a console that has CBHC installed.'),
    102: ResultInfo('Error in SLC/MLC or USB.'),
    103: ResultInfo('The MLC system memory is corrupted.'),
    104: ResultInfo('The SLC system memory is corrupted.'),
    105: ResultInfo('The USB storage is corrupted.'),
    2706: ResultInfo('Error when reading from USB storage device'),
    2713: ResultInfo('The USB Storage device has been disconnected.')
})

unknown = Module('unknown/misc.', {
    9999: ResultInfo(
        'Usually indicates an invalid signature, ticket, or corrupted data. Typically happens when running an unsigned program without CFW/signature patches.')
})

# We have some modules partially documented, those that aren't have dummy Modules.
modules = {
    101: fp,
    102: act,
    103: Module('ac (internet connection)'),
    104: Module('boss(spotpass)'),
    105: Module('nim (title installation)'),
    106: nex,
    107: eshop_api,
    111: eshop_web,
    112: unknown2,
    115: olv,
    118: Module('pia (peer-to-peer)'),
    124: Module('ec (e-commerce)'),
    126: eshop_unk,
    150: fs,
    151: Module('kpad (wiimote)'),
    155: Module('save'),
    160: syserr,
    165: Module('vpad (gamepad)'),
    166: Module('aoc (dlc)'),
    187: Module('nfp (amiibo)'),
    199: unknown
}

# regex for Wii U result code format "1XX-YYYY"
RE = re.compile(r'1\d{2}-\d{4}')

CONSOLE_NAME = 'Nintendo Wii U'

# Suggested color to use if displaying information through a Discord bot's embed
COLOR = 0x009AC7


def is_valid(error):
    return RE.match(error)


def construct_support(ret, mod, desc):
    category = modules.get(mod, Module(''))
    if category.name:
        ret.add_field(ConsoleErrorField('Category', message_str=category.name))
    else:
        ret.add_field(ConsoleErrorField('Category', supplementary_value=mod))
    summary = category.get_summary(desc)
    if summary:
        ret.add_field(ConsoleErrorField('Summary', message_str=summary))
    description = category.get_error(desc)
    if description and description.description:
        ret.add_field(ConsoleErrorField('Description', message_str=description.description))
        if description.support_url:
            ret.add_field(ConsoleErrorField('Further information', message_str=description.support_url))
        if description.is_ban:
            ret.add_field(BANNED_FIELD)
            ret.color = WARNING_COLOR
    else:
        ret.add_field(UNKNOWN_CATEGORY_DESCRIPTION)
    return ret


def get(error):
    mod = int(error[:3])
    desc = int(error[4:])
    ret = ConsoleErrorInfo(error, CONSOLE_NAME, COLOR)
    return construct_support(ret, mod, desc)
