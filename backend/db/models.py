"""SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.engine import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class History(Base):
    """Execution history record."""

    __tablename__ = "history"

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
    skill_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
