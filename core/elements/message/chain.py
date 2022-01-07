import base64
import ujson as json
import re

from .internal import Plain, Image, Voice, Embed
from core.elements.others import Secret, ErrorMessage
from typing import Union, List, Tuple
from core.logger import Logger


class MessageChain:
    def __init__(self, elements: Union[str, List[Union[Plain, Image, Voice, Embed]],
                                       Tuple[Union[Plain, Image, Voice, Embed]],
                                       Plain, Image, Voice, Embed]):
        self.value = []
        if isinstance(elements, ErrorMessage):
            elements = str(elements)
        if isinstance(elements, str):
            if elements != '':
                elements = Plain(elements)
            else:
                elements = Plain(ErrorMessage('机器人尝试发送空文本消息，请联系机器人开发者解决问题。'))
        if isinstance(elements, (Plain, Image, Voice, Embed)):
            if isinstance(elements, Plain):
                if elements.text != '':
                    elements = match_kecode(elements.text)
            else:
                elements = [elements]
        if isinstance(elements, (list, tuple)):
            for e in elements:
                if isinstance(e, ErrorMessage):
                    self.value.append(str(e))
                if isinstance(e, (Plain, Image, Voice, Embed)):
                    if isinstance(e, Plain):
                        if e.text != '':
                            self.value += match_kecode(e.text)
                    else:
                        self.value.append(e)
                else:
                    Logger.error(f'Unexpected message type: {elements.__dict__}')
                    self.value.append(
                        Plain(ErrorMessage('机器人尝试发送非法消息链，请联系机器人开发者解决问题。')))
        elif isinstance(elements, MessageChain):
            self.value = elements.value
        else:
            self.value.append(
                Plain(ErrorMessage('机器人尝试发送非法消息链，请联系机器人开发者解决问题。')))
        if not self.value:
            self.value.append(Plain(ErrorMessage('机器人尝试发送空消息链，请联系机器人开发者解决问题。')))

    @property
    def is_safe(self):
        for v in self.value:
            if isinstance(v, Plain):
                for secret in Secret.list:
                    if v.text.upper().find(secret.upper()) != -1:
                        return False
            elif isinstance(v, Embed):
                for secret in Secret.list:
                    if v.title.upper().find(secret.upper()) != -1:
                        return False
                    if v.description.upper().find(secret.upper()) != -1:
                        return False
                    if v.footer.upper().find(secret.upper()) != -1:
                        return False
                    if v.author.upper().find(secret.upper()) != -1:
                        return False
                    if v.url.upper().find(secret.upper()) != -1:
                        return False
                    for f in v.fields:
                        if f.name.upper().find(secret.upper()) != -1:
                            return False
                        if f.value.upper().find(secret.upper()) != -1:
                            return False
        return True

    def asSendable(self, embed=True):
        value = []
        for x in self.value:
            if isinstance(x, Embed) and not embed:
                value += x.to_msgchain()
            else:
                value.append(x)
        return value

    def append(self, element):
        self.value.append(element)

    def remove(self, element):
        self.value.remove(element)

    def __str__(self):
        return f'[{", ".join([str(x.__dict__) for x in self.value])}]'

    def __repr__(self):
        return self.value


def match_kecode(text: str) -> List[Union[Plain, Image, Voice, Embed]]:
    split_all = re.split(r'(\[Ke:.*?])', text)
    for x in split_all:
        if x == '':
            split_all.remove('')
    elements = []
    for e in split_all:
        match = re.match(r'\[Ke:(.*?),(.*)]', e)
        if not match:
            if e != '':
                elements.append(Plain(e))
        else:
            element_type = match.group(1).lower()
            args = re.split(r',|,.\s', match.group(2))
            for x in args:
                if x == '':
                    args.remove('')
            if element_type == 'plain':
                for a in args:
                    ma = re.match(r'(.*?)=(.*)', a)
                    if ma:
                        if ma.group(1) == 'text':
                            elements.append(Plain(ma.group(2)))
                        else:
                            elements.append(Plain(a))
                    else:
                        elements.append(Plain(a))
            elif element_type == 'image':
                for a in args:
                    ma = re.match(r'(.*?)=(.*)', a)
                    if ma:
                        img = None
                        if ma.group(1) == 'path':
                            img = Image(path=ma.group(2))
                        if ma.group(1) == 'headers':
                            img.headers = json.loads(str(base64.b64decode(ma.group(2)), "UTF-8"))
                        if img is not None:
                            elements.append(img)
                    else:
                        elements.append(Image(a))
            elif element_type == 'voice':
                for a in args:
                    ma = re.match(r'(.*?)=(.*)', a)
                    if ma:
                        if ma.group(1) == 'path':
                            elements.append(Voice(path=ma.group(2)))
                        else:
                            elements.append(Voice(a))
                    else:
                        elements.append(Voice(a))
    return elements


__all__ = ["MessageChain"]
