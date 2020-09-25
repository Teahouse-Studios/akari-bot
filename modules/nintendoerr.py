#Copied from kurisu(https://github.com/nh-server/Kurisu/blob/port/cogs/err.py)
import binascii
import re

class Err():
    """
    Parses CTR error codes.
    """


    # CTR Error Codes
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

    levels = {
        0: "Success",
        1: "Info",

        25: "Status",
        26: "Temporary",
        27: "Permanent",
        28: "Usage",
        29: "Reinitialize",
        30: "Reset",
        31: "Fatal"
    }

    modules = {
        0: 'Common',
        1: 'Kernel',
        2: 'Util',
        3: 'File server',
        4: 'Loader server',
        5: 'TCB',
        6: 'OS',
        7: 'DBG',
        8: 'DMNT',
        9: 'PDN',
        10: 'GSP',
        11: 'I2C',
        12: 'GPIO',
        13: 'DD',
        14: 'CODEC',
        15: 'SPI',
        16: 'PXI',
        17: 'FS',
        18: 'DI',
        19: 'HID',
        20: 'CAM',
        21: 'PI',
        22: 'PM',
        23: 'PM_LOW',
        24: 'FSI',
        25: 'SRV',
        26: 'NDM',
        27: 'NWM',
        28: 'SOC',
        29: 'LDR',
        30: 'ACC',
        31: 'RomFS',
        32: 'AM',
        33: 'HIO',
        34: 'Updater',
        35: 'MIC',
        36: 'FND',
        37: 'MP',
        38: 'MPWL',
        39: 'AC',
        40: 'HTTP',
        41: 'DSP',
        42: 'SND',
        43: 'DLP',
        44: 'HIO_LOW',
        45: 'CSND',
        46: 'SSL',
        47: 'AM_LOW',
        48: 'NEX',
        49: 'Friends',
        50: 'RDT',
        51: 'Applet',
        52: 'NIM',
        53: 'PTM',
        54: 'MIDI',
        55: 'MC',
        56: 'SWC',
        57: 'FatFS',
        58: 'NGC',
        59: 'CARD',
        60: 'CARDNOR',
        61: 'SDMC',
        62: 'BOSS',
        63: 'DBM',
        64: 'Config',
        65: 'PS',
        66: 'CEC',
        67: 'IR',
        68: 'UDS',
        69: 'PL',
        70: 'CUP',
        71: 'Gyroscope',
        72: 'MCU',
        73: 'NS',
        74: 'News',
        75: 'RO',
        76: 'GD',
        77: 'Card SPI',
        78: 'EC',
        79: 'Web Browser',
        80: 'Test',
        81: 'ENC',
        82: 'PIA',
        83: 'ACT',
        84: 'VCTL',
        85: 'OLV',
        86: 'NEIA',
        87: 'NPNS',
        90: 'AVD',
        91: 'L2B',
        92: 'MVD',
        93: 'NFC',
        94: 'UART',
        95: 'SPM',
        96: 'QTM',
        97: 'NFP (amiibo)',
        254: 'Application',
        255: 'Invalid result value'
    }

    descriptions = {
        0: 'Success',
        2: 'Invalid memory permissions (kernel)',
        4: 'Invalid ticket version (AM)',
        5: 'Invalid string length. This error is returned when service name length is greater than 8 or zero. (srv)',
        6: 'Access denied. This error is returned when you request a service that you don\'t have access to. (srv)',
        7: 'String size does not match string contents. This error is returned when service name contains an unexpected null byte. (srv)',
        8: 'Camera already in use/busy (qtm).',
        10: 'Not enough memory (os)',
        26: 'Session closed by remote (os)',
        32: 'Empty CIA? (AM)',
        37: 'Invalid NCCH? (AM)',
        39: 'Invalid title version (AM)',
        43: 'Database doesn\'t exist/failed to open (AM)',
        44: 'Trying to uninstall system-app (AM)',
        47: 'Invalid command header (OS)',
        101: 'Archive not mounted/mount-point not found (fs)',
        105: 'Request timed out (http)',
        106: 'Invalid signature/CIA? (AM)',
        120: 'Title/object not found? (fs)',
        141: 'Gamecard not inserted? (fs)',
        190: 'Object does already exist/failed to create object.',
        230: 'Invalid open-flags / permissions? (fs)',
        250: 'FAT operation denied (fs?)',
        271: 'Invalid configuration (mvd).',
        335: '(No permission? Seemed to appear when JKSM was being used without its XML.)',
        391: 'NCCH hash-check failed? (fs)',
        392: 'RSA/AES-MAC verification failed? (fs)',
        393: 'Invalid database? (AM)',
        395: 'RomFS/Savedata hash-check failed? (fs)',
        630: 'Command not allowed / missing permissions? (fs)',
        702: 'Invalid path? (fs)',
        740: '(Occurred when NDS card was inserted and attempting to use AM_GetTitleCount on MEDIATYPE_GAME_CARD.) (fs)',
        761: 'Incorrect read-size for ExeFS? (fs)',
        1000: 'Invalid selection',
        1001: 'Too large',
        1002: 'Not authorized',
        1003: 'Already done',
        1004: 'Invalid size',
        1005: 'Invalid enum value',
        1006: 'Invalid combination',
        1007: 'No data',
        1008: 'Busy',
        1009: 'Misaligned address',
        1010: 'Misaligned size',
        1011: 'Out of memory',
        1012: 'Not implemented',
        1013: 'Invalid address',
        1014: 'Invalid pointer',
        1015: 'Invalid handle',
        1016: 'Not initialized',
        1017: 'Already initialized',
        1018: 'Not found',
        1019: 'Cancel requested',
        1020: 'Already exists',
        1021: 'Out of range',
        1022: 'Timeout',
        1023: 'Invalid result value'
    }

    # Nintendo Error Codes
    errcodes = {
        # Nintendo 3DS
        '001-0502': 'Some sort of network error related to friend presence. "Allow Friends to see your online status" might fix this.',
        '001-0803': 'Could not communicate with authentication server.',
        '002-0102': 'System is permanently banned by Nintendo. You cannot ask how to fix this issue here.',
        '002-0107': 'System is temporarily(?) banned by Nintendo. You cannot ask how to fix this issue here.',
        '002-0119': 'System update required (outdated friends-module)',
        '002-0120': 'Title update required (outdated title version)',
        '002-0121': 'Local friend code SEED has invalid signature.\n\nThis should not happen unless it is modified. The only use case for modifying this file is for system unbanning, so you cannot ask how to fix this issue here.',
        '002-0123': 'System is generally banned by Nintendo. You cannot ask how to fix this issue here.',
        '022-2502': 'Region settings between the console and Nintendo Network ID do not match. The console region must be fixed to use the NNID. If you want to use a different region, the NNID must be unlinked from the system or deleted.',
        '022-2932': 'Unable to agree to the Nintendo Network Services Agreement. Usually found on region-changed devices.',
        '003-1099': 'Access point could not be found with the given SSID.',
        '003-2001': 'DNS error. If using a custom DNS server, make sure the settings are correct.',
        '005-7000': 'Base error code for most other error codes. No error occured.',
        '005-2008': 'This error is caused by installing a game or game update from an unofficial source, as it contains a bad ticket.\nThe only solution is to delete the unofficial game or update as well as its ticket\nin FBI, and install the game or update legitimately. If the title was uninstalled\nalready, remove the ticket in FBI.',
        '005-4800': 'HTTP Status 500 (Internal Error), unknown cause(?). eShop servers might have issues.',
        '005-5602': 'Unable to connect to the eShop. This error is most likely the result of an incorrect region setting.\nMake sure your region is correctly set in System Settings. If you encounter this error after region-changing your system, make sure you followed all the steps properly.',
        '005-5958': 'Unknown eShop error. Usually seen on region-changed devices.',
        '005-5964': 'Your Nintendo Network ID has been banned from accessing the eShop.\nIf you think this was unwarranted, you will have to contact Nintendo Support to have it reversed.',
        '005-7550': 'Replace SD card(?). Occurs on Nintendo eShop.',
        '006-0102': 'Unexpected error. Could probably happen trying to play an out-of-region title online?',
        '006-0332': 'Disconnected from the game server.',
        '006-0502': 'Could not connect to the server.\n\n• Check the [network status page](http://support.nintendo.com/networkstatus)\n• Move closer to your wireless router\n• Verify DNS settings. If "Auto-Obtain" doesn\'t work, try Google\'s Public DNS (8.8.8.8, 8.8.4.4) and try again.',
        '006-0612': 'Failed to join the session.',
        '007-0200': 'Could not access SD card.',
        '007-2001': 'Usually the result after region-changing the system. New 3DS cannot fix this issue right now.',
        '007-2100': 'The connection to the Nintendo eShop timed out.\nThis may be due to an ongoing server maintenance, check <https://support.nintendo.com/networkstatus> to make sure the servers are operating normally. You may also encounter this error if you have a weak internet connection.',
        '007-2404': 'An error occurred while attempting to connect to the Nintendo eShop.\nMake sure you are running the latest firmware, since this error will appear if you are trying to access the eShop on older versions.',
        '007-2670': 'Generic connection error.',
        '007-2720': 'SSL error?',
        '007-2916': 'HTTP error, server is probably down. Try again later?',
        '007-2920': 'This error is caused by installing a game or game update from an unofficial source, as it contains a bad ticket.\nThe only solution is to delete the unofficial game or update as well as its ticket\nin FBI, and install the game or update legitimately. If the title was uninstalled\nalready, remove the ticket in FBI.',
        '007-2913': 'HTTP error, server is probably down. Try again later?',
        '007-2923': 'The Nintendo Servers are currently down for maintenance. Please try again later.',
        '007-3102': 'Cannot find title on Nintendo eShop. Probably pulled.',
        '007-6054': 'Occurs when ticket database is full (8192 tickets).',
        '009-1000': 'System update required. (friends module?)',
        '009-2916': 'NIM HTTP error, server is probably down. Try again later?',
        '009-2913': 'NIM HTTP error, server is probably down. Try again later?',
        '009-2920': 'This error is caused by installing a game or game update from an unofficial source, as it contains a bad ticket.\nThe only solution is to delete the unofficial game or update as well as its ticket\nin FBI, and install the game or update legitimately. If the title was uninstalled\nalready, remove the ticket in FBI.',
        '009-4079': 'Could not access SD card. General purpose error.',
        '009-4998': '"Local content is newer."\nThe actual cause of this error is unknown.',
        '009-6106': '"AM error in NIM."\nProbably a bad ticket.',
        '009-8401': 'Update data corrupted. Delete and re-install.',
        '011-3021': 'Cannot find title on Nintendo eShop. Probably incorrect region, or never existed.',
        '011-3136': 'Nintendo eShop is currently unavailable. Try again later.',
        '011-6901': 'System is banned by Nintendo, this error code description is oddly Japanese, generic error code. You cannot ask how to fix this issue here.',
        '012-1511': 'Certificate warning.',
        '014-0016': 'Both systems have the same movable.sed key. Format the target and try system transfer again.',
        '014-0062': 'Error during System Transfer. Move closer to the wireless router and keep trying.',
        '022-2452': 'Occurs when trying to use Nintendo eShop with UNITINFO patches enabled.',
        '022-2501': 'Attempting to use a Nintendo Network ID on one system when it is linked on another. This can be the result of using System Transfer, then restoring the source system\'s NAND and attempting to use services that require a Nintendo Network ID.\n\nIn a System Transfer, all Nintendo Network ID accounts associated with the system are transferred over, whether they are currently linked or not.',
        '022-2511': 'System update required (what causes this? noticed while opening Miiverse, probably not friends module)',
        '022-2613': 'Incorrect e-mail or password when trying to link an existing Nintendo Network ID. Make sure there are no typos, and the given e-mail is the correct one for the given ID.\nIf you forgot the password, reset it at <https://id.nintendo.net/account/forgotten-password>',
        '022-2631': 'Nintendo Network ID deleted, or not usable on the current system. If you used System Transfer, the Nintendo Network ID will only work on the target system.',
        '022-2633': 'Nintendo Network ID temporarily locked due to too many incorrect password attempts. Try again later.',
        '022-2634': 'Nintendo Network ID is not correctly linked on the system. This can be a result of formatting the SysNAND using System Settings to unlink it from the EmuNAND.\nTo fix, boot GodMode9 and [follow these steps.](https://3ds.hacks.guide/godmode9-usage#removing-an-nnid-without-formatting-your-device)\nAfterwards, reboot and sign into your NNID again.',
        '022-2812': 'System is permanently banned by Nintendo for illegally playing the Pokemon Sun & Moon ROM leak online before release. You cannot ask how to fix this issue here.',
        '022-2815': 'System is banned by Nintendo from Miiverse access.',
        '022-5515': 'Network timeout.',
        '032-1820': 'Browser error that asks whether you want to go on to a potentially dangerous website. Can be bypassed by touching "yes".',
        '090-0212': 'Game is permanently banned from Pokémon Global Link. This is most likely as a result of using altered or illegal save data.',
        # Wii U
        # these all mean different things technically and maybe i should list them
        '102-2802': 'NNID is permanently banned by Nintendo. You cannot ask how to fix this issue here.',
        '102-2805': 'System is banned from accessing Nintendo eShop. You cannot ask how to fix this issue here.',
        '102-2812': 'System + linked NNID and access to online services are permanently banned by Nintendo. You cannot ask how to fix this issue here.',
        '102-2813': 'System is banned by Nintendo. You cannot ask how to fix this issue here.',
        '102-2814': 'System is permanently banned from online multiplayer in a/multiple game(s) (preferably Splatoon). You cannot ask how to fix this issue here.',
        '102-2815': 'System is banned from accessing the Nintendo eShop. You cannot ask how to fix this issue here.',
        '102-2816': 'System is banned for a/multiple game(s) (preferably Splatoon) for an unknown duration, by attempting to use modified static.pack/+ game files online. You cannot ask how to fix this issue here.',
        '106-0306': 'NNID is temporarily banned from a/multiple games (preferably Splatoon) online multiplayer. You cannot ask how to fix this issue here.',
        '106-0346': 'NNID is permanently banned from a/multiple games (preferably Splatoon) online multiplayer. You cannot ask how to fix this issue here.',
        '112-1037': 'Incorrect permissions for the default index.html file which prevents the Internet Browser from reading it. This can be fixed by following [this guide](https://wiiu.hacks.guide/#/fix-errcode-112-1037).',
        '115-1009': 'System is permanently banned from Miiverse.',
        '121-0902': 'Permissions missing for the action you are trying to perfrom (Miiverse error).',
        '126-9622': 'Error when attempting to add funds. Maybe try again after a while, or make sure there is no issue with the payment method.',
        '150-1031': 'Disc could not be read. Either the disc is dirty, the lens is dirty, or the disc is unsupported (i.e. not a Wii or Wii U game).',
        '150-2031': 'Disc could not be read. Either the disc is dirty, the lens is dirty, or the disc is unsupported (i.e. not a Wii or Wii U game).',
        '160-0101': '"Generic error". Can happen when formatting a system with CBHC.',
        '160-0102': 'Error in SLC/MLC or USB.',
        '160-0103': '"The system memory is corrupted (MLC)."',
        '160-0104': '"The system memory is corrupted (SLC)."',
        '160-0105': 'USB storage corrupted?',
        '199-9999': 'Usually occurs when trying to run an unsigned title without signature patches, or something unknown(?) is corrupted.',
    }

    switch_errcodes = {
        # Switch
        '007-1037': ['Could not detect an SD card.', None],
        '2001-0125': ['Executed svcCloseHandle on main-thread handle (No known support page)', None],
        '2002-6063': ['Attempted to read eMMC CID from browser? (No known support page)', None],
        '2005-0003': ['You are unable to download software.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/22393/kw/2005-0003'],
        '2016-2101': ['Inserted Tencent-Nintendo (Chinese model) cartridge into regular Switch, which is region locked.', 'https://nintendoswitch.com.cn/support/'],
        '2110-3400': ['This error code indicates the Internet connection you are attempting to use likely requires some type of authentication through a web browser (such as agreeing to terms of service or entering a username and password).', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/22569/kw/2110-3400'],
        '2124-4007': ['System + Nintendo Account are permanently banned by Nintendo. You cannot ask how to fix this issue here.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/28046/kw/2124-4007'],
        '2124-4025': ['Game Card is banned, this "COULD" happen to legal users if so contact Nintendo to allow them to whitelist the Game Card. Otherwise, You cannot ask how to fix this issue here.', None],
        '2124-4027': ['System + Nintendo Account are banned from a game (preferably Splatoon 2) online multiplayer services for a set duration which can be found after checking your email on the account recieving the ban. You cannot ask how to fix this issue here.', None],
        '2162-0002': ['General userland crash', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/22596/kw/2162-0002'],
        '2164-0020': ['Error starting software.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/22539/kw/2164-0020'],
        '2168-0000': ['Illegal opcode. (No known support page)', None],
        '2168-0001': ['Resource/Handle not available.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/29104/kw/2168-0001'],
        '2168-0002': ['Segmentation Fault.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/22518/kw/2168-0002'],
        '2168-0003': ['Memory access must be 4 bytes aligned. (No known support page)', None],
        '2181-4008': ['System is permanently banned by Nintendo. You cannot ask how to fix this issue here.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/42061/kw/2181-4008'],
        '2811-5001': ['General connection error.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/22392/kw/2811-5001'],
        '2124-4517': ['Console banned due a breach of the user agreements. You cannot ask how to fix this issue here.', 'https://en-americas-support.nintendo.com/app/answers/detail/a_id/43652/kw/2124-4517'],
        '2124-4621': ['Online features in foreign games are not available on Tencent-Nintendo Switch (Chinese model).', 'https://nintendoswitch.com.cn/support/']
    }
    
    messages = []

    def get_name(self, d, k, show_unknown=False):
        if k in d:
            return f'{d[k]} ({k})'
        else:
            if show_unknown:
                return f'_Unknown {show_unknown}_ ({k})'  # crappy method
            else:
                return f'{k}'

    async def aaaa(self, rc):
        # i know this is shit that's the point
        if rc == 3735928559:
            self.messages.append(binascii.unhexlify(hex(3273891394255502812531345138727304541163813328167758675079724534358388)[2:]).decode('utf-8'))
        elif rc == 3735927486:
            self.messages.append(binascii.unhexlify(hex(271463605137058211622646033881424078611212374995688473904058753630453734836388633396349994515442859649191631764050721993573)[2:]).decode('utf-8'))
        elif rc == 2343432205:
            self.messages.append(binascii.unhexlify(hex(43563598107828907579305977861310806718428700278286708)[2:]).decode('utf-8'))

    async def convert_zerox(self, rc):
        if not rc & 0x80000000:
            self.messages.append('This is likely not a CTR error code.')
        await self.aaaa(rc)
        desc = rc & 0x3FF
        mod = (rc >> 10) & 0xFF
        summ = (rc >> 21) & 0x3F
        level = (rc >> 27) & 0x1F
        return desc, mod, summ, level, rc

    def nim_3ds_errors(self, err: str):
        """
        Parses 3ds nim error codes between the range of 005-2000 to 005-3023, 005-4200 to 005-4399, 005-4400 to 005-4999, 005-5000 to 005-6999 and 005-7000 to 005-9999.

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

        if len(err) != 8:
            return False

        try:
            err_hi = int(err[:3], 10)
            err_lo = int(err[-4:], 10)
        except ValueError:
            return False

        if err_hi != 5:
            return False

        if 2000 <= err_lo < 3024:
            err_lo -= 2000

            self.messages.append("Module")
            self.messages.append(self.get_name(self.modules, 52))
            self.messages.append("Description")
            self.messages.append(self.get_name(self.descriptions, err_lo))
            return True

        # this range is still a little mystified by another section in nim
        # but this covers one section of it
        elif 4200 <= err_lo < 4400:
            embed_extra = None
            if err_lo == 4399:
                embed_extra = "Or NIM's HTTP result description maximum."
            err_lo -= 4200

            self.messages.append("Module")
            self.messages.append(self.get_name(self.modules, 40))
            self.messages.append("Description")
            self.messages.append(self.get_name(self.descriptions, err_lo))
            if embed_extra:
                self.messages.append("Extra Note")
                self.messages.append(embed_extra)
            return True

        elif 4400 <= err_lo < 5000:
            err_lo -= 4400
            embed_extra = None
            if err_lo < 100:
                desc = f"{err_lo + 100}"
            elif 100 <= err_lo < 500:
                desc = f"{err_lo + 100} or {err_lo}"
                embed_extra = "Likely due to a programming mistake in NIM, this error code range suffers collision.\n"
                embed_extra += "Real HTTP code will vary with what operation it came from."
            else:
                desc = f"{err_lo}"

            self.messages.append("HTTP error code")
            self.messages.append("Code")
            self.messages.append(desc)
            if embed_extra:
                self.messages.append("Extra Note")
                self.messages.append(embed_extra)
            return True

        elif 5000 <= err_lo < 7000:
            err_lo -= 5000

            desc = f"SOAP Message returned ErrorCode {err_lo} on a NIM operation."
            if err_lo == 1999:
                desc += "\nOr beyond 1999. It's maxed out at 005-6999."
            self.messages.append(desc)
            return True

        elif err_lo >= 7000:
            embed_extra = None
            if err_lo == 9999:
                embed_extra = "Also NIM's maximum compacted result to error code."
            elif err_lo == 7000:
                embed_extra = "Also NIM's minimum compacted result to error code."
            err_lo -= 7000

            module = err_lo >> 5
            short_desc = err_lo & 0x1F

            known_desc = []
            unknown_desc = []

            for i in range(0+short_desc, 0x400+short_desc, 0x20):
                if i not in self.descriptions:
                    unknown_desc += [str(i)]
                    continue
                known_desc += [self.get_name(self.descriptions, i)]

            known_desc = "\n".join(known_desc)
            unknown_desc = ", ".join(unknown_desc)

            self.messages.append("Module")
            self.messages.append(self.get_name(self.modules, module))
            if known_desc:
                self.messages.append("Possible known descriptions")
                self.messages.append(known_desc)
            if unknown_desc:
                self.messages.append("Possible unknown descriptions")
                self.messages.append(unknown_desc)
            if embed_extra:
                self.messages.append("Extra Note")
                self.messages.append(embed_extra)
            return True

        return False

    async def err(self, err: str):
        """
        Parses Nintendo and CTR error codes, with a fancy embed. 0x prefix is not required.

        Example:
          .err 0xD960D02B
          .err 022-2634
        """
        if re.match('[0-1][0-9][0-9]\-[0-9][0-9][0-9][0-9]', err):
            self.messages.append(err + (": Nintendo 3DS" if err[0] == "0" else ": Wii U"))
            self.messages.append(f"https://en-americas-support.nintendo.com/app/answers/list/kw/{err}")
            if err in self.errcodes:
                self.messages.append(self.errcodes[err])
            else:
                self.messages.append("I don't know this one! Click the error code for details on Nintendo Support.")

        # 0xE60012
        # Switch Error Codes (w/ website)
        # Switch Error Codes (w/o website)
        elif re.match('[0-9][0-9][0-9][0-9]\-[0-9][0-9][0-9][0-9]', err):
            self.messages.append(err + ": Nintendo Switch")
            self.messages.append("http://en-americas-support.nintendo.com/app/answers/landing/p/897")
            if re.match('2110\-1[0-9][0-9][0-9]', err):
                self.messages.append("http://en-americas-support.nintendo.com/app/answers/detail/a_id/22594")
                self.messages.append("General connection error.")
            elif re.match('2110\-29[0-9][0-9]', err):
                self.messages.append("http://en-americas-support.nintendo.com/app/answers/detail/a_id/22277/p/897")
                self.messages.append("General connection error.")
            elif re.match('2110\-2[0-8][0-9][0-9]', err):
                self.messages.append("http://en-americas-support.nintendo.com/app/answers/detail/a_id/22263/p/897")
                self.messages.append("General connection error.")
            else:
                if err in self.switch_errcodes:
                    self.messages.append(self.switch_errcodes[err][1])
                    self.messages.append(self.switch_errcodes[err][0])
                else:
                    self.messages.append("I don't know this one! Click the error code for details on Nintendo Support.\n\nIf you keep getting this issue and Nintendo Support does not help, and know how to fix it, you should report relevant details to [the Kurisu repository](https://github.com/nh-server/Kurisu/issues) so it can be added to the bot.")
        else:
            try:
                err_num = int(err, 16)
            except ValueError:
                return f"Invalid error code {err}."

            desc, mod, summ, level, rc = await self.convert_zerox(err_num)

            # garbage
            self.messages.append(f"0x{rc:X}")
            self.messages.append("Module")
            self.messages.append(self.get_name(self.modules, mod))
            self.messages.append("Description")
            self.messages.append(self.get_name(self.descriptions, desc))
            self.messages.append("Summary")
            self.messages.append(self.get_name(self.summaries, summ))
            self.messages.append("Level")
            self.messages.append(self.get_name(self.levels, level))
        a = '\n'
        b = a.join(self.messages)
        self.messages.clear()
        return b

command = {'err': 'from nintendoerr import Err|err'}