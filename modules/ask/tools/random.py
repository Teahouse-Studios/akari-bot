import uuid
from typing import List

from core.utils.random import Random
from .utils import AkariTool, parse_input


async def random_number(mininum: int, maxinum: int):
    random = Random.randint(mininum, maxinum)
    return random


async def random_choice(input_: List[str]):
    parsed = parse_input(input_)
    return Random.choice(parsed)


async def random_uuid():
    return uuid.uuid4()


random_number_tool = AkariTool.from_function(
    func=random_number,
    description="Generates a random number based on a max value and a min value.",
)

random_choice_tool = AkariTool.from_function(
    func=random_choice, description="Randomly chooses a input item."
)

random_uuid_tool = AkariTool.from_function(
    func=random_uuid, description="Generates a random UUID."
)
