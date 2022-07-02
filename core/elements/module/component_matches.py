from typing import List

from .component_meta import *


class CommandMatches:
    def __init__(self):
        self.set: List[CommandMeta] = []

    def add(self, meta):
        self.set.append(meta)
        return self.set

    def get(self, targetFrom: str) -> List[CommandMeta]:
        metas = []
        for meta in self.set:
            if targetFrom in meta.exclude_from:
                continue
            if targetFrom in meta.available_for or '*' in meta.available_for:
                metas.append(meta)
        return metas


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
