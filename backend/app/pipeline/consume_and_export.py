from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import duckdb
from rapidfuzz import fuzz, process
from sqlalchemy import select

from ..config import get_settings
from ..db import engine, session_scope
from ..etl.import_onet_duckdb import load_onet_text_zip
from ..etl.import_r4_csv import import_r4_ontology
from ..models import Base, Task, TaskCategory, TaskToCategory


@dataclass(frozen=True)
class Manifest:
    generated_at_utc: str
    inputs: dict
    outputs: dict


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _latest_file(dir_path: Path, pattern: str) -> Path | None:
    matches = list(dir_path.glob(pattern))
    if not matches:
        return None
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def _ensure_dirs(exports_dir: Path) -> None:
    exports_dir.mkdir(parents=True, exist_ok=True)


def _export_table_csv(path: Path, header: list[str], rows: Iterable[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def _export_tasks(exports_dir: Path) -> dict:
    with session_scope() as session:
        tasks = session.execute(select(Task).order_by(Task.id.asc())).scalars().all()

        _export_table_csv(
            exports_dir / "task.csv",
            ["id", "title", "task_text", "description", "phase", "metrics_text", "outcomes_text", "image_url"],
            [
                [
                    t.id,
                    t.title,
                    t.task_text or "",
                    t.description or "",
                    t.phase or "",
                    t.metrics_text or "",
                    t.outcomes_text or "",
                    t.image_url or "",
                ]
                for t in tasks
            ],
        )

        cats = session.execute(select(TaskCategory).order_by(TaskCategory.id.asc())).scalars().all()
        _export_table_csv(
            exports_dir / "task_category.csv",
            ["id", "kind", "name"],
            [[c.id, c.kind, c.name] for c in cats],
        )

        maps = session.execute(select(TaskToCategory).order_by(TaskToCategory.task_id.asc())).scalars().all()
        _export_table_csv(
            exports_dir / "task_to_category.csv",
            ["task_id", "category_id", "order"],
            [[m.task_id, m.category_id, m.order] for m in maps],
        )

        return {"task_count": len(tasks), "category_count": len(cats), "task_category_edges": len(maps)}


def _tokenize(s: str) -> list[str]:
    return [t for t in "".join(ch.lower() if ch.isalnum() else " " for ch in s).split() if len(t) >= 3]


def _build_profiles(exports_dir: Path, duckdb_path: Path) -> dict:
    """
    Brute-force initial profiles:
    - For each R4 task, propose top O*NET occupation titles (fuzzy match against task text/title)
    - Propose top O*NET skill names (fuzzy match against skill element names)

    This is intentionally naive but fast + offline, and good enough to seed manual refinement later.
    """
    con = duckdb.connect(str(duckdb_path), read_only=True)

    occ_rows = con.execute(
        "SELECT DISTINCT \"O*NET-SOC Code\" AS code, \"Title\" AS title FROM occupation_data"
    ).fetchall()
    occupations = [{"code": r[0], "title": r[1]} for r in occ_rows if r[0] and r[1]]
    occ_titles = [o["title"] for o in occupations]

    skill_rows = con.execute("SELECT DISTINCT \"Element Name\" AS name FROM skills").fetchall()
    skill_names = [r[0] for r in skill_rows if r[0]]

    profiles_path = exports_dir / "task_profile.jsonl"
    n_profiles = 0

    with session_scope() as session, profiles_path.open("w", encoding="utf-8") as out:
        tasks = session.execute(select(Task).order_by(Task.id.asc())).scalars().all()
        for t in tasks:
            query = " ".join(
                [x for x in [t.title, t.task_text or "", t.description or ""] if x]
            ).strip()
            if not query:
                continue

            # Occupations: best 8 fuzzy matches
            occ_matches = process.extract(
                query,
                occ_titles,
                scorer=fuzz.token_set_ratio,
                limit=8,
            )
            top_occ = []
            for title, score, idx in occ_matches:
                o = occupations[idx]
                top_occ.append({"code": o["code"], "title": o["title"], "score": float(score)})

            # Skills: best 12 fuzzy matches (use shorter query focusing on tokens)
            q2 = " ".join(_tokenize(query))[:500]
            skill_matches = process.extract(
                q2,
                skill_names,
                scorer=fuzz.token_set_ratio,
                limit=12,
            )
            top_skills = [{"name": name, "score": float(score)} for name, score, _ in skill_matches]

            rec = {
                "task_id": t.id,
                "task_title": t.title,
                "generated_at_utc": datetime.utcnow().isoformat() + "Z",
                "occupation_suggestions": top_occ,
                "skill_suggestions": top_skills,
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_profiles += 1

    con.close()
    return {"profiles_written": n_profiles}


def run() -> Path:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    imports_dir = settings.repo_root / "imports"
    downloads_dir = settings.repo_root / "downloads"

    r4_csv = _latest_file(imports_dir, "*.csv")
    onet_zip = _latest_file(downloads_dir, "db_*_text.zip")

    if r4_csv is None:
        raise SystemExit(f"No CSV found in {imports_dir}. Put Ontology_*.csv there.")
    if onet_zip is None:
        raise SystemExit(f"No O*NET text zip found in {downloads_dir}. Run Fetch-LaborData.ps1 first.")

    # Prepare SQLite schema
    Base.metadata.create_all(engine)

    # Import R4 ontology into SQLite
    r4_stats = import_r4_ontology(r4_csv)

    # Load O*NET into DuckDB (reference layer)
    onet_stats = load_onet_text_zip(onet_zip)

    # Export versioned bundle
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    exports_dir = settings.repo_root / "exports" / stamp
    _ensure_dirs(exports_dir)

    export_stats = _export_tasks(exports_dir)
    profile_stats = _build_profiles(exports_dir, settings.duckdb_path)

    manifest = Manifest(
        generated_at_utc=stamp,
        inputs={
            "r4_csv": {"path": str(r4_csv), "sha256": _sha256(r4_csv)},
            "onet_zip": {"path": str(onet_zip), "sha256": _sha256(onet_zip)},
            "sqlite_path": str(settings.sqlite_path),
            "duckdb_path": str(settings.duckdb_path),
        },
        outputs={
            "tables": export_stats,
            "profiles": profile_stats,
            "files": {
                "task.csv": _sha256(exports_dir / "task.csv"),
                "task_category.csv": _sha256(exports_dir / "task_category.csv"),
                "task_to_category.csv": _sha256(exports_dir / "task_to_category.csv"),
                "task_profile.jsonl": _sha256(exports_dir / "task_profile.jsonl"),
            },
            "import_stats": {"r4": r4_stats, "onet": onet_stats},
        },
    )

    (exports_dir / "manifest.json").write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    return exports_dir


if __name__ == "__main__":
    out_dir = run()
    print(f"Exported to: {out_dir}")

