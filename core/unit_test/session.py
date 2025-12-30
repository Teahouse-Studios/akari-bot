import asyncio

from PIL import Image as PILImage

from core.builtins.message.chain import get_message_chain, MessageChain
from core.builtins.message.elements import PlainElement, ImageElement, MentionElement, BaseElement
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants import FinishedException


class TestMessageSession(MessageSession):
    def __init__(self, trigger_msg: str):
        self.trigger_msg = trigger_msg
        self.parsed_msg = {}
        self.matched_msg = None
        self.sent_msg = []
        self.action = []

    async def async_init(self):
        self.session_info = await SessionInfo.assign(
            target_id="TEST|Console|0",
            client_name="TEST",
            target_from="TEST",
            sender_id="TEST|0",
            sender_from="TEST",
            sender_name="TEST",
            messages=MessageChain.assign(self.trigger_msg),
            require_enable_modules=False
        )

    async def send_message(
            self,
            message_chain,
            quote=True,
            disable_secret_check=False,
            enable_parse_message=True,
            enable_split_image=True,
            callback=None):
        message = get_message_chain(self.session_info, chain=message_chain)

        for x in message.as_sendable(self.session_info, parse_message=enable_parse_message):
            if isinstance(x, PlainElement):
                self.sent_msg.append(x.text)
                self.action.append(x.text)
            elif isinstance(x, ImageElement):
                image_path = await x.get()
                img = PILImage.open(image_path)
                img.show()
                self.sent_msg.append(str(x))
                self.action.append(str(x))
            elif isinstance(x, MentionElement):
                self.sent_msg.append(f"<@{x.client}|{str(x.id)}>")
                self.action.append(f"<@{x.client}|{str(x.id)}>")
            elif isinstance(x, BaseElement):
                self.sent_msg.append(str(x))
                self.action.append(str(x))
            else:
                pass

    async def finish(
            self,
            message_chain=None,
            quote=True,
            disable_secret_check=False,
            enable_parse_message=True,
            enable_split_image=True,
            callback=None):
        if message_chain:
            await self.send_message(message_chain)
        raise FinishedException

    async def send_direct_message(
            self,
            message_chain,
            quote=True,
            disable_secret_check=False,
            enable_parse_message=True,
            enable_split_image=True,
            callback=None):
        await self.send_message(message_chain)

    async def delete(self):
        self.action.append("(delete message)")

    async def add_reaction(self, emoji):
        self.action.append(f"(add reaction {emoji})")

    async def remove_reaction(self, emoji):
        self.action.append(f"(remove reaction {emoji})")

    async def check_native_permission(self):
        return True

    async def handle_error_signal(self):
        pass

    async def hold(self):
        self.action.append("(holding context)")

    async def release(self):
        self.action.append("(release context)")

    async def start_typing(self):
        pass

    async def end_typing(self):
        pass

    async def wait_confirm(
        self,
        message_chain=None,
        quote=True,
        delete=True,
        timeout=120,
        append_instruction=True,
        no_confirm_action=True
    ):
        ...
        return no_confirm_action

    async def wait_next_message(
        self,
        message_chain=None,
        quote=True,
        delete=False,
        timeout=120,
        append_instruction=True,
        add_confirm_reaction=False,
    ):
        ...

    async def wait_reply(
        self,
        message_chain,
        quote=True,
        delete=False,
        timeout=120,
        all_=False,
        append_instruction=True,
        add_confirm_reaction=False,
    ):
        ...

    async def wait_anyone(
        self,
        message_chain=None,
        quote=False,
        delete=False,
        timeout=120,
    ):
        ...

    async def sleep(self, s):
        await asyncio.sleep(s)

    def check_super_user(self):
        return True

    async def check_permission(self):
        return True

    async def qq_call_api(self, api_name, **kwargs):
        pass
