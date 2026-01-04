from copy import deepcopy

from attrs import define, field

from .component_meta import *


@define
class BaseMatches:
    set: list[ModuleMeta] = field(factory=list)

    def add(self, meta):
        self.set.append(meta)
        return self.set

    @classmethod
    def init(cls):
        return deepcopy(cls())


@define
class CommandMatches(BaseMatches):
    set: list[CommandMeta] = field(factory=list)

    def get(
        self,
        target_from: str | None = None,
        show_required_superuser: bool = False,
        show_required_base_superuser: bool = False,
    ) -> list[CommandMeta]:
        metas = []
        for meta in self.set:
            if not show_required_base_superuser and meta.required_base_superuser:
                continue
            if not show_required_superuser and meta.required_superuser:
                continue
            if not meta.load:
                continue
            if target_from:
                if "|" in target_from:
                    client_name = target_from.split("|")[0]
                else:
                    client_name = target_from

                if target_from in meta.exclude_from or client_name in meta.exclude_from:
                    continue
                if target_from in meta.available_for or client_name in meta.available_for or "*" in meta.available_for:
                    metas.append(meta)
            else:
                metas.append(meta)
        return metas


@define
class RegexMatches(BaseMatches):
    set: list[RegexMeta] = field(factory=list)

    def get(
        self,
        target_from: str | None = None,
        show_required_superuser: bool = False,
        show_required_base_superuser: bool = False,
    ) -> list[RegexMeta]:
        metas = []
        for meta in self.set:
            if not show_required_base_superuser and meta.required_base_superuser:
                continue
            if not show_required_superuser and meta.required_superuser:
                continue
            if not meta.load:
                continue
            if target_from:
                if "|" in target_from:
                    client_name = target_from.split("|")[0]
                else:
                    client_name = target_from

                if target_from in meta.exclude_from or client_name in meta.exclude_from:
                    continue
                if target_from in meta.available_for or client_name in meta.available_for or "*" in meta.available_for:
                    metas.append(meta)
            else:
                metas.append(meta)
        return metas


@define
class ScheduleMatches(BaseMatches):
    set: list[ScheduleMeta] = field(factory=list)


@define
class HookMatches(BaseMatches):
    set: list[HookMeta] = field(factory=list)


__all__ = ["CommandMatches", "RegexMatches", "ScheduleMatches", "HookMatches"]
