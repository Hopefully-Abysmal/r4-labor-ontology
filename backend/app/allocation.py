from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from .db import session_scope
from .models import AllocationDecision, AllocationRun, NeedClaim, NeedStatus


@dataclass(frozen=True)
class AllocationWeights:
    urgency_weight: float = 1.0
    age_weight: float = 0.15


def _score_need(n: NeedClaim, now: datetime, w: AllocationWeights) -> tuple[float, str]:
    age_hours = max(0.0, (now - n.created_at).total_seconds() / 3600.0)
    score = w.urgency_weight * float(n.urgency) + w.age_weight * age_hours
    reason = f"urgency={n.urgency}, age_hours={age_hours:.2f}"
    return score, reason


def run_allocation(rule_version: str = "v0", notes: str | None = None) -> int:
    """
    MVP allocator: prioritize open needs by urgency + age.
    Fulfillment is a placeholder boolean for now; we mark top-N as 'fulfilled' only if desired later.
    """
    now = datetime.utcnow()
    w = AllocationWeights()

    with session_scope() as session:
        run = AllocationRun(rule_version=rule_version, notes=notes)
        session.add(run)
        session.flush()

        needs = (
            session.execute(select(NeedClaim).where(NeedClaim.status == NeedStatus.open))
            .scalars()
            .all()
        )

        # Compute scores and store decisions for explainability.
        scored = []
        for n in needs:
            score, reason = _score_need(n, now, w)
            scored.append((score, reason, n))
        scored.sort(key=lambda x: x[0], reverse=True)

        for score, reason, n in scored:
            d = AllocationDecision(
                run_id=run.id,
                need_id=n.id,
                fulfilled=False,
                score=score,
                reason=reason,
                plan={},
            )
            session.add(d)

        return run.id

