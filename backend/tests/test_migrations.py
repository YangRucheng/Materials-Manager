from sqlalchemy import create_engine, inspect, text

from app.core.migrations import apply_schema_migrations


def test_purchase_material_status_migration_is_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE purchase_material ("
                "id INTEGER PRIMARY KEY, "
                "identity_hash VARCHAR(64) NOT NULL"
                ")"
            )
        )

        assert apply_schema_migrations(connection) == [
            "purchase_material.status",
            "ix_purchase_material_status",
        ]
        assert apply_schema_migrations(connection) == []

        inspector = inspect(connection)
        columns = {column["name"]: column for column in inspector.get_columns("purchase_material")}
        indexes = {index["name"] for index in inspector.get_indexes("purchase_material")}

    assert columns["status"]["nullable"] is False
    assert columns["status"]["default"] == "'NORMAL'"
    assert "ix_purchase_material_status" in indexes
