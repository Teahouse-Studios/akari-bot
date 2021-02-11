import re
from .profile import cytoid_profile

async def cytoid(kwargs: dict):
    command = kwargs['trigger_msg']
    command = re.sub('cytoid ', '', command)
    command_split = command.split(' ')
    if command_split[0] == 'profile':
        kwargs['trigger_msg'] = re.sub('profile ', '', command)
        await cytoid_profile(kwargs)


command = {'cytoid': cytoid}