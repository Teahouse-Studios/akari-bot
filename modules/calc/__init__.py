import asyncio
import os
import subprocess
import sys

from core.builtins import Bot
from core.component import module
from core.exceptions import NoReportException
from core.logger import Logger

c = module('calc', developers=[
    'Dianliang233'], desc='{calc.help.desc}')


@c.command('<math_expression>', options_desc={'+': '{calc.help.plus}',
                                              '-': '{calc.help.minus}',
                                              '/': '{calc.help.multiply}',
                                              '*': '{calc.help.divide}',
                                              '**': '{calc.help.power}',
                                              '%': '{calc.help.modulo}',
                                              '==': '{calc.help.equal}',
                                              '<=': '{calc.help.less_equal}',
                                              '>=': '{calc.help.greater_equal}',
                                              '>>': '{calc.help.move_right}',
                                              '<<': '{calc.help.move_left}',
                                              '^': '{calc.help.xor}',
                                              'not': '{calc.help.not}',
                                              'is': '{calc.help.is}',
                                              'randint(x)': '{calc.help.randint}',
                                              'rand()': '{calc.help.rand}',
                                              'int()': '{calc.help.int}',
                                              'float()': '{calc.help.float}',
                                              'str()': '{calc.help.str}',
                                              'complex()': '{calc.help.complex}',
                                              'bool()': '{calc.help.bool}',
                                              'bin()': '{calc.help.bin}',
                                              'oct()': '{calc.help.oct}',
                                              'hex()': '{calc.help.hex}',
                                              '{calc.help.more}': 'https://bot.teahouse.team/-/340',
                                              })
async def _(msg: Bot.MessageSession):
    expr = msg.asDisplay().split(' ', 1)[1]
    if sys.platform == 'win32' and sys.version_info.minor < 10:
        try:
            res = subprocess.check_output(
                ['python', os.path.abspath("./modules/calc/calc.py"), expr], timeout=10, shell=False).decode('utf-8')
            if res[0:6] == 'Result':
                await msg.finish(f'{(expr)} = {res[7:]}')
            else:
                await msg.finish(msg.locale.t("calc.message.invalid", exp={res[7:]}))
        except subprocess.TimeoutExpired:
            raise NoReportException(msg.locale.t("calc.message.time_out"))
    else:
        try:
            p = await asyncio.create_subprocess_exec('python', os.path.abspath("./modules/calc/calc.py"), expr,
                                                     stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.PIPE
                                                     )
            try:
                await asyncio.wait_for(p.wait(), timeout=10)
            except asyncio.TimeoutError:
                p.kill()
                raise NoReportException(msg.locale.t("calc.message.time_out"))
            stdout_data, stderr_data = await p.communicate()
            if p.returncode == 0:
                res = stdout_data.decode('utf-8')

                if res[0:6] == 'Result':
                    await msg.finish(f'{(expr)} = {res[7:]}')
                else:
                    await msg.finish(msg.locale.t("calc.message.invalid", expr=res[7:]))
            else:
                Logger.error(f'calc.py exited with code {p.returncode}')
                try:
                    Logger.error(
                        f'calc.py stderr: {stderr_data.decode("utf-8")}')
                except UnicodeDecodeError:
                    Logger.error(
                        f'calc.py stderr: {stderr_data.decode("gbk")}')
        except Exception as e:
            raise NoReportException(e)
