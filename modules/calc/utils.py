import os
import sys


def invoke():
    if sys.version_info.minor > 8 or (sys.version_info.minor == 8 and sys.version_info.micro >=
                                      14):  # Added in 3.8.14, 3.7 and below not supported so
        sys.set_int_max_str_digits(0)
    if os.name == 'posix' and os.uname().sysname != 'Darwin':
        os.nice(15)
        import resource

        resource.setrlimit(resource.RLIMIT_AS,
                           (16 * 1024 * 1024, 16 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_DATA,
                           (16 * 1024 * 1024, 16 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_STACK,
                           (16 * 1024 * 1024, 16 * 1024 * 1024))
    elif os.name == 'nt':
        import win32process

        win32process.SetPriorityClass(win32process.GetCurrentProcess(
        ), 16384)
        win32process.SetProcessWorkingSetSize(
            win32process.GetCurrentProcess(), 1, 16 * 1024 * 1024)
