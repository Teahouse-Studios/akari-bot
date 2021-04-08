# copied from kurisu(https://github.com/nh-server/Kurisu/tree/main/cogs/results)
import discord

from core.template import sendMessage
from . import switch, wiiu_support, wiiu_results, ctr_support, ctr_results


class ctx:
    @classmethod
    async def send(cls, kwargs, msg=False, embed=False):
        def convertdict(ele: dict):
            emsglst = []
            if 'title' in ele:
                emsglst.append(ele['title'])
            if 'url' in ele:
                emsglst.append(ele['url'])
            if 'fields' in ele:
                for field_value in ele['fields']:
                    emsglst.append(field_value['name'] + ': ' + field_value['value'])
            if 'description' in ele:
                emsglst.append(ele['description'])
            if 'footer' in ele:
                emsglst.append(ele['footer']['text'])
            return emsglst

        msglst = []
        if msg:
            if isinstance(msg, dict):
                msgs = convertdict(msg)
                msglst.append('\n'.join(msgs))
            elif isinstance(msg, str):
                msglst.append(msg)
        if embed:
            msgs = convertdict(embed)
            msglst.append('\n'.join(msgs))
        await sendMessage(kwargs, '\n'.join(msglst))


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

    async def result(self, kwargs):
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
        err = ' '.join(kwargs['trigger_msg'].split(' ')[1:])
        err = self.fixup_input(err)
        if (meme := self.check_meme(err)) is not None:
            return await ctx.send(kwargs, meme)

        ret = self.fetch(err)

        if ret:
            embed = discord.Embed(title=ret.get_title())
            if ret.extra_description:
                embed.description = ret.extra_description
            for field in ret:
                embed.add_field(name=field.field_name, value=field.message, inline=False)

            embed.color = ret.color
            embed = embed.to_dict()
            await ctx.send(kwargs, embed=embed)
        else:
            await ctx.send(kwargs, f'你输入的代码是无效的，或者此功能不支持你使用的主机。')

    async def nxerr(self, kwargs):
        """
        Displays information on switch result codes, with a fancy embed.
        0x prefix is not required for hex input.

        Examples:
          .nxerr 0x4A8
          .nxerr 4A8
          .nxerr 2168-0002
          .nxerr 2-ARVHA-0000
        """
        err = ' '.join(kwargs['trigger_msg'].split(' ')[1:])
        err = self.fixup_input(err)
        if (meme := self.check_meme(err)) is not None:
            return await ctx.send(kwargs, meme)

        ret = None

        if switch.is_valid(err):
            ret = switch.get(err)

        if ret:
            embed = discord.Embed(title=ret.get_title())
            if ret.extra_description:
                embed.description = ret.extra_description
            for field in ret:
                embed.add_field(name=field.field_name, value=field.message, inline=False)

            embed.color = ret.color
            embed = embed.to_dict()
            await ctx.send(kwargs, embed=embed)
        else:
            await ctx.send(kwargs, f'The code you entered is \
invalid for the switch.')

    async def ctrerr(self, kwargs):
        """
        Displays information on 3DS result codes, with a fancy embed.
        0x prefix is not required for hex input.

        Examples:
          .ctrerr 0xD960D02B
          .ctrerr D960D02B
          .ctrerr 022-2634
        """
        err = ' '.join(kwargs['trigger_msg'].split(' ')[1:])
        if (meme := self.check_meme(err)) is not None:
            return await ctx.send(kwargs, meme)

        ret = None

        if ctr_support.is_valid(err):
            ret = ctr_support.get(err)
        elif ctr_results.is_valid(err):
            ret = ctr_results.get(err)

        if ret:
            embed = discord.Embed(title=ret.get_title())
            if ret.extra_description:
                embed.description = ret.extra_description
            for field in ret:
                embed.add_field(name=field.field_name, value=field.message, inline=False)

            embed.color = ret.color
            embed = embed.to_dict()
            await ctx.send(kwargs, embed=embed)
        else:
            await ctx.send(kwargs, f'The code you entered is \
invalid for the 3DS.')

    async def cafeerr(self, kwargs):
        """
        Displays information on Wii U result codes, with a fancy embed.
        0x prefix is not required for hex input.

        Examples:
          .cafeerr 0xC070FA80
          .cafeerr C070FA80
          .cafeerr 0x18106FFF
          .cafeerr 18106FFF
          .cafeerr 102-2804
        """
        err = ' '.join(kwargs['trigger_msg'].split(' ')[1:])
        err = self.fixup_input(err)
        if (meme := self.check_meme(err)) is not None:
            return await ctx.send(kwargs, meme)

        ret = None

        if wiiu_support.is_valid(err):
            ret = wiiu_support.get(err)
        elif wiiu_results.is_valid(err):
            ret = wiiu_results.get(err)

        if ret:
            embed = discord.Embed(title=ret.get_title())
            if ret.extra_description:
                embed.description = ret.extra_description
            for field in ret:
                embed.add_field(name=field.field_name, value=field.message, inline=False)

            embed.color = ret.color
            embed = embed.to_dict()
            await ctx.send(kwargs, embed=embed)
        else:
            await ctx.send(kwargs, f'The code you entered is \
invalid for the Wii U.')

    async def cmderr2hex(self, kwargs):
        """
        Converts a support code of a console to a hex result code.

        Switch only supported.
        3DS and WiiU support and result codes are not directly interchangeable.
        """
        err = ' '.join(kwargs['trigger_msg'].split(' ')[1:])
        error = self.fixup_input(err)
        await ctx.send(kwargs, self.err2hex(error))

    async def cmdhex2err(self, kwargs):
        """
        Converts a hex result code of a console to a support code.

        Switch only supported.
        3DS and WiiU support and result codes are not directly interchangeable.
        """
        err = ' '.join(kwargs['trigger_msg'].split(' ')[1:])
        error = self.fixup_input(err)
        await ctx.send(kwargs, self.hex2err(error))

    async def hexinfo(self, kwargs):
        """
        Breaks down a 3DS result code into its components.
        """
        err = ' '.join(kwargs['trigger_msg'].split(' ')[1:])
        error = self.fixup_input(err)
        if self.is_hex(error):
            if ctr_results.is_valid(error):
                mod, desc, summary, level = ctr_results.hexinfo(error)
                embed = discord.Embed(title="3DS hex result info")
                embed.add_field(name="Module", value=mod, inline=False)
                embed.add_field(name="Summary", value=summary, inline=False)
                embed.add_field(name="Level", value=level, inline=False)
                embed.add_field(name="Description", value=desc, inline=False)
                embed = embed.to_dict()

                await ctx.send(kwargs, embed=embed)
            else:
                await ctx.send(kwargs, 'This isn\'t a 3DS result code.')
        else:
            await ctx.send(kwargs, 'This isn\'t a hexadecimal value!')


command = {'err': Results().result}
help = {'err': {
    'help': '~err <报错码> - 查询任天堂主机系列报错码详细信息。'}}
