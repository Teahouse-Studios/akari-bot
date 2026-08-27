import asyncio
import mimetypes
from pathlib import Path

import nio
from nio.api import RelationshipType

from core.builtins.message.chain import MessageChain, MessageNodes, match_atcode
from core.builtins.message.elements import PlainElement, ImageElement, AudioElement, VideoElement, MentionElement
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.utils.image_split import image_split
from .client import matrix_bot, homeserver_host
from .features import features as matrix_features
from .info import client_name, target_prefix


class MatrixContextManager(ContextManager):
    context: dict[str, tuple[nio.MatrixRoom, nio.Event | None]] = {}
    features: Features = matrix_features

    @staticmethod
    def _response_succeeded(response, operation: str) -> bool:
        """Matrix SDK 会以错误响应对象表示协议失败，而不一定抛异常。"""
        if isinstance(response, nio.ErrorResponse):
            Logger.error(f"Failed to {operation}: {response}")
            return False
        return True

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        # 这里可以添加权限检查的逻辑
        ctx: tuple[nio.MatrixRoom, nio.RoomMessageFormatted] | None = cls.context.get(session_info.session_id)
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
        power_levels_response = await matrix_bot.room_get_state_event(room_id, "m.room.power_levels")
        if isinstance(power_levels_response, nio.ErrorResponse):
            Logger.warning(f"Failed to fetch Matrix power levels for {room_id}: {power_levels_response}")
            return False
        power_levels = power_levels_response.content
        users = power_levels.get("users", {})
        level = users.get(sender_mxid) if sender_mxid in users else power_levels.get("users_default", 0)
        if level and int(level) >= 50:
            return True
        return False

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
    ) -> list[str]:
        msg_ids = []
        try:
            return await cls._send_message(
                session_info,
                message,
                quote=quote,
                msg_ids=msg_ids,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            Logger.exception(f"Failed to send Matrix message to {session_info.target_id}: ")
            return msg_ids

    @classmethod
    async def _send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        msg_ids: list[str] | None = None,
    ) -> list[str]:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        if msg_ids is None:
            msg_ids = []
        ctx: tuple[nio.MatrixRoom, nio.RoomMessageFormatted] | None = cls.context.get(session_info.session_id)
        room, event = None, None
        if ctx:
            room, event = ctx
        reaction_event = isinstance(event, nio.ReactionEvent)
        if isinstance(message, MessageNodes):
            Logger.error("This session does not support message nodes, check if bug exists.")
            return []
        for x in message.as_sendable(session_info):

            async def _send_msg(content):
                reply_to = None
                reply_to_user = None
                if quote and not msg_ids:
                    # Reaction 自身的 event_id 仍须保留为当前消息 ID，供删除 Reaction 等操作使用；
                    # 但回复应引用被反应的原消息，即 Reaction 入口写入的 reply_id。
                    reply_to = (
                        session_info.reply_id if reaction_event and session_info.reply_id else session_info.message_id
                    )
                    reply_to_user = f"@{session_info.get_common_sender_id()}"

                if reply_to:
                    # rich reply
                    content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}
                    # mention target user
                    content["m.mentions"] = {"user_ids": [reply_to_user]}
                    if content.get("msgtype") == "m.notice" and isinstance(event, nio.RoomMessageFormatted):
                        # https://spec.matrix.org/v1.9/client-server-api/#fallbacks-for-rich-replies
                        # todo: standardize fallback for m.image, m.video, m.audio, and m.file
                        event_content = event.source.get("content", {})
                        reply_to_type = event_content.get("msgtype", "")
                        content["body"] = f">{' *' if reply_to_type == 'm.emote' else ''} <{event.sender}> {
                            event_content.get('body', '')
                        }\n\n{x.text}"
                        content["format"] = "org.matrix.custom.html"
                        html_text = x.text
                        html_text = html_text.replace("<", "&lt;").replace(">", "&gt;")
                        html_text = html_text.replace("\n", "<br />")
                        content["formatted_body"] = f'<mx-reply><blockquote><a href="https://matrix.to/#/{
                            room.room_id
                        }/{reply_to}?via={homeserver_host}">In reply to</a>{
                            " *" if reply_to_type == "m.emote" else ""
                        } <a href="https://matrix.to/#/{event.sender}">{event.sender}</a><br/>{
                            event.source.get("content", {}).get("body", "")
                        }</blockquote></mx-reply>{html_text}'

                if isinstance(event, nio.RoomMessageFormatted) and "m.relates_to" in event.source.get("content", {}):
                    relates_to = event.source["content"].get("m.relates_to", {})
                    if "rel_type" in relates_to and relates_to.get("rel_type") == "m.thread":
                        # replying in thread
                        thread_root = relates_to.get("event_id")
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
                if isinstance(resp, nio.ErrorResponse):
                    Logger.error(f"Error while sending message: {str(resp)}")
                else:
                    msg_ids.append(resp.event_id)
                # reply_to = None
                # reply_to_user = None

            if isinstance(x, PlainElement):
                if x.allow_parse:
                    x.text = match_atcode(x.text, client_name, "{uid}")
                content = {"msgtype": "m.notice", "body": x.text}
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
                await _send_msg(content)
            elif isinstance(x, ImageElement):
                split = [x]
                if x.allow_split:
                    Logger.info(f"Split image: {str(x)}")
                    split = await image_split(x)
                for xs in split:
                    path = await xs.get()
                    with open(path, "rb") as image:
                        filename = Path(path).name
                        filesize = Path(path).stat().st_size
                        mimetype = mimetypes.guess_type(path)[0] or "image/png"

                        encrypted = session_info.get_common_target_id() in matrix_bot.encrypted_rooms
                        (upload, upload_encryption) = await matrix_bot.upload(
                            image,
                            content_type=mimetype,
                            filename=filename,
                            encrypt=encrypted,
                            filesize=filesize,
                        )
                        if isinstance(upload, nio.ErrorResponse):
                            Logger.error(f"Failed to upload Matrix image {filename}: {upload}")
                            continue
                        Logger.info(
                            f"Uploaded image {filename} to media repo, uri: {upload.content_uri}, mime: {
                                mimetype
                            }, encrypted: {encrypted}"
                        )
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
            elif isinstance(x, AudioElement):
                path = x.path
                filename = Path(path).name
                filesize = Path(path).stat().st_size
                mimetype = mimetypes.guess_type(path)[0] or "audio/ogg"

                encrypted = session_info.get_common_target_id() in matrix_bot.encrypted_rooms
                with open(path, "rb") as audio:
                    (upload, upload_encryption) = await matrix_bot.upload(
                        audio,
                        content_type=mimetype,
                        filename=filename,
                        encrypt=encrypted,
                        filesize=filesize,
                    )
                if isinstance(upload, nio.ErrorResponse):
                    Logger.error(f"Failed to upload Matrix audio {filename}: {upload}")
                    continue
                Logger.info(
                    f"Uploaded audio {filename} to media repo, uri: {upload.content_uri}, mime: {mimetype}, encrypted: {
                        encrypted
                    }"
                )
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

                Logger.info(f"[Bot] -> [{session_info.target_id}]: Audio: {str(x)}")
                await _send_msg(content)
            elif isinstance(x, VideoElement):
                path = x.path
                filename = Path(path).name
                filesize = Path(path).stat().st_size
                # 默认 mimetype 可以回退至 "video/mp4"
                mimetype = mimetypes.guess_type(path)[0] or "video/mp4"

                encrypted = session_info.get_common_target_id() in matrix_bot.encrypted_rooms
                with open(path, "rb") as video:
                    (upload, upload_encryption) = await matrix_bot.upload(
                        video,
                        content_type=mimetype,
                        filename=filename,
                        encrypt=encrypted,
                        filesize=filesize,
                    )
                if isinstance(upload, nio.ErrorResponse):
                    Logger.error(f"Failed to upload Matrix video {filename}: {upload}")
                    continue
                Logger.info(
                    f"Uploaded video {filename} to media repo, uri: {upload.content_uri}, mime: {mimetype}, encrypted: {
                        encrypted
                    }"
                )

                video_info = {
                    "size": filesize,
                    "mimetype": mimetype,
                }
                if hasattr(x, "width") and x.width:
                    video_info["w"] = x.width
                if hasattr(x, "height") and x.height:
                    video_info["h"] = x.height
                if hasattr(x, "duration") and x.duration:
                    video_info["duration"] = int(x.duration * 1000)  # 规范单位通常为毫秒 (ms)

                if not encrypted:
                    content = {
                        "msgtype": "m.video",
                        "url": upload.content_uri,
                        "body": filename,
                        "info": video_info,
                    }
                else:
                    upload_encryption["url"] = upload.content_uri
                    content = {
                        "msgtype": "m.video",
                        "body": filename,
                        "file": upload_encryption,
                        "info": video_info,
                    }

                Logger.info(f"[Bot] -> [{session_info.target_id}]: Video: {str(x)}")
                await _send_msg(content)
            elif isinstance(x, MentionElement):
                if x.client == client_name:
                    content = {"msgtype": "m.notice", "body": x.id}
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Mention: {x.client}|{x.id}")
                    await _send_msg(content)
        return msg_ids

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
                    resp = await matrix_bot.room_get_state_event(room.room_id, "m.room.member", target_id)
                    if isinstance(resp, nio.ErrorResponse):
                        pass
                    elif resp.content.get("membership") in ["join", "leave", "invite"]:
                        return room
            Logger.info(f"Could not find any exist private room for {target_id}, trying to create one.")
            try:
                resp = await matrix_bot.room_create(
                    visibility=nio.RoomVisibility.private,
                    is_direct=True,
                    preset=nio.RoomPreset.trusted_private_chat,
                    invite=[target_id],
                )
                if isinstance(resp, nio.ErrorResponse):
                    Logger.error(f"Failed to create private messaging room for {target_id}: {resp}")
                    return None
                room_id = resp.room_id
                Logger.info(f"Created private messaging room for {target_id}: {room_id}")
                # room_create 的响应不会立刻写入 AsyncClient.rooms；新房间要到下一次 sync
                # 才会出现。首次私信只需要 room_id，先构造轻量 MatrixRoom 即可立即发送。
                return matrix_bot.rooms.get(room_id) or nio.MatrixRoom(room_id, matrix_bot.user_id)
            except Exception as e:
                Logger.error(f"Failed to create room for {target_id}: {e}")
                return None

    @classmethod
    async def send_private_msg(
        cls,
        session_info: SessionInfo,
        user_id: str,
        message: MessageChain | MessageNodes,
    ) -> list[str]:
        # Matrix 没有独立的私聊通道，私信实为仅含双方的房间，此处先查找该房间，不存在则创建
        mxid = user_id.split("|")[-1]
        if not mxid.startswith("@"):
            mxid = f"@{mxid}"

        try:
            room = await cls._resolve_matrix_room_(
                cls.derive_private_session(session_info, f"{target_prefix}|{mxid}", target_prefix)
            )
            if not room:
                Logger.warning(f"Could not resolve private room for {user_id}, skipping private message send.")
                return []

            return await MatrixContextManager.send_message(
                cls.derive_private_session(session_info, f"{target_prefix}|{room.room_id}", target_prefix),
                message,
                quote=False,
            )
        except Exception:
            Logger.exception(f"Failed to send private message to {user_id}: ")
            return []

    @classmethod
    async def delete_message(
        cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None
    ) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        for m in message_id:
            try:
                response = await matrix_bot.room_redact(session_info.get_common_target_id(), m, reason)
                if not cls._response_succeeded(response, f"delete message {m} in session {session_info.session_id}"):
                    continue
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
                response = await matrix_bot.room_kick(
                    session_info.get_common_target_id(), f"@{x.split('|')[-1]}", reason
                )
                if not cls._response_succeeded(response, f"kick member {x} in channel {session_info.target_id}"):
                    continue
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
                response = await matrix_bot.room_ban(
                    session_info.get_common_target_id(), f"@{x.split('|')[-1]}", reason
                )
                if not cls._response_succeeded(response, f"ban member {x} in channel {session_info.target_id}"):
                    continue
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
                response = await matrix_bot.room_unban(session_info.get_common_target_id(), f"@{x.split('|')[-1]}")
                if not cls._response_succeeded(response, f"unban member {x} in channel {session_info.target_id}"):
                    continue
                Logger.info(f"Unbanned member {x} in channel {session_info.target_id}")
            except Exception:
                Logger.exception(f"Failed to unban member {x} in channel {session_info.target_id}: ")

    @classmethod
    async def add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        ctx = cls.context.get(session_info.session_id)
        event = ctx[1] if ctx else None
        if isinstance(event, nio.ReactionEvent):
            message_id = session_info.reply_id
        if message_id is None:
            Logger.warning(f"Matrix reaction target is unavailable in session {session_info.session_id}.")
            return
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        content = {"m.relates_to": {"rel_type": "m.annotation", "event_id": message_id[-1], "key": emoji}}
        try:
            response = await matrix_bot.room_send(
                session_info.get_common_target_id(), message_type="m.reaction", content=content
            )
            if not cls._response_succeeded(
                response,
                f'add reaction "{emoji}" to message {message_id} in session {session_info.session_id}',
            ):
                return
            Logger.info(f'Added reaction "{emoji}" to message {message_id} in session {session_info.session_id}')
        except Exception:
            Logger.exception(
                f'Failed to add reaction "{emoji}" to message {message_id} in session {session_info.session_id}: '
            )

    @classmethod
    async def remove_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        ctx = cls.context.get(session_info.session_id)
        event = ctx[1] if ctx else None
        if isinstance(event, nio.ReactionEvent):
            message_id = session_info.reply_id
        if message_id is None:
            Logger.warning(f"Matrix reaction target is unavailable in session {session_info.session_id}.")
            return
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")
        if not message_id:
            return

        room_id = session_info.get_common_target_id()
        target_message_id = message_id[-1]
        try:
            async for reaction in matrix_bot.room_get_event_relations(
                room_id,
                target_message_id,
                rel_type=RelationshipType.annotation,
                event_type="m.reaction",
            ):
                reaction_key = getattr(reaction, "key", None)
                if reaction_key is None:
                    reaction_key = reaction.source.get("content", {}).get("m.relates_to", {}).get("key")
                if reaction.sender != matrix_bot.user_id or reaction_key != emoji:
                    continue
                response = await matrix_bot.room_redact(room_id, reaction.event_id)
                if not cls._response_succeeded(
                    response,
                    f'remove reaction "{emoji}" from message {target_message_id} in session {session_info.session_id}',
                ):
                    return
                Logger.info(
                    f'Removed reaction "{emoji}" from message {target_message_id} in session {session_info.session_id}'
                )
                return
            Logger.warning(
                f'Bot reaction "{emoji}" was not found on message {target_message_id} '
                f"in session {session_info.session_id}."
            )
        except Exception:
            Logger.exception(
                f'Failed to remove reaction "{emoji}" from message {target_message_id} '
                f"in session {session_info.session_id}: "
            )

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        try:
            response = await matrix_bot.room_typing(session_info.get_common_target_id(), True)
            cls._response_succeeded(response, f"start typing in session {session_info.session_id}")
        except Exception:
            Logger.exception(f"Failed to start typing in session {session_info.session_id}: ")

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        try:
            response = await matrix_bot.room_typing(session_info.get_common_target_id(), False)
            cls._response_succeeded(response, f"end typing in session {session_info.session_id}")
        except Exception:
            Logger.exception(f"Failed to end typing in session {session_info.session_id}: ")

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        pass


class MatrixFetchedContextManager(MatrixContextManager):
    """
    用于获取会话信息的上下文管理器。
    该管理器在处理消息时会自动获取会话信息。
    """

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
    ) -> list[str]:
        try:
            room = await cls._resolve_matrix_room_(session_info)
            cls.add_context(session_info, (room, None))
            return await super().send_message(
                session_info=session_info,
                message=message,
                quote=quote,
            )
        except Exception as e:
            Logger.exception(f"Failed to send message to {session_info.get_common_target_id()}: {e}")
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
    async def delete_message(
        cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None
    ) -> None:
        try:
            room = await cls._resolve_matrix_room_(session_info)
            cls.add_context(session_info, (room, None))
            await super().delete_message(session_info=session_info, message_id=message_id)
        except Exception as e:
            Logger.exception(f"Failed to delete message in {session_info.get_common_target_id()}: {e}")
        finally:
            cls.del_context(session_info)
