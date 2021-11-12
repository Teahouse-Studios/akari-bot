from typing import List

from .meta import *


class CommandMatches:
    def __init__(self):
        self.set: List[CommandMeta] = []

    def add(self, meta):
        self.set.append(meta)
        return self.set


class RegexMatches:
    def __init__(self):
        self.set: List[RegexMeta] = []

    def add(self, meta):
        self.set.append(meta)
        return self.set


class ScheduleMatches:
    def __init__(self):
        self.set: List[ScheduleMeta] = []

    def add(self, meta):
        self.set.append(meta)
        return self.set


__all__ = ["CommandMatches", "RegexMatches", "ScheduleMatches"]
