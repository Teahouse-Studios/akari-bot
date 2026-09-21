from pathlib import Path
from typing import Any

from milky.models import (
    ImageSubType,
    MentionAllSegmentData,
    MentionSegmentData,
    OutgoingForwardSegment,
    OutgoingForwardSegmentData,
    OutgoingForwardedMessage,
    OutgoingImageSegment,
    OutgoingImageSegmentData,
    OutgoingMentionAllSegment,
    OutgoingMentionSegment,
    OutgoingRecordSegment,
    OutgoingRecordSegmentData,
    OutgoingReplySegment,
    OutgoingTextSegment,
    OutgoingVideoSegment,
    OutgoingVideoSegmentData,
    ReplySegmentData,
    TextSegmentData,
)

from bots.milky.client import milky_bot
from bots.milky.info import client_name, sender_prefix, target_group_prefix
from core.builtins.message.mention import InlineMention, iter_at_code
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.elements import (
    AudioElement,
    ImageElement,
    MentionElement,
    PlainElement,
    VideoElement,
)
from core.builtins.message.internal import Audio, Image, Plain, Raw, Video
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.logger import Logger
from core.utils.media import resolve_media_base64, resolve_media_path

MILKY_IMPL_TEMP_KEY = "milky_impl"


async def get_milky_implementation() -> str | None:
    """获取 Milky 协议端实现名。

    :return: 协议端实现名（小写）；查询失败时返回 None。
    """
    try:
        impl_info = await milky_bot.get_impl_info()
    except Exception:
        Logger.exception("Failed to get Milky implementation info: ")
        return None
    impl_name = str(getattr(impl_info, "impl_name", "") or "").strip().lower()
    return impl_name or None


async def get_available_group_list() -> list[int]:
    """获取机器人所在群组列表。

    :return: 群号列表；查询失败时返回空列表。
    """
    try:
        groups = await milky_bot.get_group_list()
    except Exception:
        Logger.exception("Failed to get Milky group list: ")
        return []
    return [group.group_id for group in groups]


async def get_available_private_list() -> list[int]:
    """获取机器人好友列表。

    :return: 好友 QQ 号列表；查询失败时返回空列表。
    """
    try:
        friends = await milky_bot.get_friend_list()
    except Exception:
        Logger.exception("Failed to get Milky friend list: ")
        return []
    return [friend.user_id for friend in friends]


def message_field(message: Any, key: str, default: Any = None) -> Any:
    """读取 Milky 消息字段，同时兼容原始字典与 SDK 模型。

    :param message: Milky 消息字典或 SDK 模型。
    :param key: 字段名。
    :param default: 字段缺失时的返回值。
    :return: 字段值。
    """
    if isinstance(message, dict):
        return message.get(key, default)
    return getattr(message, key, default)


def iter_message_segments(message: Any) -> list[dict[str, Any]]:
    segments = message_field(message, "segments") or []
    dumped = [segment.model_dump() if hasattr(segment, "model_dump") else segment for segment in segments]
    return [segment for segment in dumped if isinstance(segment, dict)]


async def to_message_chain(message: Any) -> MessageChain:
    """将 Milky 入站消息转换为消息链。

    :param message: Milky 消息字典或 SDK 模型。
    :return: 消息链。
    """
    elements = []
    for segment in iter_message_segments(message):
        segment_type = segment.get("type", "")
        data = segment.get("data") or {}
        if segment_type == "text":
            elements.append(Plain(data.get("text", "")))
        elif segment_type == "mention":
            elements.append(Plain(f"{sender_prefix}|{data.get('user_id', '')}"))
        elif segment_type == "mention_all":
            elements.append(Plain(f"{sender_prefix}|all"))
        elif segment_type == "face":
            elements.append(Raw(f"[CQ:face,id={data.get('face_id', '')}]"))
        elif segment_type == "reply":
            elements.append(Raw(f"[CQ:reply,id={data.get('message_seq', '')}]"))
        elif segment_type == "image":
            elements.append(Image(data.get("temp_url", "")))
        elif segment_type == "record":
            elements.append(Audio(data.get("temp_url", "")))
        elif segment_type == "video":
            elements.append(Video(data.get("temp_url", "")))
        elif segment_type == "file":
            elements.append(Raw(f"[CQ:file,file_id={data.get('file_id', '')},file_name={data.get('file_name', '')}]"))
        elif segment_type == "forward":
            elements.append(Raw(f"[CQ:forward,id={data.get('forward_id', '')}]"))
        elif segment_type == "market_face":
            elements.append(Image(data.get("url", "")))
        elif segment_type == "light_app":
            elements.append(Raw(f"[CQ:json,data={data.get('json_payload', '')}]"))
        elif segment_type == "xml":
            elements.append(Raw(f"[CQ:xml,data={data.get('xml_payload', '')}]"))
        else:
            elements.append(Raw(str(segment)))
    return MessageChain.assign(elements)


def _append_text(segments: list, text: str) -> None:
    if not text:
        return
    if segments and isinstance(segments[-1], OutgoingTextSegment):
        segments[-1].data.text += text
        return
    segments.append(OutgoingTextSegment(data=TextSegmentData(text=text)))


def _append_mention(segments: list, user_id: Any) -> None:
    if str(user_id).isdigit():
        segments.append(OutgoingMentionSegment(data=MentionSegmentData(user_id=int(user_id))))
    else:
        segments.append(OutgoingMentionAllSegment(data=MentionAllSegmentData()))


def _ensure_line_break(segments: list) -> None:
    if isinstance(segments[-1], OutgoingTextSegment):
        if not segments[-1].data.text.endswith("\n"):
            segments[-1].data.text += "\n"
        return
    segments.append(OutgoingTextSegment(data=TextSegmentData(text="\n")))


async def convert_chain_to_segments(
    session_info: SessionInfo,
    message: MessageChain,
    quote: bool = False,
) -> list:
    """将消息链转换为 Milky 出站消息段。

    :param session_info: 会话信息。
    :param message: 待发送的消息链。
    :param quote: 是否引用触发本次发送的消息。
    :return: 出站消息段列表。
    """
    segments: list = []
    if quote and session_info.messages and str(session_info.message_id or "").isdigit():
        segments.append(OutgoingReplySegment(data=ReplySegmentData(message_seq=int(session_info.message_id))))

    # 标记是否已写入过元素内容：首个元素直接落段，其后元素均先补齐换行
    has_content = False

    for element in message.as_sendable(session_info):
        if isinstance(element, PlainElement):
            # AT 码与前后文本同属一条文本，需在文本流内按出现顺序转换为提及段
            parts = iter_at_code(element.text) if element.allow_parse else (element.text,)
            started = False
            for part in parts:
                if isinstance(part, InlineMention) and part.client == client_name:
                    if not started and has_content:
                        _ensure_line_break(segments)
                    started = True
                    _append_mention(segments, part.id)
                else:
                    text = part.raw if isinstance(part, InlineMention) else part
                    if not text:
                        continue
                    if not started and has_content:
                        _ensure_line_break(segments)
                    started = True
                    _append_text(segments, text)
            if started:
                has_content = True
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {element.text}")
        elif isinstance(element, ImageElement):
            image_b64 = await resolve_media_base64(element)
            if image_b64 is None:
                continue
            if has_content:
                _ensure_line_break(segments)
            # `sub_type` 为协议必填字段，缺失会被 SDK 校验拒绝
            segments.append(
                OutgoingImageSegment(
                    data=OutgoingImageSegmentData(uri=f"base64://{image_b64}", sub_type=ImageSubType.NORMAL)
                )
            )
            has_content = True
            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(element)}")
        elif isinstance(element, (AudioElement, VideoElement)):
            media_path = await resolve_media_path(element)
            if media_path is None:
                continue
            if has_content:
                _ensure_line_break(segments)
            media_uri = Path(media_path).as_uri()
            if isinstance(element, AudioElement):
                segments.append(OutgoingRecordSegment(data=OutgoingRecordSegmentData(uri=media_uri)))
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Audio: {str(element)}")
            else:
                segments.append(OutgoingVideoSegment(data=OutgoingVideoSegmentData(uri=media_uri)))
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Video: {str(element)}")
            has_content = True
        elif isinstance(element, MentionElement):
            if has_content:
                _ensure_line_break(segments)
            if element.client == client_name and session_info.target_from == target_group_prefix:
                _append_mention(segments, element.id)
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Mention: {element.client}|{str(element.id)}")
            else:
                # 无法在当前场景提及该用户，以空格占位保持文本可读性
                _append_text(segments, " ")
            has_content = True
    return segments


async def convert_msg_nodes(session_info: SessionInfo, msg_node: MessageNodes) -> OutgoingForwardSegment | None:
    """将消息节点转换为 Milky 合并转发消息段。

    :param session_info: 会话信息。
    :param msg_node: 待发送的消息节点。
    :return: 合并转发消息段；登录信息不可用或所有节点均为空时返回 None。
    """
    account = Temp.data.get("qq_account")
    if account is None:
        Logger.warning("Milky bot account is unavailable, skipping merged forward message.")
        return None
    forwarded_messages = []
    for message in msg_node.values:
        segments = await convert_chain_to_segments(session_info, message)
        if not segments:
            continue
        forwarded_messages.append(
            OutgoingForwardedMessage(
                user_id=int(account),
                sender_name=str(Temp.data.get("qq_nickname") or ""),
                segments=segments,
            )
        )
    if not forwarded_messages:
        return None
    return OutgoingForwardSegment(data=OutgoingForwardSegmentData(messages=forwarded_messages))
