"""SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.engine import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class History(Base):
    """Execution history record."""

    __tablename__ = "history"
    __table_args__ = (
        Index("ix_history_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    task: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    python_code: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    tips: Mapped[str | None] = mapped_column(Text, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    exec_stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    exec_stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_log: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    reflection_steps: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    debug_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skill_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("skills.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )


class Skill(Base):
    """Reusable skill record — stores generated code and metadata."""

    __tablename__ = "skills"
    __table_args__ = (
        Index("ix_skills_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    python_code: Mapped[str] = mapped_column(Text, nullable=False)
    file_schema: Mapped[str | None] = mapped_column(Text, nullable=True)  # column names + types JSON
    task_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source_history_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("history.id", ondelete="SET NULL"), nullable=True,
    )
