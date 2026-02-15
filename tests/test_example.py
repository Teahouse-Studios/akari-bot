from core.tester import Tester, func_case


@func_case
async def _(tester: Tester):
    """This is a test example"""
    await tester.input("~echo hi", None, "should output hi")
    await tester.input("~echo hello", "hello", "should output hello")
    await tester.input(["~echo", "lol"], True, "should output lol")
    return tester
