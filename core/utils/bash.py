import asyncio
import locale


async def run_sys_command(command: list[str], timeout: float = 10) -> tuple[int, str, str]:
    """执行系统命令并返回执行结果。此函数仅在安全环境中调用，确保知道你正在干什么。

    :param command: 需要执行的命令（List），禁止直接使用用户输入。
    :param timeout: 命令的最大执行时间（默认为 10）。
    :returns: 包含返回码、标准输出和标准错误的 Tuple (returncode, stdout, stderr)。
    """
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        encoding = locale.getpreferredencoding(False)
        return (
            process.returncode,
            stdout.decode(encoding, errors="ignore").strip(),
            stderr.decode(encoding, errors="ignore").strip(),
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return -1, "", "Process timeout"
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
