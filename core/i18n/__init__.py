import json
import os

from core.elements import MessageSession
from database import BotDBUtil


class BotI18n:
    storage = {}
    languages = []
    uselang = 'zh_cn'
    session = {}

    def __init__(self, msg: MessageSession):
        BotI18n.session = msg
        files = os.listdir(os.path.abspath('./core/i18n/lang/'))
        for lang in files:
            obj = json.load(open('./core/i18n/lang/' + lang, 'r'))
            name = lang.split('.')[0]
            BotI18n.languages.append(name)
            BotI18n.storage[name] = obj

        for module in BotDBUtil.Module(msg).enable_modules_list:
            if module.startswith('_lang_'):
                BotI18n.uselang = module.strip('_lang_')
                break
            else:
                continue

    @classmethod
    def get_string(self, key: str):
        strings = BotI18n.storage[BotI18n.uselang]
        if key in strings:
            return strings[key]
        else:
            fallbacks = strings['__metadata__']['fallback']
            for fallback in fallbacks:
                fallbacked = False
                fallback_strings = BotI18n.storage[fallback]
                if key in fallback_strings:
                    fallbacked = True
                    return fallback_strings[key]
                else:
                    continue
            if not fallbacked:
                return key

    @classmethod
    def set_language(self, target):
        module_session = BotDBUtil.Module(BotI18n.session)
        BotI18n.uselang = target
        module_session.disable(f'_lang_{BotI18n.uselang}')
        module_session.enable(f'_lang_{target}')
