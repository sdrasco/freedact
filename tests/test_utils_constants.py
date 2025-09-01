from redactor.utils.constants import RIGHT_TRIM, rtrim_index


def test_right_trim_membership_and_trim() -> None:
    for ch in ",.)”’":
        assert ch in RIGHT_TRIM
    assert rtrim_index("x).", 3) == 1
