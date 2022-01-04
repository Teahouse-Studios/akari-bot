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
                self.value.append(Plain(elements))
            else:
                self.value.append(
                    Plain(ErrorMessage('机器人尝试发送空文本消息，请联系机器人开发者解决问题。')))
        elif isinstance(elements, (Plain, Image, Voice, Embed)):
            self.value.append(elements)
        elif isinstance(elements, (list, tuple)):
            for e in elements:
                if isinstance(e, ErrorMessage):
                    self.value.append(str(e))
                if isinstance(e, (Plain, Image, Voice, Embed)):
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


__all__ = ["MessageChain"]
