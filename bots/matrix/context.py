import mimetypes
from pathlib import Path

import nio

from core.builtins.message.chain import MessageChain, MessageNodes, match_atcode
from core.builtins.message.elements import PlainElement, ImageElement, VoiceElement, MentionElement
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.utils.image import msgnode2image, image_split
from .client import matrix_bot, homeserver_host
from .features import Features
from .info import client_name


class MatrixContextManager(ContextManager):
    context: dict[str, tuple[nio.MatrixRoom, nio.RoomMessageFormatted]] = {}
    features: Features | None = Features

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        # 这里可以添加权限检查的逻辑
        ctx: tuple[nio.MatrixRoom, nio.RoomMessageFormatted] = cls.context.get(session_info.session_id)
        if ctx:
            room, event = ctx
            room_id = room.room_id if room else session_info.get_common_target_id()
            sender = event.sender if event else session_info.get_common_sender_id()
        else:
            room_id = session_info.get_common_target_id()
            sender = session_info.get_common_sender_id()
        if room_id.startswith("@") or sender.startswith("!"):
            return True
        if sender.startswith("@"):
            sender_mxid = sender
        else:
            sender_mxid = f"@{sender}"

        # check room creator for room v12
        create_event_id = "$" + str(room_id)[1:]
        result = await matrix_bot.room_get_event(room_id, create_event_id)
        if isinstance(result, nio.RoomGetEventResponse):
            event = result.event
            assert isinstance(event, nio.RoomCreateEvent)
            if int(event.room_version) >= 12:
                creators = [event.sender]
                event_content = event.source["content"]
                if "additional_creators" in event_content:
                    creators = creators + event_content["additional_creators"]
                Logger.debug(f"Matrix room v12 creators: {creators}")
                if sender_mxid in creators:
                    return True
        else:
            # When the room does not follow MSC4291, ignore it silently
            # IO and other server-side errors are also ignored
            # because I am too lazy to write a detailed check
            pass

        # https://spec.matrix.org/v1.9/client-server-api/#permissions
        power_levels = (
            await matrix_bot.room_get_state_event(room_id, "m.room.power_levels")
        ).content
        level = (
            power_levels["users"][sender_mxid]
            if sender_mxid in power_levels["users"]
            else power_levels["users_default"]
        )
        if level and int(level) >= 50:
            return True
        return False

    @classmethod
    async def send_message(cls,
                           session_info: SessionInfo,
                           message: MessageChain | MessageNodes,
                           quote: bool = True,
                           enable_parse_message: bool = True,
                           enable_split_image: bool = True,
                           ) -> list[str]:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        msg_ids = []
        ctx: tuple[nio.MatrixRoom, nio.RoomMessageFormatted] = cls.context.get(session_info.session_id)
        room, event = None, None
        if ctx:
            room, event = ctx
        if isinstance(message, MessageNodes):
            message = MessageChain.assign(await msgnode2image(message))
        for x in message.as_sendable(session_info, parse_message=enable_parse_message):
            async def _send_msg(content):
                reply_to = None
                reply_to_user = None
                if quote and not msg_ids:
                    reply_to = session_info.message_id
                    reply_to_user = f"@{session_info.get_common_sender_id()}"

                if reply_to:
                    # rich reply
                    content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}
                    # mention target user
                    content["m.mentions"] = {"user_ids": [reply_to_user]}
                    if content["msgtype"] == "m.notice" and event:
                        # https://spec.matrix.org/v1.9/client-server-api/#fallbacks-for-rich-replies
                        # todo: standardize fallback for m.image, m.video, m.audio, and m.file
                        reply_to_type = event.source["content"]["msgtype"]
                        content["body"] = (f">{" *" if reply_to_type == "m.emote" else ""} <{event.sender}> {
                            event.source["content"]["body"]}\n\n{x.text}")
                        content["format"] = "org.matrix.custom.html"
                        html_text = x.text
                        html_text = html_text.replace("<", "&lt;").replace(">", "&gt;")
                        html_text = html_text.replace("\n", "<br />")
                        content["formatted_body"] = (
                            f"<mx-reply><blockquote><a href=\"https://matrix.to/#/{
                                room.room_id}/{reply_to}?via={homeserver_host}\">In reply to</a>{
                                " *" if reply_to_type == "m.emote" else ""} <a href=\"https://matrix.to/#/{
                                event.sender}\">{
                                event.sender}</a><br/>{
                                event.source["content"]["body"]}</blockquote></mx-reply>{html_text}")

                if (
                    event
                    and "m.relates_to" in event.source["content"]
                ):
                    relates_to = event.source["content"]["m.relates_to"]
                    if (
                        "rel_type" in relates_to
                        and relates_to["rel_type"] == "m.thread"
                    ):
                        # replying in thread
                        thread_root = relates_to["event_id"]
                        if reply_to:
                            # reply to msg replying in thread
                            content["m.relates_to"] = {
                                "rel_type": "m.thread",
                                "event_id": thread_root,
                                "is_falling_back": False,
                                "m.in_reply_to": {"event_id": reply_to},
                            }
                        else:
                            # reply in thread
                            content["m.relates_to"] = {
                                "rel_type": "m.thread",
                                "event_id": thread_root,
                                "is_falling_back": True,
                                "m.in_reply_to": {"event_id": session_info.message_id},
                            }
                resp = await matrix_bot.room_send(
                    session_info.get_common_target_id(),
                    "m.room.message",
                    content,
                    ignore_unverified_devices=True,
                )
                if "status_code" in resp.__dict__:
                    Logger.error(f"Error while sending message: {str(resp)}")
                else:
                    msg_ids.append(resp.event_id)
                # reply_to = None
                # reply_to_user = None

            if isinstance(x, PlainElement):
                if enable_parse_message:
                    x.text = match_atcode(x.text, client_name, "{uid}")
                content = {"msgtype": "m.notice", "body": x.text}
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
                await _send_msg(content)
            elif isinstance(x, ImageElement):
                split = [x]
                if enable_split_image:
                    Logger.info(f"Split image: {str(x)}")
                    split = await image_split(x)
                for xs in split:
                    path = await xs.get()
                    with open(path, "rb") as image:
                        filename = Path(path).name
                        filesize = Path(path).stat().st_size
                        (content_type, content_encoding) = mimetypes.guess_type(path)
                        if not content_type or not content_encoding:
                            content_type = "image"
                            content_encoding = "png"
                        mimetype = f"{content_type}/{content_encoding}"

                        encrypted = session_info.get_common_target_id() in matrix_bot.encrypted_rooms
                        (upload, upload_encryption) = await matrix_bot.upload(
                            image,
                            content_type=mimetype,
                            filename=filename,
                            encrypt=encrypted,
                            filesize=filesize,
                        )
                        Logger.info(
                            f"Uploaded image {filename} to media repo, uri: {
                                upload.content_uri}, mime: {mimetype}, encrypted: {encrypted}")
                        # todo: provide more image info
                        if not encrypted:
                            content = {
                                "msgtype": "m.image",
                                "url": upload.content_uri,
                                "body": filename,
                                "info": {
                                    "size": filesize,
                                    "mimetype": mimetype,
                                },
                            }
                        else:
                            upload_encryption["url"] = upload.content_uri
                            content = {
                                "msgtype": "m.image",
                                "body": filename,
                                "file": upload_encryption,
                                "info": {
                                    "size": filesize,
                                    "mimetype": mimetype,
                                },
                            }
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(xs)}")
                        await _send_msg(content)
            elif isinstance(x, VoiceElement):
                path = x.path
                filename = Path(path).name
                filesize = Path(path).stat().st_size
                (content_type, content_encoding) = mimetypes.guess_type(path)
                if not content_type or not content_encoding:
                    content_type = "audio"
                    content_encoding = "ogg"
                mimetype = f"{content_type}/{content_encoding}"

                encrypted = session_info.get_common_target_id() in matrix_bot.encrypted_rooms
                with open(path, "rb") as audio:
                    (upload, upload_encryption) = await matrix_bot.upload(
                        audio,
                        content_type=mimetype,
                        filename=filename,
                        encrypt=encrypted,
                        filesize=filesize,
                    )
                Logger.info(f"Uploaded audio {filename} to media repo, uri: {
                    upload.content_uri}, mime: {mimetype}, encrypted: {encrypted}")
                # todo: provide audio duration info
                if not encrypted:
                    content = {
                        "msgtype": "m.audio",
                        "url": upload.content_uri,
                        "body": filename,
                        "info": {
                            "size": filesize,
                            "mimetype": mimetype,
                        },
                    }
                else:
                    upload_encryption["url"] = upload.content_uri
                    content = {
                        "msgtype": "m.audio",
                        "body": filename,
                        "file": upload_encryption,
                        "info": {
                            "size": filesize,
                            "mimetype": mimetype,
                        },
                    }

                Logger.info(f"[Bot] -> [{session_info.target_id}]: Voice: {str(x)}")
                await _send_msg(content)
            elif isinstance(x, MentionElement):
                if x.client == client_name:
                    content = {"msgtype": "m.notice", "body": x.id}
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Mention: {x.client}|{x.id}")
                    await _send_msg(content)
        return msg_ids

    @classmethod
    async def delete_message(cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        for m in message_id:
            try:
                await matrix_bot.room_redact(session_info.get_common_target_id(), m, reason)
                Logger.info(f"Deleted message {m} in session {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to delete message {m} in session {session_info.session_id}: ")

    @classmethod
    async def kick_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        for x in user_id:
            try:
                await matrix_bot.room_kick(session_info.get_common_target_id(), f"@{x.split("|")[-1]}", reason)
                Logger.info(f"Kicked member {x} in channel {session_info.target_id}")
            except Exception:
                Logger.exception(f"Failed to kick member {x} in channel {session_info.target_id}: ")

    @classmethod
    async def ban_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        for x in user_id:
            try:
                await matrix_bot.room_ban(session_info.get_common_target_id(), f"@{x.split("|")[-1]}", reason)
                Logger.info(f"Banned member {x} in channel {session_info.target_id}")
            except Exception:
                Logger.exception(f"Failed to ban member {x} in channel {session_info.target_id}: ")

    @classmethod
    async def unban_member(cls, session_info: SessionInfo, user_id: str | list[str]) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        for x in user_id:
            try:
                await matrix_bot.room_unban(session_info.get_common_target_id(), f"@{x.split("|")[-1]}")
                Logger.info(f"Unbanned member {x} in channel {session_info.target_id}")
            except Exception:
                Logger.exception(f"Failed to unban member {x} in channel {session_info.target_id}: ")

    @classmethod
    async def add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        content = {
            "m.relates_to": {
                "rel_type": "m.annotation",
                "event_id": message_id[-1],
                "key": emoji
            }
        }
        try:
            await matrix_bot.room_send(
                session_info.get_common_target_id(),
                message_type="m.reaction",
                content=content
            )
            Logger.info(f"Added reaction \"{emoji}\" to message {message_id} in session {session_info.session_id}")
        except Exception:
            Logger.exception(f"Failed to add reaction \"{emoji}\" to message {
                             message_id} in session {session_info.session_id}: ")

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        await matrix_bot.room_typing(session_info.get_common_target_id(), True)

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        await matrix_bot.room_typing(session_info.get_common_target_id(), False)

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        pass


class MatrixFetchedContextManager(MatrixContextManager):
    """
    用于获取会话信息的上下文管理器。
    该管理器在处理消息时会自动获取会话信息。
    """

    @staticmethod
    async def _resolve_matrix_room_(session_info: SessionInfo) -> nio.MatrixRoom | None:
        target_id: str = session_info.get_common_target_id()
        if target_id.startswith("@"):
            # find private messaging room
            for room in matrix_bot.rooms:
                room = matrix_bot.rooms[room]
                if room.join_rule == "invite" and (
                    (room.member_count == 2 and target_id in room.users)
                    or (room.member_count == 1 and target_id in room.invited_users)
                ):
                    resp = await matrix_bot.room_get_state_event(
                        room.room_id, "m.room.member", target_id
                    )
                    if resp is nio.ErrorResponse:
                        pass
                    elif resp.content["membership"] in ["join", "leave", "invite"]:
                        return room
            Logger.info(
                f"Could not find any exist private room for {target_id}, trying to create one."
            )
            try:
                resp = await matrix_bot.room_create(
                    visibility=nio.RoomVisibility.private,
                    is_direct=True,
                    preset=nio.RoomPreset.trusted_private_chat,
                    invite=[target_id],
                )
                room = resp.room_id
                Logger.info(f"Created private messaging room for {target_id}: {room}")
                return matrix_bot.rooms[room]
            except Exception as e:
                Logger.error(f"Failed to create room for {target_id}: {e}")
                return None

    @classmethod
    async def send_message(cls,
                           session_info: SessionInfo,
                           message: MessageChain | MessageNodes,
                           quote: bool = True,
                           enable_parse_message: bool = True,
                           enable_split_image: bool = True,
                           ) -> list[str]:
        try:
            room = await cls._resolve_matrix_room_(session_info)
            cls.add_context(session_info, (room, None))
            return await super().send_message(session_info=session_info,
                                              message=message,
                                              quote=quote,
                                              enable_parse_message=enable_parse_message,
                                              enable_split_image=enable_split_image)
        except Exception as e:
            Logger.exception(
                f"Failed to send message to {session_info.get_common_target_id()}: {e}")
            return []
        finally:
            cls.del_context(session_info)

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        try:
            room = await cls._resolve_matrix_room_(session_info)
            if not room:
                return False
            cls.add_context(session_info, (room, None))
            return await super().check_native_permission(session_info)
        except Exception as e:
            Logger.exception(f"Failed to check permission for {session_info.get_common_target_id()}: {e}")
            return False
        finally:
            cls.del_context(session_info)

    @classmethod
    async def delete_message(cls, session_info: SessionInfo, message_id: list[str]) -> None:
        try:
            room = await cls._resolve_matrix_room_(session_info)
            cls.add_context(session_info, (room, None))
            await super().delete_message(session_info=session_info, message_id=message_id)
        except Exception as e:
            Logger.exception(f"Failed to delete message in {session_info.get_common_target_id()}: {e}")
        finally:
            cls.del_context(session_info)
