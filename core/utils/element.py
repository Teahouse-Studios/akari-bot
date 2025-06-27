from typing import Union

from discord import Embed as DiscordEmbed

from core.builtins.message.elements import EmbedElement
from core.builtins.message.internal import EmbedField, Embed


def convert_discord_embed(embed: Union[DiscordEmbed, dict]) -> EmbedElement:
    """将DiscordEmbed转换为Embed。

    :param embed: DiscordEmbed。
    :returns: Embed。"""
    embed_ = Embed()
    if isinstance(embed, DiscordEmbed):
        embed = embed.to_dict()
    if isinstance(embed, dict):
        if "title" in embed:
            embed_.title = embed["title"]
        if "description" in embed:
            embed_.description = embed["description"]
        if "url" in embed:
            embed_.url = embed["url"]
        if "color" in embed:
            embed_.color = embed["color"]
        if "timestamp" in embed:
            embed_.timestamp = embed["timestamp"]
        if "footer" in embed:
            embed_.footer = embed["footer"]["text"]
        if "image" in embed:
            embed_.image = embed["image"]
        if "thumbnail" in embed:
            embed_.thumbnail = embed["thumbnail"]
        if "author" in embed:
            embed_.author = embed["author"]
        if "fields" in embed:
            fields = []
            for field_value in embed["fields"]:
                fields.append(
                    EmbedField(
                        field_value["name"], field_value["value"], field_value["inline"]
                    )
                )
            embed_.fields = fields
    return embed_
