from typing import List

from .component_meta import *

from attrs import define
from copy import deepcopy


@define
class BaseMatches:
    set: List[ModuleMeta] = []

    def add(self, meta):
        self.set.append(meta)
        return self.set

    @classmethod
    def init(cls):
        return deepcopy(cls())


@define
class CommandMatches(BaseMatches):
    set: List[CommandMeta] = []

    def get(
        self,
        target_from: str,
        show_required_superuser: bool = False,
        show_required_base_superuser: bool = False,
    ) -> List[CommandMeta]:
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
            if target_from in meta.available_for or "*" in meta.available_for:
                metas.append(meta)
        return metas


@define
class RegexMatches(BaseMatches):
    set: List[RegexMeta] = []

    def get(
        self,
        target_from: str,
        show_required_superuser: bool = False,
        show_required_base_superuser: bool = False,
    ) -> List[RegexMeta]:
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
            if target_from in meta.available_for or "*" in meta.available_for:
                metas.append(meta)
        return metas


@define
class ScheduleMatches(BaseMatches):
    set: List[ScheduleMeta] = []


@define
class HookMatches(BaseMatches):
    set: List[HookMeta] = []


__all__ = ["CommandMatches", "RegexMatches", "ScheduleMatches", "HookMatches"]
