class AnchorElement:
    __slots__ = ["attrs", "count", "outcount"]

    def __init__(self, attrs: dict[str, str | None], count: int, outcount: int):
        self.attrs = attrs
        self.count = count
        self.outcount = outcount


class ListElement:
    __slots__ = ["name", "num"]

    def __init__(self, name: str, num: int):
        self.name = name
        self.num = num
