from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG_PATH = BACKEND_DIRECTORY / "alembic.ini"


def test_alembic_upgrade_and_downgrade_use_an_isolated_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "migration-test.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    alembic_config = Config(str(ALEMBIC_CONFIG_PATH))
    head_revision = ScriptDirectory.from_config(alembic_config).get_current_head()

    command.upgrade(alembic_config, "head")

    engine = create_engine(database_url)
    try:
        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "locations",
            "manufacturers",
            "materials",
            "spools",
            "weight_history",
            "print_jobs",
        }
        spool_foreign_keys = {
            (foreign_key["constrained_columns"][0], foreign_key["referred_table"])
            for foreign_key in inspect(engine).get_foreign_keys("spools")
        }
        assert spool_foreign_keys == {
            ("location_id", "locations"),
            ("manufacturer_id", "manufacturers"),
            ("material_id", "materials"),
        }
        assert {
            index["name"] for index in inspect(engine).get_indexes("spools")
        } >= {
            "ix_spools_code",
            "ix_spools_location_id",
            "ix_spools_manufacturer_id",
            "ix_spools_material_id",
            "ix_spools_status",
        }
        history_foreign_keys = inspect(engine).get_foreign_keys("weight_history")
        assert len(history_foreign_keys) == 1
        assert history_foreign_keys[0]["constrained_columns"] == ["spool_id"]
        assert history_foreign_keys[0]["referred_table"] == "spools"
        assert history_foreign_keys[0]["referred_columns"] == ["id"]
        assert history_foreign_keys[0]["options"] == {"ondelete": "CASCADE"}
        assert {
            index["name"]
            for index in inspect(engine).get_indexes("weight_history")
        } == {"ix_weight_history_spool_id_created_at"}
        assert {
            constraint["name"]
            for constraint in inspect(engine).get_check_constraints(
                "weight_history"
            )
        } == {
            "ck_weight_history_source",
            "ck_weight_history_weight_non_negative",
        }
        print_job_foreign_keys = inspect(engine).get_foreign_keys("print_jobs")
        assert len(print_job_foreign_keys) == 1
        assert print_job_foreign_keys[0]["constrained_columns"] == ["spool_id"]
        assert print_job_foreign_keys[0]["referred_table"] == "spools"
        assert print_job_foreign_keys[0]["options"] == {"ondelete": "RESTRICT"}
        assert {
            index["name"] for index in inspect(engine).get_indexes("print_jobs")
        } == {
            "ix_print_jobs_spool_id",
            "ix_print_jobs_status",
            "uq_print_jobs_one_printing_per_spool",
        }
        assert {
            column["name"] for column in inspect(engine).get_columns("print_jobs")
        } >= {
            "filament_cost_per_g",
            "material_cost",
            "material_cost_currency",
        }
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == head_revision

        command.downgrade(alembic_config, "-1")

        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "locations",
            "manufacturers",
            "materials",
            "spools",
            "weight_history",
            "print_jobs",
        }
        assert {
            index["name"] for index in inspect(engine).get_indexes("print_jobs")
        } == {
            "ix_print_jobs_spool_id",
            "ix_print_jobs_status",
            "uq_print_jobs_one_printing_per_spool",
        }
        assert {
            column["name"] for column in inspect(engine).get_columns("print_jobs")
        }.isdisjoint({
            "filament_cost_per_g",
            "material_cost",
            "material_cost_currency",
        })

        command.downgrade(alembic_config, "-1")

        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "locations",
            "manufacturers",
            "materials",
            "spools",
            "weight_history",
            "print_jobs",
        }
        assert {
            index["name"] for index in inspect(engine).get_indexes("print_jobs")
        } == {"ix_print_jobs_spool_id", "ix_print_jobs_status"}

        command.downgrade(alembic_config, "-1")

        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "locations",
            "manufacturers",
            "materials",
            "spools",
            "weight_history",
        }

        command.downgrade(alembic_config, "base")

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none() is None

        command.upgrade(alembic_config, "head")

        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "locations",
            "manufacturers",
            "materials",
            "spools",
            "weight_history",
            "print_jobs",
        }
    finally:
        engine.dispose()
