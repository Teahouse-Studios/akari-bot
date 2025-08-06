import datetime

import discord

from core.builtins.message.elements import EmbedElement
from core.builtins.session.info import SessionInfo


def get_channel_id(session_info: SessionInfo) -> str:
    return session_info.target_id.split(session_info.target_from + "|")[1]


def get_sender_id(session_info: SessionInfo) -> str:
    return session_info.sender_id.split(session_info.sender_from + "|")[1]


async def convert_embed(embed: EmbedElement, session_info: SessionInfo):
    if isinstance(embed, EmbedElement):
        files = []
        embeds = discord.Embed(
            title=session_info.locale.t_str(embed.title) if embed.title else None,
            description=session_info.locale.t_str(embed.description) if embed.description else None,
            color=embed.color if embed.color else None,
            url=embed.url if embed.url else None,
            timestamp=datetime.datetime.fromtimestamp(embed.timestamp) if embed.timestamp else None
        )
        if embed.image:
            upload = discord.File(await embed.image.get(), filename="image.png")
            files.append(upload)
            embeds.set_image(url="attachment://image.png")
        if embed.thumbnail:
            upload = discord.File(await embed.thumbnail.get(), filename="thumbnail.png")
            files.append(upload)
            embeds.set_thumbnail(url="attachment://thumbnail.png")
        if embed.author:
            embeds.set_author(name=session_info.locale.t_str(embed.author))
        if embed.footer:
            embeds.set_footer(text=session_info.locale.t_str(embed.footer))
        if embed.fields:
            for field in embed.fields:
                embeds.add_field(
                    name=session_info.locale.t_str(field.name),
                    value=session_info.locale.t_str(field.value),
                    inline=field.inline
                )
        return embeds, files

    raise TypeError("Embed must be an instance of EmbedElement")
