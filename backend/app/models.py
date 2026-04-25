from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Phase(str, enum.Enum):
    immediate_response = "Immediate Response"
    recovery = "Recovery"
    long_term_reconstruction = "Long-Term Reconstruction"
    preparedness = "Preparedness"
    mixed = "Mixed"


class TaskCategory(Base):
    __tablename__ = "task_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(64))  # Primary Category, Operational Domain, etc.
    name: Mapped[str] = mapped_column(String(256))

    __table_args__ = (UniqueConstraint("kind", "name", name="uq_task_category_kind_name"),)


class Task(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    task_text: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    phase: Mapped[Optional[str]] = mapped_column(String(64))
    metrics_text: Mapped[Optional[str]] = mapped_column(Text)
    outcomes_text: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)

    categories: Mapped[list["TaskToCategory"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class TaskToCategory(Base):
    __tablename__ = "task_to_category"

    task_id: Mapped[int] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"), primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("task_category.id", ondelete="CASCADE"), primary_key=True)
    order: Mapped[int] = mapped_column(Integer, default=0)

    task: Mapped[Task] = relationship(back_populates="categories")
    category: Mapped[TaskCategory] = relationship()


class NeedStatus(str, enum.Enum):
    open = "open"
    fulfilled = "fulfilled"
    cancelled = "cancelled"


class NeedClaim(Base):
    __tablename__ = "need_claim"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, index=True)
    title: Mapped[str] = mapped_column(String(512))
    category: Mapped[Optional[str]] = mapped_column(String(256))
    urgency: Mapped[int] = mapped_column(Integer, default=50)  # 0-100
    quantity: Mapped[float] = mapped_column(Float, default=1)
    unit: Mapped[Optional[str]] = mapped_column(String(64))
    constraints: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[NeedStatus] = mapped_column(Enum(NeedStatus), default=NeedStatus.open, index=True)


class InventoryItem(Base):
    __tablename__ = "inventory_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), unique=True)
    category: Mapped[Optional[str]] = mapped_column(String(256))
    unit: Mapped[Optional[str]] = mapped_column(String(64))
    is_essential: Mapped[bool] = mapped_column(Boolean, default=False)


class Site(Base):
    __tablename__ = "site"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), unique=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class InventoryStock(Base):
    __tablename__ = "inventory_stock"

    site_id: Mapped[int] = mapped_column(ForeignKey("site.id", ondelete="CASCADE"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_item.id", ondelete="CASCADE"), primary_key=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, primary_key=True)
    quantity: Mapped[float] = mapped_column(Float)

    site: Mapped[Site] = relationship()
    item: Mapped[InventoryItem] = relationship()


class AllocationRun(Base):
    __tablename__ = "allocation_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, index=True)
    rule_version: Mapped[str] = mapped_column(String(64), default="v0")
    notes: Mapped[Optional[str]] = mapped_column(Text)

    decisions: Mapped[list["AllocationDecision"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class AllocationDecision(Base):
    __tablename__ = "allocation_decision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("allocation_run.id", ondelete="CASCADE"), index=True)
    need_id: Mapped[int] = mapped_column(ForeignKey("need_claim.id", ondelete="CASCADE"), index=True)
    fulfilled: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")
    plan: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    run: Mapped[AllocationRun] = relationship(back_populates="decisions")
    need: Mapped[NeedClaim] = relationship()

