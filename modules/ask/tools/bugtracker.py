from modules.bugtracker.bugtracker import bugtracker_get
from .utils import fake_msg, AkariTool


async def mojira(bug_id: str):
    return (await bugtracker_get(fake_msg, bug_id))[0]


bugtracker_tool = AkariTool.from_function(
    func=mojira,
    description='A tool for querying a bug on Mojira, Minecraft/Mojang\'s bug tracker. Input should be a Jira issue id, e.g. XX-1234.'
)
