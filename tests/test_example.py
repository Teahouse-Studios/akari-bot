from core.tester import Tester, func_case, Contains, Match


@func_case
async def test_example(tester: Tester):
    """This is a test example"""
    await tester.expect("~echo hi", None, "should output hi")
    await tester.expect("~echo hello", Match("hello"), "should output hello")
    await tester.expect(["~echo", "lol"], Contains("lol"), "should output lol")
    return tester
