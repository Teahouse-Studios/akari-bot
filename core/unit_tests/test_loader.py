import importlib
from unittest.mock import MagicMock, patch

import pytest

from core.loader import ModulesManager, Module


@pytest.fixture
def sample_module():
    mod = MagicMock(spec=Module)
    mod.module_name = "test_module"
    mod.alias = {"alias1": "test_module"}
    mod.hooks_list = MagicMock()
    mod.hooks_list.set = set()
    mod.available_for = {"*"}
    mod.exclude_from = set()
    mod.load = True
    return mod


def test_add_module(sample_module):
    ModulesManager.modules.clear()
    ModulesManager.modules_origin.clear()
    ModulesManager.add_module(sample_module, "modules.test_module")
    assert "test_module" in ModulesManager.modules
    assert ModulesManager.modules_origin["test_module"] == "modules.test_module"

    with pytest.raises(ValueError):
        ModulesManager.add_module(sample_module, "modules.test_module")


def test_remove_modules(sample_module):
    ModulesManager.modules.clear()
    ModulesManager.modules_origin.clear()
    ModulesManager.add_module(sample_module, "modules.test_module")

    ModulesManager.remove_modules(["test_module"])
    assert "test_module" not in ModulesManager.modules

    with pytest.raises(ValueError):
        ModulesManager.remove_modules(["non_exist_module"])


def test_return_modules_list(sample_module):
    ModulesManager.modules.clear()
    ModulesManager.modules_origin.clear()
    ModulesManager._return_cache.clear()

    ModulesManager.add_module(sample_module, "modules.test_module")

    mods = ModulesManager.return_modules_list()
    assert "test_module" in mods

    result = ModulesManager.return_modules_list(target_from="client1")
    assert "test_module" in result


def test_search_related_module(sample_module):
    ModulesManager.modules.clear()
    ModulesManager.modules_origin.clear()
    ModulesManager.add_module(sample_module, "modules.sub.test_module")

    related = ModulesManager.search_related_module("test_module")
    assert "test_module" in related

    related = ModulesManager.search_related_module("test_module", include_self=False)
    assert "test_module" not in related

    with pytest.raises(ValueError):
        ModulesManager.search_related_module("non_exist_module")


def test_return_py_module(sample_module):
    ModulesManager.modules.clear()
    ModulesManager.modules_origin.clear()
    ModulesManager.add_module(sample_module, "modules.sub.test_module")

    py_module = ModulesManager.return_py_module("test_module")
    assert py_module == "modules.sub"

    assert ModulesManager.return_py_module("non_exist_module") is None


@patch("core.loader.importlib.reload")
@patch("core.loader.sys.modules", new_callable=dict)
def test_reload_py_module(mock_modules, mock_reload, sample_module):
    ModulesManager.modules.clear()
    ModulesManager.modules_origin.clear()
    ModulesManager.add_module(sample_module, "modules.test_module")

    mock_module = MagicMock()
    mock_modules["modules.test_module"] = mock_module

    count = ModulesManager.reload_py_module("modules.test_module")
    assert count == 1
    mock_reload.assert_called_with(mock_module)


def test_reload_py_module_exception(monkeypatch):
    monkeypatch.setattr(importlib, "reload", lambda x: (_ for _ in ()).throw(Exception("fail")))
    count = ModulesManager.reload_py_module("non_exist_module")
    assert count == -999
