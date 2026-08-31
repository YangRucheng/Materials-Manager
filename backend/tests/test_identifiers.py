from uuid import UUID

from app.core.identifiers import uuid7_string


def test_uuid7_strings_are_valid_and_monotonically_ordered() -> None:
    identifiers = [uuid7_string() for _ in range(100)]

    assert identifiers == sorted(identifiers)
    assert len(set(identifiers)) == len(identifiers)
    assert all(UUID(identifier).version == 7 for identifier in identifiers)
