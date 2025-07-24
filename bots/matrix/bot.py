import asyncio
import os
from time import strftime
from uuid import uuid4

import nio

from bots.matrix import client
from bots.matrix.client import matrix_bot
from bots.matrix.context import MatrixContextManager, MatrixFetchedContextManager
from bots.matrix.info import *
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, Image, Voice
from core.builtins.session.info import SessionInfo
from core.client.init import client_init
from core.config import Config
from core.constants.default import ignored_sender_default
from core.logger import Logger
from core.queue.client import JobQueueClient

Bot.register_bot(client_name=client_name)

ctx_id = Bot.register_context_manager(MatrixContextManager)
Bot.register_context_manager(MatrixFetchedContextManager, fetch_session=True)

ignored_sender = Config("ignored_sender", ignored_sender_default)


async def on_sync(resp: nio.SyncResponse):
    with open(client.store_path_next_batch, "w") as fp:
        fp.write(resp.next_batch)


async def on_invite(room: nio.MatrixRoom, event: nio.InviteEvent):
    Logger.info(
        f"Received room invitation for {room.room_id} ({room.name}) from {event.sender}"
    )
    await matrix_bot.join(room.room_id)
    Logger.info(f"Joined room: {room.room_id}")


async def on_room_member(room: nio.MatrixRoom, event: nio.RoomMemberEvent):
    Logger.info(
        f"Received m.room.member, {event.sender}: {event.prev_membership} -> {event.membership}"
    )
    # is_direct = (room.member_count == 1 or room.member_count == 2) and room.join_rule == "invite"
    # if not is_direct:
    #     resp = await bot.room_get_state_event(room.room_id, "m.room.member", client.user)
    #     if "prev_content" in resp.__dict__ and "is_direct" in resp.__dict__[
    #             "prev_content"] and resp.__dict__["prev_content"]["is_direct"]:
    #         is_direct = True
    if room.member_count == 1 and event.membership == "leave":
        resp = await matrix_bot.room_leave(room.room_id)
        if resp is nio.ErrorResponse:
            Logger.error(f"Error while leaving empty room {room.room_id}: {str(resp)}")
        else:
            Logger.info(f"Left empty room: {room.room_id}")


async def to_message_chain(event: nio.RoomMessageFormatted, reply_id: str = None, target_id: str = None):
    if not event.source:
        return MessageChain.assign([])
    content = event.source["content"]
    msgtype = content["msgtype"]
    if msgtype == "m.emote":
        msgtype = "m.text"
    if msgtype == "m.text":  # compatible with py38
        text = str(content["body"])
        if reply_id:
            # redact the fallback line for rich reply
            # https://spec.matrix.org/v1.9/client-server-api/#fallbacks-for-rich-replies
            while text.startswith("> "):
                text = "".join(text.splitlines(keepends=True)[1:])
        return MessageChain.assign(Plain(text.strip()))
    if msgtype == "m.image":
        url = None
        if "url" in content:
            url = str(content["url"])
        elif "file" in content:
            # todo: decrypt image
            # url = str(content["file"]["url"])
            return MessageChain.assign([])
        else:
            Logger.error(f"Got invalid m.image message from {target_id}")
        return MessageChain.assign(Image(await matrix_bot.mxc_to_http(url)))
    if msgtype == "m.audio":
        url = str(content["url"])
        return MessageChain.assign(Voice(await matrix_bot.mxc_to_http(url)))
    Logger.error(f"Got unknown msgtype: {msgtype}")
    return MessageChain.assign([])


async def on_message(room: nio.MatrixRoom, event: nio.RoomMessageFormatted):
    if event.sender != matrix_bot.user_id and matrix_bot.olm:
        for device_id, olm_device in matrix_bot.device_store[event.sender].items():
            if matrix_bot.olm.is_device_verified(olm_device):
                continue
            matrix_bot.verify_device(olm_device)
            Logger.info(
                f"Trust olm device for device id: {event.sender} -> {device_id}"
            )
    if event.source["content"]["msgtype"] == "m.notice":
        # https://spec.matrix.org/v1.9/client-server-api/#mnotice
        return
    target_id = f"{target_prefix}|{room.room_id}"
    sender_id = f"{sender_prefix}|{event.sender}"
    if sender_id in ignored_sender:
        return
    reply_id = None
    if "m.relates_to" in event.source["content"]:
        relatesTo = event.source["content"]["m.relates_to"]
        if "m.in_reply_to" in relatesTo:  # rich reply
            reply_id = relatesTo["m.in_reply_to"]["event_id"]
        if "rel_type" in relatesTo:
            relType = relatesTo["rel_type"]
            if relType == "m.replace":  # skip edited message
                return
            if relType == "m.thread":  # reply in thread
                # https://spec.matrix.org/v1.9/client-server-api/#fallback-for-unthreaded-clients
                if "is_falling_back" in relatesTo and relatesTo["is_falling_back"]:
                    # we regard thread roots as reply target rather than last message in threads
                    reply_id = relatesTo["event_id"]
    resp = await matrix_bot.get_displayname(event.sender)
    if isinstance(resp, nio.ErrorResponse):
        Logger.error(f"Failed to get display name for {event.sender}")
        return

    msg_chain = await to_message_chain(event, reply_id, target_id)

    session = await SessionInfo.assign(target_id=target_id,
                                       sender_id=sender_id,
                                       sender_name=resp.displayname,
                                       target_from=target_prefix,
                                       sender_from=sender_prefix,
                                       client_name=client_name,
                                       message_id=str(event.event_id),
                                       reply_id=reply_id,
                                       messages=msg_chain,
                                       ctx_slot=ctx_id
                                       )

    await Bot.process_message(session, (room, event))


async def on_verify(event: nio.KeyVerificationEvent):
    if isinstance(event, nio.KeyVerificationStart):
        await matrix_bot.accept_key_verification(event.transaction_id)
        await matrix_bot.to_device(matrix_bot.key_verifications[event.transaction_id].share_key())
        Logger.info(
            f"Accepted key verification request {event.transaction_id} from {event.sender} {event.from_device}"
        )
    elif isinstance(event, nio.KeyVerificationCancel):
        Logger.info(
            f"Key verification {event.transaction_id} is cancelled: {event.reason}"
        )
    elif isinstance(event, nio.KeyVerificationKey):
        Logger.info(
            f"Key verification {event.transaction_id}: {matrix_bot.key_verifications[event.transaction_id].get_emoji()}"
        )
        await matrix_bot.confirm_short_auth_string(event.transaction_id)
    elif isinstance(event, nio.KeyVerificationMac):
        mac = matrix_bot.key_verifications[event.transaction_id].get_mac()
        Logger.info(f"Key verification {event.transaction_id} succeeded: {mac}")
        await matrix_bot.to_device(mac)
    else:
        Logger.warning(f"Unknown key verification event: {event}")


async def on_in_room_verify(room: nio.MatrixRoom, event: nio.RoomMessageUnknown):
    if event.msgtype == "m.key.verification.request":
        Logger.info(f"Cancelling in-room verification in {room.room_id}")
        msg = "You are requesting a in-room verification to AkariBot. But I does not support in-room-verification at this time, please use to-device verification!"
        await matrix_bot.room_send(
            room.room_id, "m.room.message", {"msgtype": "m.notice", "body": msg}
        )
        tx_id = str(uuid4())
        resp = await matrix_bot.to_device(
            nio.ToDeviceMessage(
                type="m.key.verification.cancel",
                recipient=event.sender,
                recipient_device=event.content["from_device"],
                content={
                    "code": "m.invalid_message",
                    "reason": msg,
                    "transaction_id": tx_id,
                },
            ),
            tx_id,
        )
        Logger.info(resp)


async def start():
    # Logger.info(f"Trying first sync")
    # sync = await bot.sync()
    # Logger.info(f"First sync finished in {sync.elapsed}ms, dropped older messages")
    # if sync is nio.SyncError:
    #     Logger.error(f"Failed in first sync: {sync.status_code} - {sync.message}")
    try:
        with open(client.store_path_next_batch, "r", encoding="utf-8") as fp:
            matrix_bot.next_batch = fp.read()
            Logger.info(f"Loaded next sync batch from storage: {matrix_bot.next_batch}")
    except FileNotFoundError:
        matrix_bot.next_batch = 0

    matrix_bot.add_response_callback(on_sync, nio.SyncResponse)
    matrix_bot.add_event_callback(on_invite, nio.InviteEvent)
    matrix_bot.add_event_callback(on_room_member, nio.RoomMemberEvent)
    matrix_bot.add_event_callback(on_message, nio.RoomMessageFormatted)
    matrix_bot.add_to_device_callback(on_verify, nio.KeyVerificationEvent)
    matrix_bot.add_event_callback(on_in_room_verify, nio.RoomMessageUnknown)

    # E2EE setup
    if matrix_bot.olm:
        if matrix_bot.should_upload_keys:
            Logger.info("Uploading matrix E2E encryption keys...")
            resp = await matrix_bot.keys_upload()
            if (
                isinstance(resp, nio.KeysUploadError)
                and "One time key" in resp.message
                and "already exists." in resp.message
            ):
                Logger.warning(
                    f"Matrix E2EE keys have been uploaded for this session, we are going to force claim them down, although this is very dangerous and should never happen for a clean session: {resp}")
                keys = 0
                while True:
                    resp = await matrix_bot.keys_claim({client.user: [client.device_id]})
                    Logger.info(f"Matrix OTK claim resp #{keys + 1}: {resp}")
                    if isinstance(resp, nio.KeysClaimError):
                        break
                    keys += 1
                    resp = await matrix_bot.keys_upload()
                    if not isinstance(resp, nio.KeysUploadError):
                        Logger.success(
                            f"Successfully uploaded matrix OTK keys after {keys} claims."
                        )
                        break
        megolm_backup_path = os.path.join(
            client.store_path_megolm_backup, "restore.txt"
        )
        if os.path.exists(megolm_backup_path):
            pass_path = os.path.join(
                client.store_path_megolm_backup, "restore-passphrase.txt"
            )
            if not os.path.exists(pass_path):
                Logger.error(f"Passphrase file {pass_path} not found.")
                return
            Logger.info(f"Importing megolm keys backup from {megolm_backup_path}")
            with open(pass_path) as f:
                passphrase = f.read()
            await matrix_bot.import_keys(megolm_backup_path, passphrase)
            Logger.info("Megolm backup imported.")

    # set device name
    if client.device_name:
        asyncio.create_task(
            matrix_bot.update_device(client.device_id, {"display_name": client.device_name})
        )

    # sync joined room state
    Logger.info("Starting sync room full state...")
    # bot.upload_filter(presence={"limit":1},room={"timeline":{"limit":1}})
    resp = await matrix_bot.sync(
        timeout=10000, since=matrix_bot.next_batch, full_state=True, set_presence="unavailable"
    )
    await matrix_bot._handle_invited_rooms(resp)
    await matrix_bot._handle_joined_rooms(resp)

    await client_init(target_prefix_list, sender_prefix_list)

    Logger.info("starting sync loop...")
    version = await JobQueueClient.get_bot_version()
    await matrix_bot.set_presence("online", f"AkariBot {version}")
    await matrix_bot.sync_forever(timeout=30000, full_state=False)
    Logger.info("sync loop stopped.")

    if matrix_bot.olm:
        if client.megolm_backup_passphrase:
            backup_date = strftime("%Y-%m")
            backup_path = os.path.join(
                client.store_path_megolm_backup,
                f"akaribot-megolm-backup-{backup_date}.txt",
            )
            old_backup_path = os.path.join(
                client.store_path_megolm_backup,
                f"akaribot-megolm-backup-{backup_date}-old.txt",
            )
            if os.path.exists(backup_path):
                if os.path.exists(old_backup_path):
                    os.remove(old_backup_path)
                os.rename(backup_path, old_backup_path)
            Logger.info(f"Saving megolm keys backup to {backup_path}")
            await matrix_bot.export_keys(backup_path, client.megolm_backup_passphrase)
            Logger.info("Megolm backup exported.")

    await matrix_bot.set_presence("offline")


if matrix_bot and Config("enable", False, table_name="bot_matrix"):
    loop = asyncio.new_event_loop()
    loop.run_until_complete(start())
