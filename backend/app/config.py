from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    data_dir: Path
    sqlite_path: Path
    duckdb_path: Path


def get_settings() -> Settings:
    # repo_root/backend/app/config.py -> repo_root
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = repo_root / "data"
    return Settings(
        repo_root=repo_root,
        data_dir=data_dir,
        sqlite_path=data_dir / "r4.sqlite",
        duckdb_path=data_dir / "onet.duckdb",
    )

