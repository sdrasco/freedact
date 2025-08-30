from redactor.config.schema import deep_merge_dicts


def test_deep_merge_nested_and_list_replace() -> None:
    base = {
        "outer": {"a": 1, "b": {"c": 2}},
        "list": [1, 2],
    }
    override = {
        "outer": {"b": {"c": 3}},
        "list": [3],
    }
    merged = deep_merge_dicts(base, override)
    assert merged == {"outer": {"a": 1, "b": {"c": 3}}, "list": [3]}
    # ensure original not mutated
    assert base["list"] == [1, 2]
