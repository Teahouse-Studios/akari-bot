import asyncio
import os
import subprocess
import sys

from core.builtins import Bot
from core.component import module
from core.exceptions import NoReportException
from core.logger import Logger

calc_dir = os.path.dirname(os.path.abspath(__file__))

c = module('calc', developers=['Dianliang233'], doc=True)


@c.command('<math_expression> {{calc.help}}')
async def _(msg: Bot.MessageSession, math_expression: str, use_markdown=False):
    if msg.target.sender_from in ['Discord|Client', 'KOOK|User']:
        use_markdown = True
    expr = math_expression.replace("\\", "")
    res = await spawn_subprocess('/calc.py', expr, msg)
    if res[:6] == 'Result':
        if use_markdown:
            expr = expr.replace('*', '\\*')
        m = f'{expr} = {res[7:]}'
        await msg.finish(m)
    else:
        await msg.finish(msg.locale.t("calc.message.invalid", expr=res[7:]))


async def spawn_subprocess(file: str, arg: str, msg: Bot.MessageSession) -> str:
    envs = os.environ.copy()
    if sys.platform == 'win32' and sys.version_info.minor < 10:
        try:
            return subprocess.check_output(
                [sys.executable, calc_dir + file, arg], timeout=10, shell=False,
                cwd=os.path.abspath('.'), env=envs) \
                .decode('utf-8')
        except subprocess.TimeoutExpired as e:
            raise NoReportException(msg.locale.t("calc.message.time_out")) from e
    else:
        try:
            p = await asyncio.create_subprocess_exec(sys.executable, calc_dir + file,
                                                     arg,
                                                     stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.PIPE,
                                                     cwd=os.path.abspath('.'), env=envs
                                                     )
            try:
                await asyncio.wait_for(p.wait(), timeout=10)
            except asyncio.TimeoutError as e:
                p.kill()
                raise NoReportException(msg.locale.t("calc.message.time_out")) from e
            stdout_data, stderr_data = await p.communicate()
            if p.returncode != 0:
                Logger.error(f'{file} exited with code {p.returncode}')
                try:
                    Logger.error(
                        f'{file} stderr: {stderr_data.decode("utf-8")}')
                except UnicodeDecodeError:
                    Logger.error(
                        f'{file} stderr: {stderr_data.decode("gbk")}')
            return stdout_data.decode('utf-8')
        except Exception as e:
            raise NoReportException(e) from e
