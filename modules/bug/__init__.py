import re

from .bugtracker import bug


async def main(name):
    q = re.match(r'(.*)\-(.*)', name)
    if q:
        return (await bug(q.group(1) + '-' + q.group(2)))


command = {'bug': 'bug'}
