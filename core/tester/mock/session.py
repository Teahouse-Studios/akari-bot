import asyncio
import os

from PIL import Image as PILImage

from core.builtins.message.chain import get_message_chain, MessageChain
from core.builtins.message.elements import PlainElement, ImageElement, MentionElement, BaseElement
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession, I18NContext
from core.builtins.utils import confirm_command
from core.config import Config
from core.constants.exceptions import SessionFinished


class MockMessageSession(MessageSession):
    def __init__(self, trigger_msg=None, parent_session=None, is_ci=False):
        if isinstance(trigger_msg, (list, tuple)):
            self._script = list(trigger_msg)
            self.trigger_msg = self._script.pop(0) if self._script else ""
        else:
            self._script = []
            self.trigger_msg = trigger_msg
        self.is_ci = is_ci
        self.parsed_msg = {}
        self.matched_msg = None
        self.sent = []
        self.action = []
        self.parent_session = parent_session

    async def async_init(self, msg):
        self.session_info = await SessionInfo.assign(
            target_id="TEST|Console|0",
            client_name="TEST",
            target_from="TEST",
            sender_id="TEST|0",
            sender_from="TEST",
            sender_name="TEST",
            messages=MessageChain.assign(msg)
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
            self.sent.append(x)
            if isinstance(x, PlainElement):
                self.action.append(x.text)
            elif isinstance(x, ImageElement):
                image_path = await x.get()
                if not self.is_ci:
                    img = PILImage.open(image_path)
                    img.show()
                self.action.append(str(x))
            elif isinstance(x, MentionElement):
                self.action.append(f"<@{x.client}|{str(x.id)}>")
            elif isinstance(x, BaseElement):
                self.action.append(str(x))

        if self.parent_session:
            self.parent_session.sent.extend(self.sent)
            self.parent_session.action.extend(self.action)

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
        raise SessionFinished

    async def send_direct_message(
            self,
            message_chain,
            disable_secret_check=False,
            enable_parse_message=True,
            enable_split_image=True,
            callback=None):
        await self.send_message(message_chain)

    async def delete(self):
        self.action.append("(delete message)")

    async def kick_member(self, user_id, ban=False):
        if isinstance(user_id, str):
            user_id = [user_id]

        for x in user_id:
            self.action.append(f"({"ban" if ban else "kick"} {x})")

    async def restrict_member(self, user_id, duration):
        if isinstance(user_id, str):
            user_id = [user_id]

        for x in user_id:
            self.action.append(f"(restrict {x}{f" ({duration}s)" if duration else ""})")

    async def unrestrict_member(self, user_id):
        if isinstance(user_id, str):
            user_id = [user_id]

        for x in user_id:
            self.action.append(f"(unrestrict {x})")

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
        if Config("no_confirm", False):
            return no_confirm_action

        if message_chain:
            message_chain = get_message_chain(self.session_info, message_chain)
        else:
            message_chain = MessageChain.assign(I18NContext("core.message.confirm"))
        if append_instruction:
            message_chain.append(I18NContext("message.wait.confirm.prompt"))
        await self.send_message(message_chain)
        try:
            confirm_prompt = "\n".join([x.text if isinstance(x, PlainElement) else str(x)
                                       for x in message_chain.as_sendable()])
            if self._script:
                result = self._script.pop(0)
                if delete:
                    await self.delete()
                if result in confirm_command:
                    return True
                return False

            if not self.is_ci:
                result = input(f"{confirm_prompt}\nConfirm: ")
                if delete:
                    await self.delete()
                if result in confirm_command:
                    return True
                return False
            raise IndexError("Input has been exhausted")
        except (EOFError, KeyboardInterrupt):
            os._exit(1)
        except Exception as e:
            raise e

    async def wait_next_message(
        self,
        message_chain=None,
        quote=True,
        delete=False,
        timeout=120,
        append_instruction=True,
    ):
        confirm_prompt = None
        if message_chain:
            message_chain = get_message_chain(self.session_info, message_chain)
            if append_instruction:
                message_chain.append(I18NContext("message.wait.next_message.prompt"))
            await self.send_message(message_chain, quote)
            confirm_prompt = "\n".join([x.text if isinstance(x, PlainElement) else str(x)
                                       for x in message_chain.as_sendable()])
        try:
            if self._script:
                result = self._script.pop(0)
                if delete:
                    await self.delete()
                new_msg = MockMessageSession(parent_session=self, is_ci=self.is_ci)
                new_msg._script = self._script
                self._script = []
                await new_msg.async_init(result)
                return new_msg

            if not self.is_ci:
                if confirm_prompt:
                    result = input(f"{confirm_prompt}\nSend: ")
                else:
                    result = input("Send: ")
                if delete:
                    await self.delete()
                new_msg = MockMessageSession(parent_session=self)
                await new_msg.async_init(result)
                return new_msg
            raise IndexError("Input has been exhausted")
        except (EOFError, KeyboardInterrupt):
            os._exit(1)
        except Exception as e:
            raise e

    async def wait_anyone(
        self,
        message_chain=None,
        quote=False,
        delete=False,
        timeout=120,
    ):
        confirm_prompt = None
        if message_chain:
            message_chain = get_message_chain(self.session_info, message_chain)
            await self.send_message(message_chain, quote)
            confirm_prompt = "\n".join([x.text if isinstance(x, PlainElement) else str(x)
                                       for x in message_chain.as_sendable()])

        try:
            if self._script:
                result = self._script.pop(0)
                if delete:
                    await self.delete()
                new_msg = MockMessageSession(parent_session=self, is_ci=self.is_ci)
                new_msg._script = self._script
                self._script = []
                await new_msg.async_init(result)
                return new_msg

            if not self.is_ci:
                if confirm_prompt:
                    result = input(f"{confirm_prompt}\nSend: ")
                else:
                    result = input("Send: ")
                if delete:
                    await self.delete()
                new_msg = MockMessageSession(parent_session=self)
                await new_msg.async_init(result)
                return new_msg
            raise IndexError("Input has been exhausted")
        except (EOFError, KeyboardInterrupt):
            os._exit(1)
        except Exception as e:
            raise e

    async def wait_reply(
        self,
        message_chain,
        quote=True,
        delete=False,
        timeout=120,
        all_=False,
        append_instruction=True,
    ):
        confirm_prompt = None
        if message_chain:
            message_chain = get_message_chain(self.session_info, message_chain)
            if append_instruction:
                message_chain.append(I18NContext("message.reply.prompt"))
            await self.send_message(message_chain, quote)
            confirm_prompt = "\n".join([x.text if isinstance(x, PlainElement) else str(x)
                                       for x in message_chain.as_sendable()])
        try:
            if self._script:
                result = self._script.pop(0)
                if delete:
                    await self.delete()
                new_msg = MockMessageSession(parent_session=self, is_ci=self.is_ci)
                new_msg._script = self._script
                self._script = []
                await new_msg.async_init(result)
                return new_msg

            if not self.is_ci:
                if confirm_prompt:
                    result = input(f"{confirm_prompt}\nReply: ")
                else:
                    result = input("Reply: ")
                if delete:
                    await self.delete()
                new_msg = MockMessageSession(parent_session=self)
                await new_msg.async_init(result)
                return new_msg
            raise IndexError("Input has been exhausted")
        except (EOFError, KeyboardInterrupt):
            os._exit(1)
        except Exception as e:
            raise e

    async def sleep(self, s):
        await asyncio.sleep(s)

    async def check_permission(self):
        return True

    async def call_onebot_api(self, api_name, **kwargs):
        pass
