import asyncio
import os
import sys
from time import strftime
from uuid import uuid4

import nio

from bots.matrix import client
from bots.matrix.client import bot
from bots.matrix.info import client_name
from bots.matrix.message import MessageSession, FetchTarget
from core.builtins import PrivateAssets, Url
from core.logger import Logger
from core.parser.message import parser
from core.types import MsgInfo, Session
from core.utils.bot import load_prompt, init_async
from core.utils.info import Info

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + "/assets"))
Url.disable_mm = True


async def on_sync(resp: nio.SyncResponse):
    with open(client.store_path_next_batch, 'w') as fp:
        fp.write(resp.next_batch)


async def on_invite(room: nio.MatrixRoom, event: nio.InviteEvent):
    Logger.info(f"Received room invitation for {room.room_id} ({room.name}) from {event.sender}")
    await bot.join(room.room_id)
    Logger.info(f"Joined room: {room.room_id}")


async def on_room_member(room: nio.MatrixRoom, event: nio.RoomMemberEvent):
    Logger.info(f"Received m.room.member, {event.sender}: {event.prev_membership} -> {event.membership}")
    if event.sender == client.user or event.prev_membership == event.membership:
        pass
    # is_direct = (room.member_count == 1 or room.member_count == 2) and room.join_rule == 'invite'
    # if not is_direct:
    #     resp = await bot.room_get_state_event(room.room_id, 'm.room.member', client.user)
    #     if 'prev_content' in resp.__dict__ and 'is_direct' in resp.__dict__[
    #             'prev_content'] and resp.__dict__['prev_content']['is_direct']:
    #         is_direct = True
    if room.member_count == 1 and event.membership == 'leave':
        resp = await bot.room_leave(room.room_id)
        if resp is nio.ErrorResponse:
            Logger.error(f"Error leaving empty room {room.room_id}: {str(resp)}")
        else:
            Logger.info(f"Left empty room: {room.room_id}")


async def on_message(room: nio.MatrixRoom, event: nio.RoomMessageFormatted):
    if event.sender != bot.user_id and bot.olm:
        for device_id, olm_device in bot.device_store[event.sender].items():
            if bot.olm.is_device_verified(olm_device):
                continue
            bot.verify_device(olm_device)
            Logger.info(f"Trust olm device for device id: {event.sender} -> {device_id}")
    if event.source['content']['msgtype'] == 'm.notice':
        # https://spec.matrix.org/v1.9/client-server-api/#mnotice
        return
    is_room = room.member_count != 2 or room.join_rule != 'invite'
    target_id = room.room_id if is_room else event.sender
    reply_id = None
    if 'm.relates_to' in event.source['content']:
        relatesTo = event.source['content']['m.relates_to']
        if 'm.in_reply_to' in relatesTo:  # rich reply
            reply_id = relatesTo['m.in_reply_to']['event_id']
        if 'rel_type' in relatesTo:
            relType = relatesTo['rel_type']
            if relType == 'm.replace':  # skip edited message
                return
            elif relType == 'm.thread':  # reply in thread
                # https://spec.matrix.org/v1.9/client-server-api/#fallback-for-unthreaded-clients
                if 'is_falling_back' in relatesTo and relatesTo['is_falling_back']:
                    # we regard thread roots as reply target rather than last message in threads
                    reply_id = relatesTo['event_id']
    resp = await bot.get_displayname(event.sender)
    if isinstance(resp, nio.ErrorResponse):
        Logger.error(f"Failed to get display name for {event.sender}")
        return
    sender_name = resp.displayname

    msg = MessageSession(MsgInfo(target_id=f'Matrix|{target_id}',
                                 sender_id=f'Matrix|{event.sender}',
                                 target_from=f'Matrix',
                                 sender_from='Matrix',
                                 sender_name=sender_name,
                                 client_name=client_name,
                                 message_id=event.event_id,
                                 reply_id=reply_id),
                         Session(message=event.source, target=room.room_id, sender=event.sender))
    asyncio.create_task(parser(msg))


async def on_verify(event: nio.KeyVerificationEvent):
    if isinstance(event, nio.KeyVerificationStart):
        await bot.accept_key_verification(event.transaction_id)
        await bot.to_device(bot.key_verifications[event.transaction_id].share_key())
        Logger.info(f"Accepted key verification request {event.transaction_id} from {event.sender} {event.from_device}")
    elif isinstance(event, nio.KeyVerificationCancel):
        Logger.info(f"Key verification {event.transaction_id} is cancelled: {event.reason}")
    elif isinstance(event, nio.KeyVerificationKey):
        Logger.info(
            f"Key verification {event.transaction_id}: {bot.key_verifications[event.transaction_id].get_emoji()}")
        await bot.confirm_short_auth_string(event.transaction_id)
    elif isinstance(event, nio.KeyVerificationMac):
        mac = bot.key_verifications[event.transaction_id].get_mac()
        Logger.info(f"Key verification {event.transaction_id} succeeded: {mac}")
        await bot.to_device(mac)
    else:
        Logger.warn(f"Unknown key verification event: {event}")


async def on_in_room_verify(room: nio.MatrixRoom, event: nio.RoomMessageUnknown):
    if event.msgtype == 'm.key.verification.request':
        Logger.info(f"Cancelling in-room verification in {room.room_id}")
        msg = 'You are requesting a in-room verification to akari-bot. But I does not support in-room-verification at this time, please use to-device verification!'
        await bot.room_send(room.room_id, 'm.room.message', {
            'msgtype': 'm.notice',
            'body': msg
        })
        tx_id = str(uuid4())
        resp = await bot.to_device(nio.ToDeviceMessage(type='m.key.verification.cancel',
                                                       recipient=event.sender,
                                                       recipient_device=event.content['from_device'],
                                                       content={
                                                           "code": "m.invalid_message",
                                                           "reason": msg,
                                                           "transaction_id": tx_id
                                                       },
                                                       ), tx_id)
        Logger.info(resp)
    pass


async def start():
    # Logger.info(f"Trying first sync")
    # sync = await bot.sync()
    # Logger.info(f"First sync finished in {sync.elapsed}ms, dropped older messages")
    # if sync is nio.SyncError:
    #     Logger.error(f"Failed in first sync: {sync.status_code} - {sync.message}")
    try:
        with open(client.store_path_next_batch, 'r') as fp:
            bot.next_batch = fp.read()
            Logger.info(f"Loaded next sync batch from storage: {bot.next_batch}")
    except FileNotFoundError:
        bot.next_batch = 0

    bot.add_response_callback(on_sync, nio.SyncResponse)
    bot.add_event_callback(on_invite, nio.InviteEvent)
    bot.add_event_callback(on_room_member, nio.RoomMemberEvent)
    bot.add_event_callback(on_message, nio.RoomMessageFormatted)
    bot.add_to_device_callback(on_verify, nio.KeyVerificationEvent)
    bot.add_event_callback(on_in_room_verify, nio.RoomMessageUnknown)

    # E2EE setup
    if bot.olm:
        if bot.should_upload_keys:
            Logger.info(f"Uploading matrix E2E encryption keys...")
            resp = await bot.keys_upload()
            if isinstance(
                    resp,
                    nio.KeysUploadError) and "One time key" in resp.message and "already exists." in resp.message:
                Logger.warn(
                    f"Matrix E2EE keys have been uploaded for this session, we are going to force claim them down, although this is very dangerous and should never happen for a clean session: {resp}")
                keys = 0
                while True:
                    resp = await bot.keys_claim({client.user: [client.device_id]})
                    Logger.info(f"Matrix OTK claim resp #{keys+1}: {resp}")
                    if isinstance(resp, nio.KeysClaimError):
                        break
                    keys += 1
                    resp = await bot.keys_upload()
                    if not isinstance(resp, nio.KeysUploadError):
                        Logger.info(f"Successfully uploaded matrix OTK keys after {keys} claims.")
                        break
        megolm_backup_path = os.path.join(client.store_path_megolm_backup, f"restore.txt")
        if os.path.exists(megolm_backup_path):
            pass_path = os.path.join(client.store_path_megolm_backup, f"restore-passphrase.txt")
            assert os.path.exists(pass_path)
            Logger.info(f"Importing megolm keys backup from {megolm_backup_path}")
            with open(pass_path) as f:
                passphrase = f.read()
            await bot.import_keys(megolm_backup_path, passphrase)
            Logger.info(f"Megolm backup imported.")

    # set device name
    if client.device_name:
        asyncio.create_task(bot.update_device(client.device_id, {"display_name": client.device_name}))

    # sync joined room state
    Logger.info(f"Starting sync room full state...")
    # bot.upload_filter(presence={'limit':1},room={'timeline':{'limit':1}})
    resp = await bot.sync(timeout=10000, since=bot.next_batch, full_state=True, set_presence='unavailable')
    await bot._handle_invited_rooms(resp)
    await bot._handle_joined_rooms(resp)

    await init_async()
    await load_prompt(FetchTarget)

    Logger.info(f"starting sync loop")
    await bot.set_presence('online', f"akari-bot {Info.version}")
    await bot.sync_forever(timeout=30000, full_state=False)
    Logger.info(f"sync loop stopped")

    if bot.olm:
        if client.megolm_backup_passphrase:
            backup_date = strftime('%Y-%m')
            backup_path = os.path.join(client.store_path_megolm_backup, f"akaribot-megolm-backup-{backup_date}.txt")
            old_backup_path = os.path.join(
                client.store_path_megolm_backup,
                f"akaribot-megolm-backup-{backup_date}-old.txt")
            if os.path.exists(backup_path):
                if os.path.exists(old_backup_path):
                    os.remove(old_backup_path)
                os.rename(backup_path, old_backup_path)
            Logger.info(f"Saving megolm keys backup to {backup_path}")
            await bot.export_keys(backup_path, client.megolm_backup_passphrase)
            Logger.info(f"Megolm backup exported.")

    await bot.set_presence('offline')


if bot:
    if 'subprocess' in sys.argv:
        Info.subprocess = True
    asyncio.run(start())
