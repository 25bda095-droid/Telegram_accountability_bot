# Accountability Bot — Full Project Specification

> **For the AI model reading this:** This document is your complete build spec. Read every section carefully before writing any code. Follow the build order exactly. Each file description tells you what to implement. Do not skip sections.

---

## Overview

**Accountability Bot** is a Telegram group bot that helps members stay accountable on daily tasks. Users submit task completions, earn points and streaks, compete on leaderboards, and unlock achievements. Admins can configure task windows, manage users, and view audit logs.

**Core user flow:**
1. User sends `/start` or joins a configured group
2. Each day, the bot opens a task submission window
3. Users submit their task completion (text/photo proof)
4. Bot awards points, updates streaks, checks achievements
5. Daily leaderboard snapshot is taken at end of window
6. Weekly/monthly summaries are posted automatically

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Telegram framework | aiogram 3.x (async) |
| ORM | SQLAlchemy 2.x (async, with `asyncpg` for PostgreSQL) |
| Scheduler | APScheduler 3.x (AsyncIOScheduler) |
| Database (dev) | SQLite (via `aiosqlite`) |
| Database (prod) | PostgreSQL (via `asyncpg`) |
| Migrations | Alembic |
| Cache | In-process TTL dict (custom, no Redis needed) |
| Containerization | Docker + docker-compose |
| Config | `pydantic-settings` (reads from `.env`) |

---

## Project File Structure

```
accountability-bot/
│
├── config.py                        # All settings via pydantic-settings
├── main.py                          # Entry point — wires everything together
│
├── models/
│   └── db_models.py                 # SQLAlchemy ORM models (all tables)
│
├── repositories/
│   ├── base_repo.py                 # Abstract base with session management
│   ├── user_repo.py                 # CRUD for User model
│   ├── task_repo.py                 # CRUD for TaskSubmission model
│   ├── snapshot_repo.py             # Leaderboard snapshot read/write
│   ├── streak_repo.py               # Streak read/write
│   ├── achievement_repo.py          # Achievement unlocks
│   ├── group_settings_repo.py       # Per-group configuration
│   └── audit_repo.py                # Audit log writes
│
├── cache/
│   └── ttl_cache.py                 # Simple in-process TTL key-value store
│
├── services/
│   ├── point_engine.py              # Pure math: points, multipliers, bonuses
│   ├── task_service.py              # Core task submission business logic
│   ├── streak_engine.py             # Streak calculation logic
│   ├── leaderboard_service.py       # Leaderboard aggregation + snapshot
│   ├── achievement_service.py       # Achievement check and award
│   ├── admin_service.py             # Admin actions (ban, reset, configure)
│   └── notification_service.py      # All outgoing Telegram messages
│
├── keyboards/
│   └── task_keyboard.py             # Inline keyboards for task interactions
│
├── middleware/
│   ├── auth.py                      # User upsert + inject user into handler data
│   ├── rate_limiter.py              # Per-user cooldown on task submissions
│   └── anti_cheat.py                # Detect duplicate/suspicious submissions
│
├── handlers/
│   ├── start_handler.py             # /start, /help commands
│   ├── task_handler.py              # Task submission and completion callbacks
│   ├── leaderboard_handler.py       # /leaderboard, /mystats commands
│   ├── achievement_handler.py       # /achievements command
│   ├── admin_handler.py             # /admin, /ban, /config commands
│   └── group_handler.py             # Bot added to group, member join/leave
│
├── scheduler/
│   ├── jobs.py                      # Individual scheduled job functions
│   └── scheduler.py                 # APScheduler setup and job registration
│
├── migrations/
│   ├── env.py                       # Alembic async migration env
│   └── versions/                    # Auto-generated migration scripts
│
├── alembic.ini                      # Alembic config
├── .env.example                     # Template for environment variables
├── Dockerfile                       # Production Docker image
├── docker-compose.yml               # Service orchestration
└── requirements.txt                 # All Python dependencies
```

---

## Environment Variables (`.env.example`)

```env
# Required
BOT_TOKEN=your_telegram_bot_token_here

# Database
DATABASE_URL=sqlite+aiosqlite:///./data/bot.db
# For production PostgreSQL:
# DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# Bot behavior
TASK_WINDOW_OPEN_HOUR=8        # Hour (UTC) when daily task window opens
TASK_WINDOW_CLOSE_HOUR=22      # Hour (UTC) when daily task window closes
MAX_SUBMISSIONS_PER_DAY=1      # How many times a user can submit per day
RATE_LIMIT_SECONDS=30          # Cooldown between any two submissions

# Points
BASE_POINTS=10                 # Points for a basic submission
STREAK_MULTIPLIER=0.1          # Extra 10% per streak day (e.g., day 5 = +50%)
MAX_STREAK_BONUS=2.0           # Cap multiplier at 2x

# Admin
ADMIN_IDS=123456789,987654321  # Comma-separated Telegram user IDs

# Logging
LOG_LEVEL=INFO                 # DEBUG in dev, INFO in prod
```

---

## File-by-File Implementation Spec

### `config.py`

Use `pydantic-settings` `BaseSettings`. Read all values from env/`.env` file.

```python
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./data/bot.db"
    task_window_open_hour: int = 8
    task_window_close_hour: int = 22
    max_submissions_per_day: int = 1
    rate_limit_seconds: int = 30
    base_points: int = 10
    streak_multiplier: float = 0.1
    max_streak_bonus: float = 2.0
    admin_ids: List[int] = []
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

---

### `models/db_models.py`

Define all SQLAlchemy ORM models using `DeclarativeBase`. Use `mapped_column` and `Mapped` (SQLAlchemy 2.x style). All primary keys are integers unless noted.

**Tables to define:**

**`User`**
- `id` (BigInteger PK) — Telegram user ID
- `username` (String, nullable)
- `full_name` (String)
- `is_banned` (Boolean, default False)
- `created_at` (DateTime, default utcnow)
- `total_points` (Integer, default 0)
- `current_streak` (Integer, default 0)
- `longest_streak` (Integer, default 0)
- relationship → `tasks`, `achievements`

**`GroupSettings`**
- `group_id` (BigInteger PK) — Telegram chat ID
- `task_window_open_hour` (Integer, nullable) — override global setting
- `task_window_close_hour` (Integer, nullable)
- `is_active` (Boolean, default True)
- `welcome_message` (Text, nullable)

**`TaskSubmission`**
- `id` (Integer PK, autoincrement)
- `user_id` (BigInteger FK → User.id)
- `group_id` (BigInteger)
- `submitted_at` (DateTime, default utcnow)
- `proof_text` (Text, nullable)
- `proof_file_id` (String, nullable) — Telegram file_id for photo
- `points_awarded` (Integer)
- `streak_day` (Integer) — streak at time of submission
- `is_flagged` (Boolean, default False) — anti-cheat flag

**`Streak`**
- `user_id` (BigInteger FK → User.id, PK)
- `group_id` (BigInteger, PK) — composite PK
- `current_streak` (Integer, default 0)
- `longest_streak` (Integer, default 0)
- `last_submission_date` (Date, nullable)

**`LeaderboardSnapshot`**
- `id` (Integer PK)
- `group_id` (BigInteger)
- `snapshot_date` (Date)
- `user_id` (BigInteger FK → User.id)
- `rank` (Integer)
- `points` (Integer)
- `streak` (Integer)

**`Achievement`**
- `id` (Integer PK)
- `user_id` (BigInteger FK → User.id)
- `group_id` (BigInteger)
- `achievement_key` (String) — e.g., "streak_7", "top3_weekly", "first_submission"
- `awarded_at` (DateTime, default utcnow)
- UniqueConstraint on (user_id, group_id, achievement_key)

**`AuditLog`**
- `id` (Integer PK)
- `actor_id` (BigInteger) — admin who performed action
- `action` (String) — e.g., "ban_user", "reset_streak", "change_window"
- `target_id` (BigInteger, nullable) — affected user
- `group_id` (BigInteger)
- `detail` (Text, nullable)
- `created_at` (DateTime, default utcnow)

Also define at the bottom of this file:
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

---

### `repositories/base_repo.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession

class BaseRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def commit(self):
        await self.session.commit()

    async def flush(self):
        await self.session.flush()
```

All other repos inherit from `BaseRepo` and accept `session: AsyncSession` in `__init__`.

---

### `repositories/user_repo.py`

Key methods:
- `async get_by_id(user_id: int) -> User | None`
- `async get_or_create(user_id: int, username: str, full_name: str) -> tuple[User, bool]` — returns (user, was_created)
- `async update_points(user_id: int, points: int)` — adds to total_points
- `async ban(user_id: int)`
- `async unban(user_id: int)`
- `async get_top_n(group_id: int, n: int = 10) -> list[User]` — by total_points for that group

---

### `repositories/task_repo.py`

Key methods:
- `async create_submission(user_id, group_id, proof_text, proof_file_id, points, streak_day) -> TaskSubmission`
- `async get_today_submission(user_id: int, group_id: int) -> TaskSubmission | None` — checks if already submitted today (UTC date)
- `async count_today_submissions(group_id: int) -> int`
- `async get_user_submissions(user_id: int, group_id: int, limit: int = 30) -> list[TaskSubmission]`
- `async flag_submission(submission_id: int)`

---

### `repositories/snapshot_repo.py`

Key methods:
- `async save_snapshot(group_id: int, date: date, rankings: list[dict])` — bulk insert LeaderboardSnapshot rows
- `async get_snapshot(group_id: int, date: date) -> list[LeaderboardSnapshot]`
- `async get_user_best_rank(user_id: int, group_id: int) -> int | None`

---

### `repositories/streak_repo.py`

Key methods:
- `async get_streak(user_id: int, group_id: int) -> Streak | None`
- `async upsert_streak(user_id: int, group_id: int, new_streak: int, last_date: date) -> Streak`
- `async reset_streak(user_id: int, group_id: int)`

---

### `repositories/achievement_repo.py`

Key methods:
- `async has_achievement(user_id: int, group_id: int, key: str) -> bool`
- `async award(user_id: int, group_id: int, key: str) -> Achievement | None` — returns None if already awarded (use INSERT OR IGNORE / on_conflict_do_nothing)
- `async get_user_achievements(user_id: int, group_id: int) -> list[Achievement]`

---

### `repositories/group_settings_repo.py`

Key methods:
- `async get(group_id: int) -> GroupSettings | None`
- `async upsert(group_id: int, **kwargs) -> GroupSettings`
- `async set_active(group_id: int, active: bool)`

---

### `repositories/audit_repo.py`

Key methods:
- `async log(actor_id: int, action: str, group_id: int, target_id: int | None = None, detail: str | None = None)`
- `async get_recent(group_id: int, limit: int = 50) -> list[AuditLog]`

---

### `cache/ttl_cache.py`

Simple in-memory dict with TTL. No Redis, no external dependencies.

```python
import time
from typing import Any

class TTLCache:
    def __init__(self, default_ttl: int = 300):
        self._store: dict[str, tuple[Any, float]] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        if key in self._store:
            value, expires_at = self._store[key]
            if time.monotonic() < expires_at:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int | None = None):
        ttl = ttl or self.default_ttl
        self._store[key] = (value, time.monotonic() + ttl)

    def delete(self, key: str):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

# Module-level singletons (import these in services)
leaderboard_cache = TTLCache(default_ttl=300)   # 5 min
rate_limit_cache  = TTLCache(default_ttl=3600)  # 1 hr
```

---

### `services/point_engine.py`

Pure math. No database calls. No aiogram imports. Must be unit-testable in isolation.

```python
from config import settings

def calculate_points(base: int, streak_day: int) -> int:
    """
    Apply streak multiplier to base points.
    streak_day=1 = first day (no bonus).
    multiplier = 1 + (streak_day - 1) * streak_multiplier
    capped at max_streak_bonus.
    """
    multiplier = 1.0 + (streak_day - 1) * settings.streak_multiplier
    multiplier = min(multiplier, settings.max_streak_bonus)
    return int(base * multiplier)

def rank_change_bonus(old_rank: int, new_rank: int) -> int:
    """Award bonus points for climbing the leaderboard. 2 pts per rank climbed."""
    climb = old_rank - new_rank  # positive = moved up
    return max(0, climb * 2)

def weekly_bonus(position: int) -> int:
    """Bonus points for weekly top 3."""
    bonuses = {1: 50, 2: 30, 3: 15}
    return bonuses.get(position, 0)
```

---

### `services/streak_engine.py`

```python
from datetime import date

def calculate_new_streak(last_submission_date: date | None, current_streak: int) -> int:
    """
    - No previous submission  → streak = 1
    - Last submission yesterday → streak = current_streak + 1
    - Last submission today     → streak unchanged (shouldn't happen, guarded upstream)
    - Gap > 1 day               → streak resets to 1
    """
    today = date.today()
    if last_submission_date is None:
        return 1
    delta = (today - last_submission_date).days
    if delta == 1:
        return current_streak + 1
    elif delta == 0:
        return current_streak
    else:
        return 1

def is_streak_milestone(streak: int) -> bool:
    milestones = {3, 7, 14, 30, 60, 100}
    return streak in milestones
```

---

### `services/task_service.py`

This is the core orchestration service. It coordinates all other services and repos.

Define a result dataclass:
```python
from dataclasses import dataclass, field

@dataclass
class SubmitResult:
    success: bool
    error_code: str | None = None   # "window_closed" | "already_submitted" | "banned" | "rate_limited" | "no_proof"
    points_awarded: int = 0
    new_streak: int = 0
    achievements_unlocked: list[str] = field(default_factory=list)
```

Main method:
```python
async def submit_task(
    session: AsyncSession,
    user_id: int,
    group_id: int,
    proof_text: str | None,
    proof_file_id: str | None,
) -> SubmitResult:
```

Logic steps (in order):
1. Load group settings → determine effective open/close hours
2. Check if current UTC hour is within window → if not, return `error_code="window_closed"`
3. Fetch user from user_repo → if `is_banned`, return `error_code="banned"`
4. Check today's submission via `task_repo.get_today_submission()` → if exists, return `error_code="already_submitted"`
5. Validate proof: at least one of proof_text or proof_file_id must be non-None → if both None, return `error_code="no_proof"`
6. Get current streak via `streak_repo.get_streak()` → call `streak_engine.calculate_new_streak()`
7. Calculate points via `point_engine.calculate_points(settings.base_points, new_streak)`
8. Write TaskSubmission via `task_repo.create_submission()`
9. Upsert streak via `streak_repo.upsert_streak()`
10. Add points via `user_repo.update_points()`
11. Check and award achievements via `achievement_service.check_and_award()`
12. Return `SubmitResult(success=True, points_awarded=points, new_streak=new_streak, achievements_unlocked=[...])`

---

### `services/leaderboard_service.py`

Key methods:
- `async get_leaderboard(session, group_id: int, limit: int = 10) -> list[dict]`
  - Check `leaderboard_cache.get(f"lb:{group_id}")`
  - On miss: query top N users by total_points for that group
  - Cache result with TTL=300
  - Return list of dicts: `[{rank, user_id, full_name, points, streak}, ...]`

- `async take_daily_snapshot(session, group_id: int)`
  - Get current leaderboard (bypass cache or use fresh query)
  - Save via `snapshot_repo.save_snapshot(group_id, date.today(), rankings)`
  - Invalidate cache: `leaderboard_cache.delete(f"lb:{group_id}")`

---

### `services/achievement_service.py`

Define all achievement keys and their check logic:

| Key | Condition |
|---|---|
| `first_submission` | First ever submission in a group |
| `streak_3` | Reach 3-day streak |
| `streak_7` | Reach 7-day streak |
| `streak_14` | Reach 14-day streak |
| `streak_30` | Reach 30-day streak |
| `top1_daily` | Rank #1 on a daily snapshot |
| `top3_weekly` | Top 3 on weekly summary |
| `century_points` | Accumulate 100 total points |

```python
async def check_and_award(
    session: AsyncSession,
    user_id: int,
    group_id: int,
    streak: int,
    total_points: int,
    is_first_submission: bool = False,
    snapshot_rank: int | None = None,
) -> list[str]:
    """Check all achievement conditions. Award newly earned ones. Return list of newly unlocked keys."""
    unlocked = []
    candidates = []

    if is_first_submission:
        candidates.append("first_submission")
    if streak >= 3:
        candidates.append("streak_3")
    if streak >= 7:
        candidates.append("streak_7")
    if streak >= 14:
        candidates.append("streak_14")
    if streak >= 30:
        candidates.append("streak_30")
    if total_points >= 100:
        candidates.append("century_points")
    if snapshot_rank == 1:
        candidates.append("top1_daily")

    for key in candidates:
        result = await achievement_repo.award(session, user_id, group_id, key)
        if result is not None:
            unlocked.append(key)

    return unlocked
```

---

### `services/admin_service.py`

Key methods — every method must verify actor is in `settings.admin_ids` first, then write to audit_repo:
- `async ban_user(session, actor_id, group_id, target_id) -> bool`
- `async unban_user(session, actor_id, group_id, target_id) -> bool`
- `async reset_user_streak(session, actor_id, group_id, target_id)`
- `async configure_group(session, actor_id, group_id, open_hour=None, close_hour=None, welcome_message=None)`
- `async get_audit_log(session, group_id, limit=20) -> list[AuditLog]`

---

### `services/notification_service.py`

Wraps the aiogram Bot instance. All message formatting lives here. Handlers call this service; they do NOT format messages directly.

Key methods:
- `async send_submission_success(bot, chat_id, user_id, points, streak, achievements: list[str])`
- `async send_leaderboard(bot, chat_id, entries: list[dict])`
- `async send_window_open(bot, chat_id)`
- `async send_window_close(bot, chat_id, snapshot: list[dict])`
- `async send_achievement_unlocked(bot, chat_id, user_id, achievement_key: str)`
- `async send_daily_summary(bot, chat_id, stats: dict)`
- `async send_error(bot, chat_id, error_code: str)` — look up USER_ERRORS dict, never expose raw exception text

All messages use HTML parse mode (`ParseMode.HTML`). Use `<b>` for names, `<i>` for points/stats.

---

### `keyboards/task_keyboard.py`

```python
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

class TaskCallback(CallbackData, prefix="task"):
    action: str   # "submit" | "confirm" | "cancel"
    group_id: int

def submit_task_keyboard(group_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Submit Task",
        callback_data=TaskCallback(action="submit", group_id=group_id)
    )
    return builder.as_markup()

def confirm_submission_keyboard(group_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Confirm", callback_data=TaskCallback(action="confirm", group_id=group_id))
    builder.button(text="❌ Cancel",  callback_data=TaskCallback(action="cancel",  group_id=group_id))
    builder.adjust(2)
    return builder.as_markup()

def admin_keyboard(group_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Members",   callback_data=f"admin:members:{group_id}")
    builder.button(text="📋 Audit Log", callback_data=f"admin:audit:{group_id}")
    builder.button(text="⚙️ Configure", callback_data=f"admin:config:{group_id}")
    builder.adjust(1)
    return builder.as_markup()
```

---

### `middleware/auth.py`

Register as both `dp.message.middleware` and `dp.callback_query.middleware`.

Logic for every incoming update:
1. Extract `user_id`, `username`, `full_name` from update
2. Call `user_repo.get_or_create()`
3. Inject `data["user"] = user` and `data["session"] = session`
4. If `user.is_banned` → reply "You are not allowed to participate." and return without calling handler
5. Open a single `AsyncSession` for the full request lifetime; commit after handler returns

```python
class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            tg_user = data["event_from_user"]
            user_repo = UserRepo(session)
            user, _ = await user_repo.get_or_create(
                user_id=tg_user.id,
                username=tg_user.username or "",
                full_name=tg_user.full_name,
            )
            data["user"] = user
            if user.is_banned:
                if hasattr(event, "message"):
                    await event.message.answer("You are not allowed to participate.")
                return
            result = await handler(event, data)
            await session.commit()
            return result
```

---

### `middleware/rate_limiter.py`

Register as `dp.message.middleware`.

Logic:
1. Key: `f"rl:{user_id}:{group_id}"`
2. Check `rate_limit_cache.get(key)`
3. If exists → reply "Please wait before submitting again." and return (do not call handler)
4. After passing through → set `rate_limit_cache.set(key, True, ttl=settings.rate_limit_seconds)`

Only apply to task submission messages, not to commands like `/start` or `/leaderboard`.

---

### `middleware/anti_cheat.py`

Register as `dp.message.middleware`. Runs after auth and rate_limiter.

Checks to implement:
- **Duplicate text**: if `proof_text` is identical to user's last submission in this group → flag
- **Suspiciously fast**: if submission arrives within 5 seconds of window open time → flag
- **No proof**: if neither `proof_text` nor a photo caption/file is provided → reject, return error

When flagged (for the first two cases):
- Still pass through to the handler
- Set a flag in `data["anti_cheat_flag"] = True` with `data["anti_cheat_reason"] = reason`
- The task_service will set `is_flagged=True` on the submission if this flag is present
- Do NOT reveal to the user that they were flagged — silent flag only
- Log at WARNING: `logging.warning(f"Anti-cheat flag: user={user_id} reason={reason}")`

---

### `handlers/start_handler.py`

```python
from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, user):
    if message.chat.type == "private":
        await message.answer(
            f"<b>Welcome, {user.full_name}!</b>\n\n"
            "I'm the Accountability Bot. Add me to a group to get started.\n\n"
            "Commands:\n"
            "/submit — Submit your daily task\n"
            "/leaderboard — View group standings\n"
            "/mystats — Your personal stats\n"
            "/achievements — Your badges"
        )
    else:
        await message.answer(
            f"<b>Accountability Bot is active!</b>\n"
            "Use /submit to complete your daily task. Good luck! 💪"
        )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Available Commands</b>\n\n"
        "/submit — Submit today's task completion\n"
        "/leaderboard — View the group leaderboard\n"
        "/mystats — Your points, streak, and rank\n"
        "/achievements — Your earned badges\n"
        "/help — Show this message"
    )
```

---

### `handlers/task_handler.py`

Handles the full task submission flow.

- `/submit` command → send "Ready to submit? Tap below!" with `submit_task_keyboard(group_id)`
- Callback `task:submit:{group_id}` → ask for proof (reply "Send your proof text or photo")
- When photo or text arrives after /submit → show confirm keyboard
- Callback `task:confirm:{group_id}` → call `task_service.submit_task()` → call `notification_service`
- Callback `task:cancel:{group_id}` → send "Submission cancelled."

**CRITICAL rules:**
- Every `callback_query` handler MUST call `await callback.answer()` — use try/finally
- Verify `callback.from_user.id` matches task ownership before confirming
- Use `data["session"]` injected by auth middleware — do NOT open a new session

```python
@router.callback_query(TaskCallback.filter(F.action == "confirm"))
async def on_confirm(callback: CallbackQuery, callback_data: TaskCallback, session, user):
    try:
        result = await task_service.submit_task(session, user.id, callback_data.group_id, ...)
        if result.success:
            await notification_service.send_submission_success(...)
            await callback.answer("✅ Submitted!")
        else:
            error_msg = USER_ERRORS.get(result.error_code, "Something went wrong.")
            await callback.answer(error_msg, show_alert=True)
    except Exception as e:
        logging.error(f"Error in confirm callback: {e}", exc_info=True)
        await callback.answer("Something went wrong.", show_alert=True)
```

---

### `handlers/leaderboard_handler.py`

```python
@router.message(Command("leaderboard", "lb"))
async def cmd_leaderboard(message: Message, session):
    group_id = message.chat.id
    entries = await leaderboard_service.get_leaderboard(session, group_id)
    await notification_service.send_leaderboard(message.bot, message.chat.id, entries)

@router.message(Command("mystats"))
async def cmd_mystats(message: Message, user, session):
    # Query: total_points, current_streak, longest_streak, achievement count
    # Format and send personal stats card
```

---

### `handlers/achievement_handler.py`

```python
ACHIEVEMENT_DISPLAY = {
    "first_submission": "🌱 First Step",
    "streak_3":         "🔥 3-Day Streak",
    "streak_7":         "⚡ 7-Day Streak",
    "streak_14":        "💎 2-Week Streak",
    "streak_30":        "🏆 30-Day Streak",
    "top1_daily":       "👑 Daily Champion",
    "top3_weekly":      "🥉 Weekly Top 3",
    "century_points":   "💯 Century Club",
}

@router.message(Command("achievements"))
async def cmd_achievements(message: Message, user, session):
    achievements = await achievement_repo.get_user_achievements(user.id, message.chat.id, session)
    if not achievements:
        await message.answer("You haven't earned any badges yet. Keep going! 💪")
        return
    lines = []
    for a in achievements:
        label = ACHIEVEMENT_DISPLAY.get(a.achievement_key, a.achievement_key)
        lines.append(f"{label} — <i>{a.awarded_at.strftime('%b %d')}</i>")
    await message.answer("<b>Your Achievements</b>\n\n" + "\n".join(lines))
```

---

### `handlers/admin_handler.py`

Guard every handler — check `user.id in settings.admin_ids` first.

- `/ban @username` or `/ban <user_id>` → call `admin_service.ban_user()` → confirm
- `/unban @username` → call `admin_service.unban_user()` → confirm
- `/resetstreak @username` → call `admin_service.reset_user_streak()` → confirm
- `/config open=8 close=22` → parse args → call `admin_service.configure_group()`
- `/admin` → show `admin_keyboard(group_id)`

If non-admin calls these → answer "This command is restricted to admins." and return.

---

### `handlers/group_handler.py`

Handle `ChatMemberUpdated` events:

```python
from aiogram.types import ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, MEMBER, LEFT

@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def bot_added_to_group(event: ChatMemberUpdated, session):
    # Bot was added to a group
    group_id = event.chat.id
    await group_settings_repo.upsert(session, group_id, is_active=True)
    await event.bot.send_message(group_id, "👋 Accountability Bot is ready! Use /submit daily.")

@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=LEFT))
async def bot_removed_from_group(event: ChatMemberUpdated, session):
    await group_settings_repo.set_active(session, event.chat.id, False)

@router.chat_member()
async def new_member_joined(event: ChatMemberUpdated, session):
    settings_record = await group_settings_repo.get(session, event.chat.id)
    if settings_record and settings_record.welcome_message:
        await event.bot.send_message(event.chat.id, settings_record.welcome_message)
```

---

### `scheduler/jobs.py`

```python
async def job_open_task_window(bot, session_factory):
    """Daily at task_window_open_hour UTC. Post window-open message to all active groups."""
    logging.info("Scheduler: opening task window")
    async with session_factory() as session:
        active_groups = await group_settings_repo.get_all_active(session)
    for group in active_groups:
        try:
            await notification_service.send_window_open(bot, group.group_id)
        except Exception as e:
            logging.warning(f"Could not notify group {group.group_id}: {e}")

async def job_close_task_window(bot, session_factory):
    """Daily at task_window_close_hour UTC. Take snapshot + post daily summary."""
    logging.info("Scheduler: closing task window")
    async with session_factory() as session:
        active_groups = await group_settings_repo.get_all_active(session)
        for group in active_groups:
            try:
                await leaderboard_service.take_daily_snapshot(session, group.group_id)
                snapshot = await snapshot_repo.get_snapshot(session, group.group_id, date.today())
                await notification_service.send_window_close(bot, group.group_id, snapshot)
                await session.commit()
            except Exception as e:
                logging.error(f"Error closing window for group {group.group_id}: {e}", exc_info=True)

async def job_check_broken_streaks(bot, session_factory):
    """Daily at 00:05 UTC. Reset streaks for users who missed yesterday."""
    logging.info("Scheduler: checking broken streaks")
    yesterday = date.today() - timedelta(days=1)
    async with session_factory() as session:
        # Find all Streak rows where last_submission_date < yesterday
        # Reset those streaks to 0
        # Commit
        pass  # implement query

async def job_weekly_summary(bot, session_factory):
    """Every Monday 00:05 UTC. Compute top 3, award top3_weekly, post recap."""
    logging.info("Scheduler: weekly summary")
    async with session_factory() as session:
        active_groups = await group_settings_repo.get_all_active(session)
        for group in active_groups:
            try:
                entries = await leaderboard_service.get_leaderboard(session, group.group_id, limit=3)
                for i, entry in enumerate(entries[:3], start=1):
                    await achievement_service.check_and_award(
                        session, entry["user_id"], group.group_id,
                        streak=entry["streak"], total_points=entry["points"],
                        snapshot_rank=i,
                    )
                    points_bonus = point_engine.weekly_bonus(i)
                    await user_repo.update_points(session, entry["user_id"], points_bonus)
                await notification_service.send_daily_summary(bot, group.group_id, {"top3": entries})
                await session.commit()
            except Exception as e:
                logging.error(f"Weekly summary error for group {group.group_id}: {e}", exc_info=True)
```

---

### `scheduler/scheduler.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import settings
from scheduler.jobs import job_open_task_window, job_close_task_window, job_check_broken_streaks, job_weekly_summary

def create_scheduler(bot, session_factory) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        job_open_task_window,
        CronTrigger(hour=settings.task_window_open_hour, minute=0),
        kwargs={"bot": bot, "session_factory": session_factory},
        id="open_window", replace_existing=True,
    )
    scheduler.add_job(
        job_close_task_window,
        CronTrigger(hour=settings.task_window_close_hour, minute=0),
        kwargs={"bot": bot, "session_factory": session_factory},
        id="close_window", replace_existing=True,
    )
    scheduler.add_job(
        job_check_broken_streaks,
        CronTrigger(hour=0, minute=5),
        kwargs={"bot": bot, "session_factory": session_factory},
        id="check_streaks", replace_existing=True,
    )
    scheduler.add_job(
        job_weekly_summary,
        CronTrigger(day_of_week="mon", hour=0, minute=5),
        kwargs={"bot": bot, "session_factory": session_factory},
        id="weekly_summary", replace_existing=True,
    )

    return scheduler
```

---

### `main.py`

Wire everything together. This is the last file you write.

```python
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import settings
from models.db_models import init_db, AsyncSessionLocal
from middleware.auth import AuthMiddleware
from middleware.rate_limiter import RateLimiterMiddleware
from middleware.anti_cheat import AntiCheatMiddleware
from handlers import start_handler, task_handler, leaderboard_handler, achievement_handler, admin_handler, group_handler
from scheduler.scheduler import create_scheduler

async def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    await init_db()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    # Middleware — order matters: auth first, then rate limiter, then anti-cheat
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.message.middleware(RateLimiterMiddleware())
    dp.message.middleware(AntiCheatMiddleware())

    # Routers
    dp.include_router(start_handler.router)
    dp.include_router(task_handler.router)
    dp.include_router(leaderboard_handler.router)
    dp.include_router(achievement_handler.router)
    dp.include_router(admin_handler.router)
    dp.include_router(group_handler.router)

    # Global error handler — catches any unhandled exception from any handler
    @dp.errors()
    async def global_error_handler(event, exception):
        logging.error(f"Unhandled exception: {exception}", exc_info=True)
        try:
            if hasattr(event, "message") and event.message:
                await event.message.answer("Something went wrong. Please try again.")
            elif hasattr(event, "callback_query") and event.callback_query:
                await event.callback_query.answer("Something went wrong.", show_alert=True)
        except Exception:
            pass
        # Do NOT re-raise — prevents the update from being retried infinitely

    scheduler = create_scheduler(bot, AsyncSessionLocal)
    scheduler.start()
    logging.info("Bot started. Polling...")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Error Handling — Mandatory Patterns

### 1. Callback Queries Must Always Be Answered

```python
@router.callback_query(TaskCallback.filter())
async def handle_callback(callback: CallbackQuery, ...):
    try:
        # handler body
        await callback.answer("✅ Done!")
    except Exception as e:
        logging.error(f"Callback error: {e}", exc_info=True)
        await callback.answer("Something went wrong.", show_alert=True)
    # If you use finally, ensure callback.answer() is always called.
    # Failure to call it leaves a spinning loader on the user's button forever.
```

### 2. User-Facing Error Messages

```python
USER_ERRORS = {
    "duplicate_task":  "You've already submitted your task today.",
    "window_closed":   "Task submission is closed for today.",
    "banned":          "You are not allowed to participate.",
    "rate_limited":    "Please wait before submitting again.",
    "no_proof":        "Please provide text or a photo as proof.",
    "not_your_task":   "That's not your task!",
}
```

Never expose internal exception text to users. Always go through this dict.

### 3. Ownership Check

```python
if callback.from_user.id != task.user_id:
    await callback.answer(USER_ERRORS["not_your_task"], show_alert=True)
    return
```

### 4. Logging Levels

| Level | Use for |
|---|---|
| `ERROR` | Unexpected exception that aborted a user action or scheduler job. Always include `exc_info=True`. |
| `WARNING` | Expected handled failure: user blocked bot, rate-limited, duplicate task, message not found. |
| `INFO` | High-level events: bot started, scheduler job started/finished, user banned, achievement awarded. |
| `DEBUG` | Granular: each task submission parsed, each DB query, cache hit/miss, each callback. Off in prod. |

---

## Deployment

### `requirements.txt`

```
aiogram==3.7.0
SQLAlchemy==2.0.30
aiosqlite==0.20.0
asyncpg==0.29.0
APScheduler==3.10.4
alembic==1.13.1
pydantic-settings==2.2.1
python-dotenv==1.0.1
```

### `Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/data /app/logs
CMD ["python", "main.py"]
```

### `docker-compose.yml`

```yaml
version: '3.9'
services:
  bot:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data      # SQLite persistence
      - ./logs:/app/logs      # Log persistence
    healthcheck:
      test: ["CMD", "python", "-c", "import bot"]
      interval: 30s
      retries: 3
```

### Option A — Railway (5 minutes)

```
1. Push repo to GitHub
2. railway.app → New Project → Deploy from GitHub repo
3. Set env vars in Railway dashboard (copy from .env.example)
4. Railway auto-detects Dockerfile → Deploy → done ✓
Free tier: 500 hrs/month
```

### Option B — Oracle Always Free

```bash
sudo apt update && sudo apt install -y docker.io docker-compose git
git clone <your-repo> bot && cd bot
cp .env.example .env && nano .env  # set BOT_TOKEN
docker-compose up -d
# Free forever on ARM VM
```

### Migrating SQLite → PostgreSQL

When you hit >500 active users or >50 concurrent submissions/sec, change one line in `.env`:
```
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
```
SQLAlchemy abstracts all differences. No other code changes needed.

---

## Recommended Build Order

Follow this order exactly so each file has its dependencies ready.

| # | File | Why this order |
|---|---|---|
| 1 | `config.py` | Everything else imports this |
| 2 | `models/db_models.py` | Repos and services need ORM types |
| 3 | `repositories/base_repo.py` | All repos inherit from this |
| 4 | `repositories/user_repo.py` | Used by auth middleware — needed early |
| 5 | `repositories/task_repo.py` + `snapshot_repo.py` | Core data access |
| 6 | `repositories/streak_repo.py` + `achievement_repo.py` + `group_settings_repo.py` + `audit_repo.py` | Remaining repos |
| 7 | `cache/ttl_cache.py` | Used by leaderboard_service and rate_limiter |
| 8 | `services/point_engine.py` | Pure math, no deps. Test this first. |
| 9 | `services/task_service.py` | Core service, needs point_engine + repos |
| 10 | `services/streak_engine.py` + `leaderboard_service.py` | Need snapshot_repo + cache |
| 11 | `services/achievement_service.py` + `admin_service.py` + `notification_service.py` | Need other services ready |
| 12 | `keyboards/task_keyboard.py` | Needs ORM types only |
| 13 | `middleware/auth.py` → `rate_limiter.py` → `anti_cheat.py` | Need repos and cache |
| 14 | `handlers/*.py` (all 6) | Need all services and keyboards |
| 15 | `scheduler/jobs.py` + `scheduler.py` | Need services and bot instance |
| 16 | `main.py` | Wires everything together. Build last. |
| 17 | `migrations/env.py` + `alembic.ini` | Set up after models are finalized |
| 18 | `Dockerfile` + `docker-compose.yml` | Containerize once everything runs locally |

---

## Prompt Template for Qwen2.5 7B

Use this exact structure when generating each file with your local model:

```
You are a senior Python developer building the Accountability Bot — a Telegram group
accountability bot using aiogram 3.x, SQLAlchemy 2.x async, APScheduler, and SQLite.

Files already implemented: [list completed files]

Now implement: [target filename]

Spec for this file:
[paste the relevant section from this README]

Constraints:
- Use async/await throughout — no blocking calls
- Use SQLAlchemy 2.x style: Mapped[], mapped_column(), select(), etc.
- Follow the exact class and method signatures in the spec
- Do not add features not in the spec
- Add docstrings to all public methods
- Use full type hints everywhere
- Use the session injected by middleware (data["session"]) — never open a new session inside a handler

Output ONLY the complete file content. No explanation. No markdown fences.
```

---

*End of specification. Build in order. Test point_engine first — it has no dependencies.*
