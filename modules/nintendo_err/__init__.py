# ported from kurisu(https://github.com/nh-server/Kurisu/tree/main/cogs/results)
import discord

from core.builtins import Bot
from core.component import module
from core.utils.message import convert_discord_embed
from . import switch, wiiu_support, wiiu_results, ctr_support, ctr_results


class Results:
    """
    Parses game console result codes.
    """

    def fetch(self, error):
        if ctr_support.is_valid(error):
            return ctr_support.get(error)
        if ctr_results.is_valid(error):
            return ctr_results.get(error)
        if wiiu_support.is_valid(error):
            return wiiu_support.get(error)
        if wiiu_results.is_valid(error):
            return wiiu_results.get(error)
        if switch.is_valid(error):
            return switch.get(error)

        # Console name, module name, result, color
        return None

    def err2hex(self, error, suppress_error=False):
        # If it's already hex, just return it.
        if self.is_hex(error):
            return error

        # Only Switch is supported. The other two can only give nonsense results.
        if switch.is_valid(error):
            return switch.err2hex(error, suppress_error)

        if not suppress_error:
            return 'Invalid or unsupported error code format. \
Only Nintendo Switch XXXX-YYYY formatted error codes are supported.'

    def hex2err(self, error, suppress_error=False):
        # Don't bother processing anything if it's not hex.
        if self.is_hex(error):
            if switch.is_valid(error):
                return switch.hex2err(error)
        if not suppress_error:
            return 'This isn\'t a hexadecimal value!'

    def fixup_input(self, user_input):
        # Truncate input to 16 chars so as not to create a huge embed or do
        # eventual regex on a huge string. If we add support for consoles that
        # that have longer error codes, adjust accordingly.
        user_input = user_input[:16]

        # Fix up hex input if 0x was omitted. It's fine if it doesn't convert.
        try:
            user_input = hex(int(user_input, 16))
        except ValueError:
            pass

        return user_input

    def is_hex(self, user_input):
        try:
            user_input = hex(int(user_input, 16))
        except ValueError:
            return False
        return True

    def check_meme(self, err: str) -> str:
        memes = {
            '0xdeadbeef': '都坏掉了，不能吃了。',
            '0xdeadbabe': '我觉得你有问题。',
            '0x8badf00d': '记得垃圾分类。'
        }
        return memes.get(err.casefold())


e = module('err', developers=['OasisAkari', 'kurisu'])


@e.handle('<errcode> {解析任天堂系列主机的报错码并给出原因。}')
async def result(msg: Bot.MessageSession):
    """
    Displays information on game console result codes, with a fancy embed.
    0x prefix is not required for hex input.

    Examples:
      .err 0xD960D02B
      .err D960D02B
      .err 022-2634
      .err 102-2804
      .err 2168-0002
      .err 2-ARVHA-0000
    """
    results = Results()
    err = msg.parsed_msg['<errcode>']
    err = results.fixup_input(err)
    if meme := results.check_meme(err):
        await msg.finish(meme)
    try:
        ret = results.fetch(err)
    except ValueError:
        ret = None

    if ret:
        embed = discord.Embed(title=ret.get_title())
        if ret.extra_description:
            embed.description = ret.extra_description
        for field in ret:
            embed.add_field(name=field.field_name, value=field.message, inline=False)
        await msg.finish(convert_discord_embed(embed))
    else:
        await msg.finish(f'你输入的代码是无效的，或者此功能不支持你使用的主机。')
