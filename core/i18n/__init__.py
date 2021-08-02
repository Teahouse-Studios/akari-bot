import os
import json

from core.elements import MessageSession
from database import BotDBUtil

class BotI18n:
    def __init__(self, msg: MessageSession):
        self.session = msg
        files = os.listdir(os.path.abspath('./core/i18n/lang/'))
        self.storage = {}
        self.languages: list = []
        self.uselang = 'zh_cn'
        for lang in files:
            obj = json.load(open('./core/i18n/lang/' + lang, 'r'))
            name = lang.split('.')[0]
            self.languages.append(name)
            self.storage[name] = obj

        for module in BotDBUtil.Module(msg).enable_modules_list:
            if module.startswith('_lang_'):
                self.uselang = module.strip('_lang_')
                break
            else:
                continue

    @classmethod
    def get_string(self, key: str):
        strings = self.storage[self.uselang]
        if key in strings:
            return strings[key]
        else:
            fallbacks = strings['__metadata__']['fallback']
            for fallback in fallbacks:
                fallbacked = False
                fallback_strings = self.storage[fallback]
                if key in fallback_strings:
                    fallbacked = True
                    return fallback_strings[key]
                else:
                    continue
            if not fallbacked:
                return key

    @classmethod
    def set_language(self, target):
        BotDBUtil.Module.disable(f'_lang_{self.uselang}')
        BotDBUtil.Module.enable(f'_lang_{target}')
