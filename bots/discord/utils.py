from datetime import datetime

import discord

from core.builtins.message.elements import EmbedElement
from core.builtins.session.info import SessionInfo


def get_channel_id(session_info: SessionInfo) -> str:
    parts = session_info.target_id.split(session_info.target_from + "|")
    return parts[1] if len(parts) > 1 else ""


def get_sender_id(session_info: SessionInfo) -> str:
    parts = session_info.sender_id.split(session_info.sender_from + "|")
    return parts[1] if len(parts) > 1 else ""


async def convert_embed(embed: EmbedElement, session_info: SessionInfo, attachment_prefix: str = "embed"):
    if isinstance(embed, EmbedElement):
        files = []
        embeds = discord.Embed(
            title=session_info.locale.t_str(embed.title) if embed.title else None,
            description=session_info.locale.t_str(embed.description) if embed.description else None,
            color=embed.color if embed.color else None,
            url=embed.url if embed.url else None,
            timestamp=datetime.fromtimestamp(embed.timestamp) if embed.timestamp else None,
        )
        if embed.image:
            image_name = f"{attachment_prefix}-image.png"
            upload = discord.File(await embed.image.get(), filename=image_name)
            files.append(upload)
            embeds.set_image(url=f"attachment://{image_name}")
        if embed.thumbnail:
            thumbnail_name = f"{attachment_prefix}-thumbnail.png"
            upload = discord.File(await embed.thumbnail.get(), filename=thumbnail_name)
            files.append(upload)
            embeds.set_thumbnail(url=f"attachment://{thumbnail_name}")
        if embed.author:
            embeds.set_author(name=session_info.locale.t_str(embed.author))
        if embed.footer:
            embeds.set_footer(text=session_info.locale.t_str(embed.footer))
        if embed.fields:
            for field in embed.fields:
                embeds.add_field(
                    name=session_info.locale.t_str(field.name),
                    value=session_info.locale.t_str(field.value),
                    inline=field.inline,
                )
        return embeds, files

    raise TypeError("Embed must be an instance of EmbedElement")
