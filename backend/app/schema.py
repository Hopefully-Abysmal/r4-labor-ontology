from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskCategoryOut(BaseModel):
    id: int
    kind: str
    name: str


class TaskOut(BaseModel):
    id: int
    title: str
    task_text: Optional[str] = None
    description: Optional[str] = None
    phase: Optional[str] = None
    metrics_text: Optional[str] = None
    outcomes_text: Optional[str] = None
    image_url: Optional[str] = None


class NeedClaimIn(BaseModel):
    title: str
    category: Optional[str] = None
    urgency: int = Field(default=50, ge=0, le=100)
    quantity: float = Field(default=1, gt=0)
    unit: Optional[str] = None
    constraints: dict[str, Any] = Field(default_factory=dict)


class NeedClaimOut(NeedClaimIn):
    id: int
    created_at: datetime
    status: str


class AllocationDecisionOut(BaseModel):
    id: int
    need_id: int
    fulfilled: bool
    score: float
    reason: str
    plan: dict[str, Any]


class AllocationRunOut(BaseModel):
    id: int
    created_at: datetime
    rule_version: str
    notes: Optional[str] = None
    decisions: list[AllocationDecisionOut]

