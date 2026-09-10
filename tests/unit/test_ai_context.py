from modules.ai import context


def test_context_isolated_by_scene_and_each_snapshot_can_branch(monkeypatch):
    monkeypatch.setattr(context, "_context_windows", context.ExpiringTempDict(exp=context.CONTEXT_EXPIRY))

    parent_id = context.create_context([{"role": "user", "content": "start"}], "scene-a")
    child_id = context.create_context(
        [{"role": "user", "content": "start"}, {"role": "assistant", "content": "reply"}], "scene-a"
    )

    assert context.get_context(parent_id, "scene-a") == [{"role": "user", "content": "start"}]
    assert context.get_context(child_id, "scene-a")[1]["content"] == "reply"
    assert context.get_context(parent_id, "scene-b") is None
