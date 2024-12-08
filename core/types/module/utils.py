from typing import Union


def convert2lst(elements: Union[str, list, tuple]) -> list:
    if isinstance(elements, str):
        return [elements]
    elif isinstance(elements, tuple):
        return list(elements)
    return elements
