from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import func, select

from .allocation import run_allocation
from .config import get_settings
from .db import engine, session_scope
from .etl.import_onet_duckdb import default_zip_path as default_onet_zip_path
from .etl.import_onet_duckdb import load_onet_text_zip
from .etl.import_r4_csv import default_csv_path, import_r4_ontology
from .models import AllocationDecision, AllocationRun, Base, NeedClaim, NeedStatus, Task
from .schema import NeedClaimOut


settings = get_settings()
templates = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(["html", "xml"]),
)

app = FastAPI(title="R4 Needs + Ontology MVP", version="0.1.0")

# In-memory event fanout for SSE (single-process MVP)
_event_queue: asyncio.Queue[str] = asyncio.Queue()


def _emit(event: str = "tick") -> None:
    try:
        _event_queue.put_nowait(event)
    except Exception:
        pass


@app.on_event("startup")
def _startup() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    with session_scope() as session:
        task_count = session.execute(select(func.count()).select_from(Task)).scalar_one()
        needs = (
            session.execute(select(NeedClaim).order_by(NeedClaim.created_at.desc()).limit(50))
            .scalars()
            .all()
        )
        last_run = session.execute(select(AllocationRun).order_by(AllocationRun.created_at.desc()).limit(1)).scalar_one_or_none()
        decisions = []
        if last_run:
            decisions = (
                session.execute(
                    select(AllocationDecision)
                    .where(AllocationDecision.run_id == last_run.id)
                    .order_by(AllocationDecision.score.desc())
                    .limit(25)
                )
                .scalars()
                .all()
            )

    tpl = templates.get_template("index.html")
    return HTMLResponse(
        tpl.render(
            task_count=task_count,
            needs=needs,
            last_run_id=last_run.id if last_run else None,
            decisions=decisions,
        )
    )


@app.get("/events")
async def events() -> EventSourceResponse:
    async def gen() -> AsyncIterator[dict]:
        while True:
            msg = await _event_queue.get()
            yield {"event": "message", "data": msg}

    return EventSourceResponse(gen())


@app.get("/needs", response_model=list[NeedClaimOut])
def list_needs() -> list[NeedClaimOut]:
    with session_scope() as session:
        needs = session.execute(select(NeedClaim).order_by(NeedClaim.created_at.desc()).limit(200)).scalars().all()
        return [
            NeedClaimOut(
                id=n.id,
                created_at=n.created_at,
                title=n.title,
                category=n.category,
                urgency=n.urgency,
                quantity=n.quantity,
                unit=n.unit,
                constraints=n.constraints or {},
                status=n.status.value if hasattr(n.status, "value") else str(n.status),
            )
            for n in needs
        ]


@app.post("/needs/new")
def create_need(
    title: str = Form(...),
    category: str | None = Form(None),
    urgency: int = Form(50),
    quantity: float = Form(1),
    unit: str | None = Form(None),
) -> RedirectResponse:
    with session_scope() as session:
        n = NeedClaim(
            title=title,
            category=category,
            urgency=max(0, min(100, int(urgency))),
            quantity=float(quantity),
            unit=unit,
            constraints={},
            status=NeedStatus.open,
        )
        session.add(n)
    _emit("need")
    return RedirectResponse("/", status_code=303)


@app.post("/allocation/run")
def allocation_run() -> RedirectResponse:
    run_id = run_allocation(rule_version="v0")
    _emit(f"allocation:{run_id}")
    return RedirectResponse("/", status_code=303)


@app.post("/imports/r4-ontology")
def import_r4() -> RedirectResponse:
    stats = import_r4_ontology(default_csv_path())
    _emit(f"import:r4:{stats.get('inserted_tasks', 0)}")
    return RedirectResponse("/", status_code=303)


@app.post("/imports/onet")
def import_onet() -> RedirectResponse:
    loaded = load_onet_text_zip(default_onet_zip_path())
    _emit(f"import:onet:{loaded.get('occupation_data', 0)}")
    return RedirectResponse("/", status_code=303)


@app.get("/health")
def health() -> dict:
    return {"ok": True}

