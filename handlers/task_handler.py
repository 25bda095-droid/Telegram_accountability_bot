import logging
from datetime import datetime, timezone, timedelta, date as date_type

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from repositories.task_repo import DailyTaskRepo, SkipRepo
from repositories.streak_repo import StreakRepo
from repositories.user_repo import UserRepo
from services import leaderboard_service
from services.streak_engine import calculate_new_streak, get_milestone_bonus
from keyboards.task_keyboard import group_main_menu, private_main_menu

router = Router()
log = logging.getLogger(__name__)

MAX_SLOTS = 6


# ─────────────────────────────────────
# FSM States
# ─────────────────────────────────────

class TaskInput(StatesGroup):
    waiting_for_task_text = State()    # data keys: slot, group_id


# ─────────────────────────────────────
# Helpers
# ─────────────────────────────────────

_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th"}


def ordinal(n: int) -> str:
    return _ORDINALS.get(n, f"{n}th")


def get_week_start(d: date_type) -> date_type:
    """Return the Monday of the week containing *d*."""
    return d - timedelta(days=d.weekday())


def _slot_label(slot: int, task=None) -> str:
    """Build the label for a task-slot button."""
    label_prefix = ordinal(slot)
    if task is None:
        return f"➕ {label_prefix} Task"
    name_preview = task.task_name[:22]
    if task.is_done:
        return f"✅ {label_prefix}: {name_preview}"
    return f"📝 {label_prefix}: {name_preview}"


def task_slots_keyboard(tasks: list, skip_available: bool = True) -> InlineKeyboardMarkup:
    """
    Shows all 6 task-slot buttons.
    Already-filled slots show the task name; empty slots show ➕.
    """
    task_map = {t.slot: t for t in tasks}
    buttons = []
    for i in range(1, MAX_SLOTS + 1):
        buttons.append([
            InlineKeyboardButton(
                text=_slot_label(i, task_map.get(i)),
                callback_data=f"tslot_{i}",
            )
        ])

    # Bottom row: Skip + Done
    bottom = []
    if skip_available:
        bottom.append(
            InlineKeyboardButton(text="⏭️ Skip Today (1×/week)", callback_data="grp_skip")
        )
    bottom.append(
        InlineKeyboardButton(text="✔️ Done Setting Tasks", callback_data="grp_main_menu")
    )
    buttons.append(bottom)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def update_task_keyboard(tasks: list) -> InlineKeyboardMarkup:
    """
    Shows each task as a button.
    Done tasks: tapping just shows 'Already completed'.
    Pending tasks: tapping marks them done.
    """
    buttons = []
    for task in sorted(tasks, key=lambda t: t.slot):
        if task.is_done:
            label = f"✅ {ordinal(task.slot)}: {task.task_name[:25]}"
            cb    = f"tdone_already_{task.slot}"
        else:
            label = f"⬜ {ordinal(task.slot)}: {task.task_name[:25]} — tap to complete"
            cb    = f"tdone_{task.slot}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=cb)])

    buttons.append([InlineKeyboardButton(text="🔙 Back to Menu", callback_data="grp_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─────────────────────────────────────
# PRIVATE CHAT CALLBACKS
# ─────────────────────────────────────

@router.callback_query(F.data == "priv_total_score")
async def priv_total_score(callback: CallbackQuery, user):
    await callback.message.answer(
        f"🏅 <b>Your Total Score</b>\n\n"
        f"Total points: <b>{user.total_points}</b>",
        parse_mode="HTML",
        reply_markup=private_main_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "priv_streak")
async def priv_streak(callback: CallbackQuery, user):
    text = (
        f"🔥 <b>Your Streak</b>\n\n"
        f"Current streak : <b>{user.current_streak}</b> days\n"
        f"Longest streak : <b>{user.longest_streak}</b> days\n\n"
        f"Add me to a group for per-group streak tracking!"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=private_main_menu())
    await callback.answer()


@router.callback_query(F.data == "priv_rank")
async def priv_rank(callback: CallbackQuery, user):
    await callback.message.answer(
        f"🏅 <b>Your Rank</b>\n\n"
        f"Total points: <b>{user.total_points}</b>\n\n"
        f"Add me to a group to see your group rank! 🏆",
        parse_mode="HTML",
        reply_markup=private_main_menu(),
    )
    await callback.answer()


# ─────────────────────────────────────
# GROUP: BACK TO MAIN MENU
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_main_menu")
async def grp_main_menu_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("👇 Main Menu:", reply_markup=group_main_menu())
    await callback.answer()


# ─────────────────────────────────────
# GROUP: SUBMIT YOUR TASK
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_submit")
async def grp_submit(callback: CallbackQuery, user, session):
    group_id = callback.message.chat.id
    today = datetime.now(timezone.utc).date()

    daily_task_repo = DailyTaskRepo(session)
    tasks = await daily_task_repo.get_today_tasks(user.id, group_id)

    # All 6 slots already filled — no more adding
    if len(tasks) >= MAX_SLOTS:
        await callback.answer(
            "You've filled all 6 task slots today! "
            "Use 'Update Task' to mark them done.",
            show_alert=True,
        )
        return

    skip_repo = SkipRepo(session)
    week_start = get_week_start(today)
    skip_used = (await skip_repo.get_skip_record(user.id, group_id, week_start)) is not None

    n_tasks = len(tasks)
    await callback.message.answer(
        f"📋 <b>Set Your Tasks for Today</b>\n"
        f"Slots filled: <b>{n_tasks}/{MAX_SLOTS}</b>\n\n"
        f"Tap any slot to add or view a task:",
        reply_markup=task_slots_keyboard(tasks, skip_available=not skip_used),
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────────────────────
# GROUP: TAP A TASK SLOT → tslot_N
# ─────────────────────────────────────

@router.callback_query(F.data.startswith("tslot_"))
async def grp_slot_tap(callback: CallbackQuery, user, session, state: FSMContext):
    try:
        slot = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid slot.", show_alert=True)
        return

    if slot < 1 or slot > MAX_SLOTS:
        await callback.answer("Invalid slot number.", show_alert=True)
        return

    group_id = callback.message.chat.id
    daily_task_repo = DailyTaskRepo(session)
    existing = await daily_task_repo.get_task_slot(user.id, group_id, slot)

    if existing:
        # Task already set — just show its current status; don't allow re-setting
        status = "✅ Done" if existing.is_done else "⏳ Pending"
        await callback.answer(
            f"{ordinal(slot)} Task: {existing.task_name}\nStatus: {status}",
            show_alert=True,
        )
        return

    # Enter FSM to collect task text from user
    await state.set_state(TaskInput.waiting_for_task_text)
    await state.update_data(slot=slot, group_id=group_id)

    await callback.message.answer(
        f"📝 Enter your <b>{ordinal(slot)} task</b> for today:",
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────────────────────
# GROUP: RECEIVE TASK TEXT (FSM)
# ─────────────────────────────────────

@router.message(TaskInput.waiting_for_task_text)
async def receive_task_text(message: Message, user, session, state: FSMContext):
    data = await state.get_data()
    slot     = data.get("slot")
    group_id = data.get("group_id")

    if not message.text:
        await message.answer("Please send a text message for your task. Try again:")
        return

    task_text = message.text.strip()
    if len(task_text) > 200:
        await message.answer("That's too long (max 200 chars). Please shorten and try again:")
        return

    daily_task_repo = DailyTaskRepo(session)
    await daily_task_repo.upsert_task_slot(user.id, group_id, slot, task_text)
    await state.clear()

    # Refresh and show updated slot menu
    tasks = await daily_task_repo.get_today_tasks(user.id, group_id)
    skip_repo = SkipRepo(session)
    week_start = get_week_start(datetime.now(timezone.utc).date())
    skip_used = (await skip_repo.get_skip_record(user.id, group_id, week_start)) is not None

    n_tasks = len(tasks)
    remaining = MAX_SLOTS - n_tasks
    await message.answer(
        f"✅ <b>Saved!</b>\n\n"
        f"Slots filled: <b>{n_tasks}/{MAX_SLOTS}</b>  "
        f"({'Tap another slot to add more' if remaining else 'All slots filled'} )\n\n"
        f"Tap a slot or tap <b>Done Setting Tasks</b>:",
        reply_markup=task_slots_keyboard(tasks, skip_available=not skip_used),
        parse_mode="HTML",
    )


# ─────────────────────────────────────
# GROUP: TODAY'S TASKS (read-only view)
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_today_task")
async def grp_today_task(callback: CallbackQuery, user, session):
    group_id = callback.message.chat.id
    daily_task_repo = DailyTaskRepo(session)
    tasks = await daily_task_repo.get_today_tasks(user.id, group_id)

    if not tasks:
        await callback.message.answer(
            "📋 <b>Today's Tasks</b>\n\n"
            "You haven't set any tasks yet.\n"
            "Tap <b>Submit Your Task</b> to add them!",
            parse_mode="HTML",
            reply_markup=group_main_menu(),
        )
        await callback.answer()
        return

    n_total = len(tasks)
    n_done  = sum(1 for t in tasks if t.is_done)
    pts     = sum(t.points_awarded for t in tasks)

    lines = [f"📋 <b>Today's Tasks</b> — {n_done}/{n_total} done\n"]
    for task in tasks:
        icon = "✅" if task.is_done else "⬜"
        lines.append(f"{icon} {ordinal(task.slot)}: {task.task_name}")
    lines.append(f"\n📊 Points earned today: <b>{pts}</b>")

    await callback.message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=group_main_menu(),
    )
    await callback.answer()


# ─────────────────────────────────────
# GROUP: UPDATE TASK (show done buttons)
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_update_task")
async def grp_update_task(callback: CallbackQuery, user, session):
    group_id = callback.message.chat.id
    daily_task_repo = DailyTaskRepo(session)
    tasks = await daily_task_repo.get_today_tasks(user.id, group_id)

    if not tasks:
        await callback.message.answer(
            "⚠️ <b>No tasks set for today.</b>\n\n"
            "Tap <b>Submit Your Task</b> first!",
            parse_mode="HTML",
            reply_markup=group_main_menu(),
        )
        await callback.answer()
        return

    n_done = sum(1 for t in tasks if t.is_done)
    await callback.message.answer(
        f"🔄 <b>Update Task</b> — {n_done}/{len(tasks)} done\n\n"
        f"Tap any pending task to mark it as <b>done</b>:",
        reply_markup=update_task_keyboard(tasks),
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────────────────────
# GROUP: MARK TASK DONE → tdone_N
# ─────────────────────────────────────

@router.callback_query(F.data.func(lambda d: d.startswith("tdone_") and not d.startswith("tdone_already_")))
async def grp_mark_done(callback: CallbackQuery, user, session):
    try:
        slot = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid task slot.", show_alert=True)
        return

    group_id = callback.message.chat.id
    today    = datetime.now(timezone.utc).date()

    daily_task_repo = DailyTaskRepo(session)
    tasks    = await daily_task_repo.get_today_tasks(user.id, group_id)
    task_map = {t.slot: t for t in tasks}
    task     = task_map.get(slot)

    if not task:
        await callback.answer("Task not found.", show_alert=True)
        return
    if task.is_done:
        await callback.answer("Already completed! ✅", show_alert=True)
        return

    # ── Point calculation ──────────────────────────────────────────
    n_tasks        = len(tasks)
    points_per_task = max(1, int(80 / n_tasks))   # 80 pts split across tasks

    # Mark this slot done
    await daily_task_repo.mark_task_done(user.id, group_id, slot, points_per_task)

    # Refresh to check if ALL tasks are now done
    tasks    = await daily_task_repo.get_today_tasks(user.id, group_id)
    n_done   = sum(1 for t in tasks if t.is_done)
    all_done = (n_done == n_tasks)

    user_repo = UserRepo(session)
    total_pts_to_add = points_per_task
    bonus_lines: list[str] = []

    if all_done:
        # +20 completion bonus
        total_pts_to_add += 20
        bonus_lines.append("🎉 <b>+20</b> — completed all tasks!")

        # ── Streak update (only on full-day completion) ───────────
        streak_repo = StreakRepo(session)
        streak      = await streak_repo.get_streak(user.id, group_id)
        last_date   = streak.last_submission_date if streak else None
        cur_streak  = streak.current_streak if streak else 0
        new_streak  = calculate_new_streak(last_date, cur_streak)
        await streak_repo.upsert_streak(user.id, group_id, new_streak, today)
        await user_repo.update_streak(user.id, new_streak)

        # ── Streak milestone bonus ────────────────────────────────
        milestone_pts, milestone_label = get_milestone_bonus(new_streak)
        if milestone_pts:
            total_pts_to_add += milestone_pts
            bonus_lines.append(
                f"🏆 <b>+{milestone_pts}</b> — {milestone_label} milestone!"
            )

    await user_repo.update_points(user.id, total_pts_to_add)

    # ── Build response message ─────────────────────────────────────
    pts_today = sum(t.points_awarded for t in tasks)
    msg_lines = [
        f"✅ <b>{ordinal(slot)} task done!</b>  +{points_per_task} pts",
    ]
    if bonus_lines:
        msg_lines.extend(bonus_lines)
    msg_lines.append(f"\nProgress: <b>{n_done}/{n_tasks}</b> tasks done")
    if all_done:
        msg_lines.append("🔥 <b>All done for today!</b>")
    else:
        n_left = n_tasks - n_done
        msg_lines.append(f"({n_left} task{'s' if n_left > 1 else ''} left)")
    msg_lines.append(f"\nTotal points today: <b>{pts_today}</b>")

    # Refresh update keyboard so ticked tasks show ✅
    fresh_tasks = await daily_task_repo.get_today_tasks(user.id, group_id)
    await callback.message.answer(
        "\n".join(msg_lines),
        parse_mode="HTML",
        reply_markup=update_task_keyboard(fresh_tasks),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tdone_already_"))
async def grp_already_done(callback: CallbackQuery):
    await callback.answer("Already completed! ✅", show_alert=True)


# ─────────────────────────────────────
# GROUP: SKIP TODAY (once per week)
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_skip")
async def grp_skip(callback: CallbackQuery, user, session):
    group_id = callback.message.chat.id
    today    = datetime.now(timezone.utc).date()
    week_start = get_week_start(today)

    skip_repo = SkipRepo(session)
    existing  = await skip_repo.get_skip_record(user.id, group_id, week_start)

    if existing:
        await callback.answer(
            "❌ You've already used your skip token this week!\n"
            "It resets every Monday.",
            show_alert=True,
        )
        return

    # Consume the skip token
    await skip_repo.create_skip(user.id, group_id, week_start, today)

    # Advance streak as if they submitted (so it doesn't break)
    streak_repo = StreakRepo(session)
    streak      = await streak_repo.get_streak(user.id, group_id)
    last_date   = streak.last_submission_date if streak else None
    cur_streak  = streak.current_streak if streak else 0
    new_streak  = calculate_new_streak(last_date, cur_streak)
    await streak_repo.upsert_streak(user.id, group_id, new_streak, today)
    await UserRepo(session).update_streak(user.id, new_streak)

    await callback.message.answer(
        "⏭️ <b>Day Skipped!</b>\n\n"
        f"Your streak is protected 🔥 (Day <b>{new_streak}</b>)\n"
        "No points are awarded for skipped days.\n\n"
        "<i>Skip token used — resets next Monday.</i>",
        parse_mode="HTML",
        reply_markup=group_main_menu(),
    )
    await callback.answer()


# ─────────────────────────────────────
# GROUP: TODAY SCORE
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_today_score")
async def grp_today_score(callback: CallbackQuery, user, session):
    group_id = callback.message.chat.id
    daily_task_repo = DailyTaskRepo(session)
    tasks  = await daily_task_repo.get_today_tasks(user.id, group_id)
    pts    = sum(t.points_awarded for t in tasks)
    n_done = sum(1 for t in tasks if t.is_done)
    n_tot  = len(tasks)

    await callback.message.answer(
        f"📊 <b>Today's Score</b>\n\n"
        f"Points earned today : <b>{pts}</b>\n"
        f"Tasks completed      : <b>{n_done}/{n_tot}</b>",
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────────────────────
# GROUP: TOTAL SCORE
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_total_score")
async def grp_total_score(callback: CallbackQuery, user):
    await callback.message.answer(
        f"🏅 <b>Your Total Score</b>\n\n"
        f"Total points: <b>{user.total_points}</b>",
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────────────────────
# GROUP: LEADERBOARD
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_leaderboard")
async def grp_leaderboard(callback: CallbackQuery, session):
    group_id = callback.message.chat.id
    entries  = await leaderboard_service.get_leaderboard(session, group_id)

    if not entries:
        await callback.message.answer(
            "🏆 <b>Leaderboard</b>\n\n"
            "No data yet — start submitting tasks to appear here!",
            parse_mode="HTML",
        )
        await callback.answer()
        return

    medals = ["🥇", "🥈", "🥉"]
    lines  = ["🏆 <b>Leaderboard</b>\n"]
    for e in entries:
        prefix = medals[e["rank"] - 1] if e["rank"] <= 3 else f"{e['rank']}."
        # FIX: show @username so users can identify themselves;
        # fallback to full_name if user has no Telegram username set
        display = f"@{e['username']}" if e.get("username") else e["full_name"]
        lines.append(
            f"{prefix} <b>{display}</b> — {e['points']} pts  🔥{e['streak']}"
        )

    await callback.message.answer("\n".join(lines), parse_mode="HTML")
    await callback.answer()


# ─────────────────────────────────────
# GROUP: MY STREAK
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_streak")
async def grp_streak(callback: CallbackQuery, user, session):
    group_id    = callback.message.chat.id
    streak_repo = StreakRepo(session)
    streak      = await streak_repo.get_streak(user.id, group_id)

    current = streak.current_streak if streak else 0
    longest = streak.longest_streak if streak else 0

    # Next milestone hint
    next_milestone = next(
        (m for m in [7, 14, 21, 28, 30, 60, 90, 120] if m > current), None
    )

    text = (
        f"🔥 <b>Your Streak</b> (this group)\n\n"
        f"Current streak : <b>{current}</b> days\n"
        f"Longest streak : <b>{longest}</b> days\n"
    )
    if next_milestone:
        days_left = next_milestone - current
        bonus = 300 if next_milestone % 30 == 0 else 100
        text += (
            f"\n⭐ <b>{days_left}</b> day{'s' if days_left > 1 else ''} until "
            f"{next_milestone}-day milestone  (+{bonus} pts bonus!)"
        )

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()
