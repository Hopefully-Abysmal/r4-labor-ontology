from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import select

from ..config import get_settings
from ..db import session_scope
from ..models import Task, TaskCategory, TaskToCategory


@dataclass(frozen=True)
class R4Row:
    task_title: str
    primary_category: Optional[str]
    operational_domain: Optional[str]
    sub_category: Optional[str]
    work_category: Optional[str]
    task_text: Optional[str]
    image: Optional[str]
    task_description: Optional[str]
    phase: Optional[str]
    metrics: Optional[str]
    outcomes: Optional[str]


def _read_rows(path: Path) -> Iterable[R4Row]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            yield R4Row(
                task_title=(r.get("Task Title") or "").strip(),
                primary_category=(r.get("Primary Category") or "").strip() or None,
                operational_domain=(r.get("Operational Domain") or "").strip() or None,
                sub_category=(r.get("Sub-Category") or "").strip() or None,
                work_category=(r.get("Work Category") or "").strip() or None,
                task_text=(r.get("Task") or "").strip() or None,
                image=(r.get("Image") or "").strip() or None,
                task_description=(r.get("Task Description") or "").strip() or None,
                phase=(r.get("Phase") or "").strip() or None,
                metrics=(r.get("Metrics") or "").strip() or None,
                outcomes=(r.get("Outcomes") or "").strip() or None,
            )


def _get_or_create_category(session, kind: str, name: str) -> TaskCategory:
    existing = session.execute(
        select(TaskCategory).where(TaskCategory.kind == kind, TaskCategory.name == name)
    ).scalar_one_or_none()
    if existing:
        return existing
    c = TaskCategory(kind=kind, name=name)
    session.add(c)
    session.flush()
    return c


def import_r4_ontology(csv_path: Path) -> dict[str, int]:
    inserted_tasks = 0
    updated_tasks = 0
    inserted_categories = 0
    mapped_edges = 0

    with session_scope() as session:
        before_cats = session.execute(select(TaskCategory.id)).all()
        before_cat_count = len(before_cats)

        for row in _read_rows(csv_path):
            if not row.task_title:
                continue

            # Upsert by title (good enough for MVP; later use stable IDs)
            task = session.execute(select(Task).where(Task.title == row.task_title)).scalar_one_or_none()
            if task is None:
                task = Task(title=row.task_title)
                session.add(task)
                session.flush()
                inserted_tasks += 1
            else:
                updated_tasks += 1

            task.task_text = row.task_text
            task.description = row.task_description
            task.phase = row.phase
            task.metrics_text = row.metrics
            task.outcomes_text = row.outcomes
            task.image_url = row.image

            # Wipe and re-map categories for deterministic import
            task.categories.clear()

            cat_pairs = [
                ("Primary Category", row.primary_category),
                ("Operational Domain", row.operational_domain),
                ("Sub-Category", row.sub_category),
                ("Work Category", row.work_category),
            ]
            order = 0
            for kind, name in cat_pairs:
                if not name:
                    continue
                cat = _get_or_create_category(session, kind=kind, name=name)
                task.categories.append(TaskToCategory(task_id=task.id, category_id=cat.id, order=order))
                mapped_edges += 1
                order += 1

        after_cat_count = session.execute(select(TaskCategory.id)).all()
        inserted_categories = len(after_cat_count) - before_cat_count

    return {
        "inserted_tasks": inserted_tasks,
        "updated_tasks": updated_tasks,
        "inserted_categories": inserted_categories,
        "mapped_task_category_edges": mapped_edges,
    }


def default_csv_path() -> Path:
    settings = get_settings()
    return settings.repo_root / "imports" / "Ontology_20241208-1.csv"


if __name__ == "__main__":
    stats = import_r4_ontology(default_csv_path())
    print(stats)

