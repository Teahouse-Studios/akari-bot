from typing import List

from .component_meta import *


class CommandMatches:
    def __init__(self):
        self.set: List[CommandMeta] = []

    def add(self, meta):
        self.set.append(meta)
        return self.set

    def get(self, target_from: str, show_required_superuser: bool = False,
            show_required_base_superuser: bool = False) -> List[CommandMeta]:
        metas = []
        for meta in self.set:
            if not show_required_base_superuser and meta.required_base_superuser:
                continue
            if not show_required_superuser and meta.required_superuser:
                continue
            if not meta.load:
                continue
            if target_from in meta.exclude_from:
                continue
            if target_from in meta.available_for or '*' in meta.available_for:
                metas.append(meta)
        return metas


class RegexMatches:
    def __init__(self):
        self.set: List[RegexMeta] = []

    def add(self, meta):
        self.set.append(meta)
        return self.set

    def get(self, target_from: str, show_required_superuser: bool = False,
            show_required_base_superuser: bool = False) -> List[RegexMeta]:
        metas = []
        for meta in self.set:
            if not show_required_base_superuser and meta.required_base_superuser:
                continue
            if not show_required_superuser and meta.required_superuser:
                continue
            if not meta.load:
                continue
            if target_from in meta.exclude_from:
                continue
            if target_from in meta.available_for or '*' in meta.available_for:
                metas.append(meta)
        return metas


class ScheduleMatches:
    def __init__(self):
        self.set: List[ScheduleMeta] = []

    def add(self, meta):
        self.set.append(meta)
        return self.set


class HookMatches:
    def __init__(self):
        self.set: List[HookMeta] = []

    def add(self, meta):
        self.set.append(meta)
        return self.set


__all__ = ["CommandMatches", "RegexMatches", "ScheduleMatches", "HookMatches"]
