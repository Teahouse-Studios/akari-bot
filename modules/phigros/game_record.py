import struct

import ujson as json
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from core.logger import Logger
from core.utils.text import remove_suffix

levels = {'EZ': 1, 'HD': 2, 'IN': 4, 'AT': 8, }
secret = bytes([232, 150, 154, 210, 165, 64, 37, 155, 151, 145, 144, 139, 136, 230, 191, 3, 30, 109, 33, 149, 110, 250,
                214, 138, 80, 221, 85, 214, 122, 176, 146, 75])
iv = bytes([42, 79, 240, 138, 200, 13, 99, 7, 0, 87, 197, 149, 24, 200, 50, 83])


def decrypt_bytes(encrypted):
    cipher = AES.new(key=secret, mode=AES.MODE_CBC, IV=iv)
    decrypted = cipher.decrypt(encrypted[1:])
    return unpad(decrypted, AES.block_size)


def parse_game_record(file_path):
    rating = json.load(open('./assets/phigros/rating.json', 'r', encoding='utf-8'))
    decrypted_data = {}
    with open(file_path, 'rb+') as rd:
        data = decrypt_bytes(rd.read())
        pos = int(data[0] < 0) + 1
        while (pos < len(data)):
            name_length = data[pos]
            pos += 1
            if name_length == 1:
                continue
            name = data[pos:(pos + name_length)]
            name = remove_suffix(name.decode('utf-8'), '.0')

            pos += name_length
            score_length = data[pos]
            pos += 1

            score = data[pos:(pos + score_length)]
            pos += score_length

            has_score = score[0]
            full_combo = score[1]
            score_pos = 2

            record = {}

            for name_, digit in levels.items():
                if (has_score & digit) == digit:
                    record[name_] = {
                        'score': int.from_bytes(score[score_pos:(score_pos + 4)], byteorder='little', signed=True),
                        'accuracy': struct.unpack('<f', score[(score_pos + 4):(score_pos + 8)])[0],
                        'full_combo': (full_combo & digit) == digit,
                    }
                    n = name.lower()
                    if n in rating:
                        record[name_]['base_rks'] = float(rating[n][name_])
                        if record[name_]['score'] == 1000000:
                            record[name_]['rks'] = float(rating[n][name_])
                        else:
                            record[name_]['rks'] = ((((record[name_]['accuracy'] - 55) / 45) ** 2)
                                                    * float(rating[n][name_])) if record[name_]['accuracy'] >= 70 else 0
                    else:
                        Logger.warn(f'No rating value for {n}.')
                        record[name_]['base_rks'] = 0
                        record[name_]['rks'] = 0
                    score_pos += 8
            decrypted_data[name] = record
    return decrypted_data
