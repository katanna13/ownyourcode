from sqlalchemy import inspect


def test_initial_migration_upgrades_an_empty_postgresql_database(
    migrated_test_engine, test_database_url
) -> None:  # type: ignore[no-untyped-def]
    inspector = inspect(migrated_test_engine)
    assert {
        "users",
        "projects",
        "project_sources",
        "project_inspection_snapshots",
        "project_learning_content_versions",
        "project_learning_attempts",
        "project_learning_progress",
    }.issubset(
        inspector.get_table_names()
    )
    enum_names = {item["name"] for item in inspector.get_enums(schema="public")}
    assert {
        "project_mode",
        "project_status",
        "learning_operation_state",
        "learning_activity_kind",
    }.issubset(enum_names)
