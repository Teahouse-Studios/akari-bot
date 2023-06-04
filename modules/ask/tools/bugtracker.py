from modules.bugtracker.bugtracker import bugtracker_get
from .utils import fake_msg, AkariTool


async def bugtracker(input: str):
    return (await bugtracker_get(fake_msg, input))[0]

bugtracker_tool = AkariTool(
    name='Mojira',
    func=bugtracker,
    description='A tool for querying a bug on Mojira, Minecraft/Mojang\'s bug tracker. Input should be a Jira issue id, e.g. XX-1234.'
)
