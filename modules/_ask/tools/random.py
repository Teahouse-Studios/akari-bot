import secrets
import uuid

from .utils import AkariTool, parse_input


async def random_number(input: str):
    parsed = parse_input(input)
    random = secrets.randbelow(int(parsed[0]) - int(parsed[1]) + 1) + int(parsed[1])
    return random


async def random_choice(input: str):
    parsed = parse_input(input)
    return secrets.choice(parsed)


async def random_uuid(input: str):
    return uuid.uuid4()


random_number_tool = AkariTool(
    name='Random Number',
    func=random_number,
    description='Generates a random number based on a max value and a min value. Requires 2 inputs, which are the max and min value.'
)

random_choice_tool = AkariTool(
    name='Random Choice',
    func=random_choice,
    description='Randomly chooses a input item. Supports arbitrary amounts of inputs.'
)

random_uuid_tool = AkariTool(
    name='Random UUID',
    func=random_uuid,
    description='Generates a random UUID. No input is required.'
)
