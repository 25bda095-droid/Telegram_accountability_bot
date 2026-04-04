import os
from datetime import datetime, date
from sqlalchemy import (
    BigInteger, Integer, String, Boolean, DateTime, Date, Text, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    full_name: Mapped[str] = mapped_column(String)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)

    tasks: Mapped[list["TaskSubmission"]] = relationship(
        "TaskSubmission",
        back_populates="user"
    )
    achievements: Mapped[list["Achievement"]] = relationship(
        "Achievement",
        back_populates="user"
    )
    daily_tasks: Mapped[list["UserDailyTask"]] = relationship(
        "UserDailyTask",
        back_populates="user"
    )


class GroupSettings(Base):
    __tablename__ = "group_settings"

    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task_window_open_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task_window_close_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class TaskSubmission(Base):
    """Legacy table kept for history — new flow uses UserDailyTask."""
    __tablename__ = "task_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    group_id: Mapped[int] = mapped_column(BigInteger)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    proof_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_file_id: Mapped[str | None] = mapped_column(String, nullable=True)
    points_awarded: Mapped[int] = mapped_column(Integer)
    streak_day: Mapped[int] = mapped_column(Integer)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(
        "User",
        back_populates="tasks"
    )


# ─────────────────────────────────────
# NEW: Per-day named tasks (1–6 slots)
# ─────────────────────────────────────

class UserDailyTask(Base):
    """Stores each named task a user sets for a day (up to 6 slots)."""
    __tablename__ = "user_daily_tasks"
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", "date", "slot", name="uix_daily_task_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    group_id: Mapped[int] = mapped_column(BigInteger)
    date: Mapped[date] = mapped_column(Date)
    slot: Mapped[int] = mapped_column(Integer)          # 1–6
    task_name: Mapped[str] = mapped_column(Text)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="daily_tasks")




# ─────────────────────────────────────
# NEW: Task lock (once per day — set when user taps 'Done Setting Tasks')
# ─────────────────────────────────────

class UserTaskLock(Base):
    """Marks that a user has finalised their task list for the day.
    Once this row exists, no new task slots can be added for that date."""
    __tablename__ = "user_task_locks"
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", "date", name="uix_task_lock_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    group_id: Mapped[int] = mapped_column(BigInteger)
    date: Mapped[date] = mapped_column(Date)
    locked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# ─────────────────────────────────────
# NEW: Skip token (once per week)
# ─────────────────────────────────────

class SkipRecord(Base):
    """Tracks usage of the weekly skip token per user per group."""
    __tablename__ = "skip_records"
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", "week_start", name="uix_skip_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    group_id: Mapped[int] = mapped_column(BigInteger)
    week_start: Mapped[date] = mapped_column(Date)   # Monday of the week
    skip_date: Mapped[date] = mapped_column(Date)    # Actual day that was skipped


class Streak(Base):
    __tablename__ = "streaks"
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uix_user_group_streak"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)
    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class LeaderboardSnapshot(Base):
    __tablename__ = "leaderboard_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(BigInteger)
    snapshot_date: Mapped[date] = mapped_column(Date)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    rank: Mapped[int] = mapped_column(Integer)
    points: Mapped[int] = mapped_column(Integer)
    streak: Mapped[int] = mapped_column(Integer)


class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "group_id",
            "achievement_key",
            name="uix_user_group_achievement"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    group_id: Mapped[int] = mapped_column(BigInteger)
    achievement_key: Mapped[str] = mapped_column(String)
    awarded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(
        "User",
        back_populates="achievements"
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    group_id: Mapped[int] = mapped_column(BigInteger)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# =========================
# DATABASE ENGINE
# =========================

DATABASE_URL = settings.database_url

if DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+asyncpg://",
        1
    )

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
