from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import duckdb

from ..config import get_settings


def _extract_zip(zip_path: Path, target_dir: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(target_dir)


def load_onet_text_zip(zip_path: Path) -> dict[str, int]:
    """
    Loads selected O*NET text tables into a local DuckDB database for fast offline joins.
    This is intentionally conservative (a few core tables) to keep MVP simple.
    """
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.duckdb_path))

    # Keep the DB reproducible: drop and recreate tables we control.
    tables = ["occupation_data", "skills", "knowledge", "abilities", "task_statements", "task_ratings"]
    for t in tables:
        con.execute(f"DROP TABLE IF EXISTS {t}")

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        _extract_zip(zip_path, td_path)

        # Text bundle layout: a single folder named db_30_2_text/
        root = next((p for p in td_path.iterdir() if p.is_dir()), td_path)

        mapping = {
            "Occupation Data.txt": "occupation_data",
            "Skills.txt": "skills",
            "Knowledge.txt": "knowledge",
            "Abilities.txt": "abilities",
            "Task Statements.txt": "task_statements",
            "Task Ratings.txt": "task_ratings",
        }

        loaded: dict[str, int] = {}
        for filename, table in mapping.items():
            f = root / filename
            if not f.exists():
                continue

            con.execute(
                f"""
                CREATE TABLE {table} AS
                SELECT * FROM read_csv_auto(
                  '{f.as_posix()}',
                  delim='\\t',
                  header=true,
                  ignore_errors=true
                )
                """
            )
            loaded[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    con.close()
    return loaded


def default_zip_path() -> Path:
    settings = get_settings()
    return settings.repo_root / "downloads" / "db_30_2_text.zip"


if __name__ == "__main__":
    print(load_onet_text_zip(default_zip_path()))

