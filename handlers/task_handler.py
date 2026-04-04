import logging
from datetime import datetime, timezone, timedelta, date as date_type

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from repositories.task_repo import DailyTaskRepo, SkipRepo, UserTaskLockRepo
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
    waiting_for_task_text = State()
    # FSM data keys stored:
    #   slot              – int, which slot (1-6)
    #   group_id          – int, the group chat id
    #   slots_message_id  – int, message_id of the task-slots keyboard (to edit in place)
    #   prompt_message_id – int, message_id of the "Enter your task" prompt (to delete)


# ─────────────────────────────────────
# Helpers
# ─────────────────────────────────────

_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th"}


def ordinal(n: int) -> str:
    return _ORDINALS.get(n, f"{n}th")


def get_week_start(d: date_type) -> date_type:
    """Return the Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


def display_name(user) -> str:
    """Return @username if set on the ORM user, otherwise full_name."""
    return f"@{user.username}" if getattr(user, "username", None) else user.full_name


def back_to_menu() -> InlineKeyboardMarkup:
    """Single Back button used on every info/result screen."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="grp_main_menu")]
    ])


async def safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML",
) -> None:
    """
    Edit the current message in place.
    Falls back to answer() silently if the message is too old or content unchanged.
    Never raises — all display errors are swallowed.
    """
    try:
        await callback.message.edit_text(
            text, parse_mode=parse_mode, reply_markup=reply_markup
        )
    except Exception:
        try:
            await callback.message.answer(
                text, parse_mode=parse_mode, reply_markup=reply_markup
            )
        except Exception:
            pass


def _slot_label(slot: int, task=None) -> str:
    """Build the display label for a task-slot button."""
    label_prefix = ordinal(slot)
    if task is None:
        return f"➕ {label_prefix} Task"
    name_preview = task.task_name[:22]
    if task.is_done:
        return f"✅ {label_prefix}: {name_preview}"
    return f"📝 {label_prefix}: {name_preview}"


def task_slots_keyboard(tasks: list, skip_available: bool = True) -> InlineKeyboardMarkup:
    """
    6 task-slot buttons.
    Filled slots show task name; empty slots show ➕.
    Bottom row: Skip (optional) + Done Setting Tasks.
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
    bottom = []
    if skip_available:
        bottom.append(
            InlineKeyboardButton(text="⏭️ Skip Today (1×/week)", callback_data="grp_skip")
        )
    bottom.append(
        InlineKeyboardButton(text="✔️ Done Setting Tasks", callback_data="grp_finalize_tasks")
    )
    buttons.append(bottom)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def update_task_keyboard(tasks: list) -> InlineKeyboardMarkup:
    """
    Each task as a button.
    Done tasks: tapping shows 'Already completed' popup.
    Pending tasks: tapping marks them done.
    Back button at the bottom.
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
    buttons.append([
        InlineKeyboardButton(text="🔙 Back to Menu", callback_data="grp_main_menu")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─────────────────────────────────────
# PRIVATE CHAT CALLBACKS
# ─────────────────────────────────────

@router.callback_query(F.data == "priv_total_score")
async def priv_total_score(callback: CallbackQuery, user):
    await safe_edit(
        callback,
        f"🏅 <b>Your Total Score</b>\n\nTotal points: <b>{user.total_points}</b>",
        reply_markup=private_main_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "priv_streak")
async def priv_streak(callback: CallbackQuery, user):
    await safe_edit(
        callback,
        f"🔥 <b>Your Streak</b>\n\n"
        f"Current streak : <b>{user.current_streak}</b> days\n"
        f"Longest streak : <b>{user.longest_streak}</b> days\n\n"
        f"Add me to a group for per-group streak tracking!",
        reply_markup=private_main_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "priv_rank")
async def priv_rank(callback: CallbackQuery, user):
    await safe_edit(
        callback,
        f"🏅 <b>Your Rank</b>\n\n"
        f"Total points: <b>{user.total_points}</b>\n\n"
        f"Add me to a group to see your group rank! 🏆",
        reply_markup=private_main_menu(),
    )
    await callback.answer()


# ─────────────────────────────────────
# GROUP: BACK TO MAIN MENU
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_main_menu")
async def grp_main_menu_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(callback, "👇 Main Menu:", reply_markup=group_main_menu())
    await callback.answer()


# ─────────────────────────────────────
# GROUP: FINALISE TASKS FOR TODAY
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_finalize_tasks")
async def grp_finalize_tasks(callback: CallbackQuery, user, session, state: FSMContext):
    """Lock the user's task list for today. Called from 'Done Setting Tasks' button."""
    await state.clear()
    group_id = callback.message.chat.id
    today    = datetime.now(timezone.utc).date()

    daily_task_repo = DailyTaskRepo(session)
    tasks = await daily_task_repo.get_today_tasks(user.id, group_id)

    if not tasks:
        await callback.answer(
            "⚠️ Add at least one task before finalising!", show_alert=True
        )
        return

    lock_repo = UserTaskLockRepo(session)
    await lock_repo.lock_tasks(user.id, group_id, today)

    n_tasks = len(tasks)
    await safe_edit(
        callback,
        f"🔒 <b>Tasks Locked for Today!</b>\n\n"
        f"You've set <b>{n_tasks}</b> task{'s' if n_tasks > 1 else ''} for today.\n"
        f"Use <b>Update Task</b> to mark them done and earn points!\n\n"
        f"<i>No more tasks can be added today.</i>",
        reply_markup=back_to_menu(),
    )
    await callback.answer()

    # ── Public group announcement ─────────────────────────────────
    name = display_name(user)
    await callback.bot.send_message(
        group_id,
        f"📋 <b>{name}</b> has set their tasks for today! 🔥\n"
        f"Let's hold them accountable!",
        parse_mode="HTML",
    )


# ─────────────────────────────────────
# GROUP: SUBMIT YOUR TASK
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_submit")
async def grp_submit(callback: CallbackQuery, user, session):
    group_id = callback.message.chat.id
    today    = datetime.now(timezone.utc).date()

    daily_task_repo = DailyTaskRepo(session)
    tasks = await daily_task_repo.get_today_tasks(user.id, group_id)

    # Block if user already finalised tasks today
    lock_repo = UserTaskLockRepo(session)
    if await lock_repo.is_locked(user.id, group_id, today):
        await callback.answer(
            "⛔ You already finalised your tasks for today!\n"
            "Tasks can only be set once per day.",
            show_alert=True,
        )
        return

    # Block if any task is already marked done (exploit prevention)
    if any(t.is_done for t in tasks):
        await callback.answer(
            "⛔ You have already started completing tasks today!\n"
            "No new tasks can be added once you begin.",
            show_alert=True,
        )
        return

    # All 6 slots filled — no more adding
    if len(tasks) >= MAX_SLOTS:
        await callback.answer(
            "You've filled all 6 task slots today! "
            "Use 'Update Task' to mark them done.",
            show_alert=True,
        )
        return

    skip_repo  = SkipRepo(session)
    week_start = get_week_start(today)
    skip_used  = (await skip_repo.get_skip_record(user.id, group_id, week_start)) is not None
    n_tasks    = len(tasks)

    # Edit existing message in place — no new message posted
    await safe_edit(
        callback,
        f"📋 <b>Set Your Tasks for Today</b>\n"
        f"Slots filled: <b>{n_tasks}/{MAX_SLOTS}</b>\n\n"
        f"Tap any slot to add or view a task:",
        reply_markup=task_slots_keyboard(tasks, skip_available=not skip_used),
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

    group_id        = callback.message.chat.id
    daily_task_repo = DailyTaskRepo(session)
    existing        = await daily_task_repo.get_task_slot(user.id, group_id, slot)

    if existing:
        # Task already set — show its status as a popup; no new message
        status = "✅ Done" if existing.is_done else "⏳ Pending"
        await callback.answer(
            f"{ordinal(slot)} Task: {existing.task_name}\nStatus: {status}",
            show_alert=True,
        )
        return

    # Store the task-slots keyboard message_id so receive_task_text can edit it in place
    slots_message_id = callback.message.message_id

    await state.set_state(TaskInput.waiting_for_task_text)
    await state.update_data(slot=slot, group_id=group_id, slots_message_id=slots_message_id)

    # Post the prompt and immediately store its message_id so we can delete it later
    prompt_msg = await callback.message.answer(
        f"📝 Enter your <b>{ordinal(slot)} task</b> for today:",
        parse_mode="HTML",
    )
    await state.update_data(prompt_message_id=prompt_msg.message_id)
    await callback.answer()


# ─────────────────────────────────────
# GROUP: RECEIVE TASK TEXT (FSM)
#
# Flow:
#   1. Delete the "Enter your task" prompt (clean up bot message)
#   2. Delete the user's typed message  (clean up user message — needs delete permission)
#   3. Edit the original task-slots keyboard in place with the updated slot list
#
# Falls back to message.answer() only if the original slots message is gone.
# All deletes are wrapped in try/except — failure is non-fatal.
# ─────────────────────────────────────

@router.message(TaskInput.waiting_for_task_text)
async def receive_task_text(message: Message, user, session, state: FSMContext):
    data              = await state.get_data()
    slot              = data.get("slot")
    group_id          = data.get("group_id")
    slots_message_id  = data.get("slots_message_id")
    prompt_message_id = data.get("prompt_message_id")

    if not message.text:
        await message.answer("Please send a text message for your task. Try again:")
        return

    task_text = message.text.strip()
    if len(task_text) > 200:
        await message.answer("That's too long (max 200 chars). Please shorten and try again:")
        return

    # Save the task first before doing any cleanup
    daily_task_repo = DailyTaskRepo(session)
    await daily_task_repo.upsert_task_slot(user.id, group_id, slot, task_text)
    await state.clear()

    # ── Step 1: Delete the "Enter your task" prompt ───────────────
    if prompt_message_id:
        try:
            await message.bot.delete_message(group_id, prompt_message_id)
        except Exception:
            pass  # Already deleted or too old — ignore

    # ── Step 2: Delete the user's typed message ───────────────────
    # Requires bot to have "Delete messages" admin permission in the group.
    # If permission is missing this silently fails — everything else still works.
    try:
        await message.delete()
    except Exception:
        pass

    # ── Step 3: Build updated keyboard and text ───────────────────
    tasks      = await daily_task_repo.get_today_tasks(user.id, group_id)
    skip_repo  = SkipRepo(session)
    week_start = get_week_start(datetime.now(timezone.utc).date())
    skip_used  = (await skip_repo.get_skip_record(user.id, group_id, week_start)) is not None
    n_tasks    = len(tasks)
    remaining  = MAX_SLOTS - n_tasks

    updated_text = (
        f"✅ <b>Saved!</b>\n\n"
        f"Slots filled: <b>{n_tasks}/{MAX_SLOTS}</b>  "
        f"({'Tap another slot to add more' if remaining else 'All slots filled'})\n\n"
        f"Tap a slot or tap <b>Done Setting Tasks</b>:"
    )
    updated_keyboard = task_slots_keyboard(tasks, skip_available=not skip_used)

    # ── Step 4: Edit the original task-slots message in place ─────
    # This is the key change — no new message posted, existing message updates silently.
    if slots_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=group_id,
                message_id=slots_message_id,
                text=updated_text,
                reply_markup=updated_keyboard,
                parse_mode="HTML",
            )
            return  # Success — done, no fallback needed
        except Exception:
            pass  # Original message gone (e.g. deleted by admin) — fall through to answer()

    # Fallback: only if original slots message is gone
    await message.answer(updated_text, reply_markup=updated_keyboard, parse_mode="HTML")


# ─────────────────────────────────────
# GROUP: TODAY'S TASKS (read-only view)
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_today_task")
async def grp_today_task(callback: CallbackQuery, user, session):
    group_id        = callback.message.chat.id
    daily_task_repo = DailyTaskRepo(session)
    tasks           = await daily_task_repo.get_today_tasks(user.id, group_id)

    if not tasks:
        await safe_edit(
            callback,
            "📋 <b>Today's Tasks</b>\n\nYou haven't set any tasks yet.\n"
            "Tap <b>Submit Your Task</b> to add them!",
            reply_markup=back_to_menu(),
        )
        await callback.answer()
        return

    n_total = len(tasks)
    n_done  = sum(1 for t in tasks if t.is_done)
    pts     = sum(t.points_awarded for t in tasks)

    lines = [f"📋 <b>Today's Tasks</b> — {n_done}/{n_total} done\n"]
    for task in sorted(tasks, key=lambda t: t.slot):
        icon = "✅" if task.is_done else "⬜"
        lines.append(f"{icon} {ordinal(task.slot)}: {task.task_name}")
    lines.append(f"\n📊 Points earned today: <b>{pts}</b>")

    await safe_edit(callback, "\n".join(lines), reply_markup=back_to_menu())
    await callback.answer()


# ─────────────────────────────────────
# GROUP: UPDATE TASK (show done buttons)
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_update_task")
async def grp_update_task(callback: CallbackQuery, user, session):
    group_id        = callback.message.chat.id
    daily_task_repo = DailyTaskRepo(session)
    tasks           = await daily_task_repo.get_today_tasks(user.id, group_id)

    if not tasks:
        await safe_edit(
            callback,
            "⚠️ <b>No tasks set for today.</b>\n\nTap <b>Submit Your Task</b> first!",
            reply_markup=back_to_menu(),
        )
        await callback.answer()
        return

    n_done = sum(1 for t in tasks if t.is_done)
    await safe_edit(
        callback,
        f"🔄 <b>Update Task</b> — {n_done}/{len(tasks)} done\n\n"
        f"Tap any pending task to mark it as <b>done</b>:",
        reply_markup=update_task_keyboard(tasks),
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

    group_id        = callback.message.chat.id
    today           = datetime.now(timezone.utc).date()
    daily_task_repo = DailyTaskRepo(session)
    tasks           = await daily_task_repo.get_today_tasks(user.id, group_id)
    task_map        = {t.slot: t for t in tasks}
    task            = task_map.get(slot)

    if not task:
        await callback.answer("Task not found.", show_alert=True)
        return
    if task.is_done:
        await callback.answer("Already completed! ✅", show_alert=True)
        return

    # ── Point calculation: 80 pts split evenly across tasks ───────
    n_tasks         = len(tasks)
    points_per_task = max(1, int(80 / n_tasks))

    await daily_task_repo.mark_task_done(user.id, group_id, slot, points_per_task)

    # Refresh to check if ALL tasks are now done
    tasks    = await daily_task_repo.get_today_tasks(user.id, group_id)
    n_done   = sum(1 for t in tasks if t.is_done)
    all_done = (n_done == n_tasks)

    user_repo        = UserRepo(session)
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
            bonus_lines.append(f"🏆 <b>+{milestone_pts}</b> — {milestone_label} milestone!")

    await user_repo.update_points(user.id, total_pts_to_add)

    # ── Build response message ────────────────────────────────────
    pts_today = sum(t.points_awarded for t in tasks)
    msg_lines = [f"✅ <b>{ordinal(slot)} task done!</b>  +{points_per_task} pts"]
    if bonus_lines:
        msg_lines.extend(bonus_lines)
    msg_lines.append(f"\nProgress: <b>{n_done}/{n_tasks}</b> tasks done")
    if all_done:
        msg_lines.append("🔥 <b>All done for today!</b>")
    else:
        n_left = n_tasks - n_done
        msg_lines.append(f"({n_left} task{'s' if n_left > 1 else ''} left)")
    msg_lines.append(f"\nTotal points today: <b>{pts_today}</b>")

    # Refresh keyboard so ticked tasks show ✅ — edits in place
    fresh_tasks = await daily_task_repo.get_today_tasks(user.id, group_id)
    await safe_edit(
        callback,
        "\n".join(msg_lines),
        reply_markup=update_task_keyboard(fresh_tasks),
    )
    await callback.answer()

    # ── Public group announcement when ALL tasks completed ────────
    if all_done:
        name = display_name(user)
        await callback.bot.send_message(
            group_id,
            f"🎉 <b>{name}</b> just completed ALL their tasks today!\n"
            f"Absolute beast mode! 🔥",
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("tdone_already_"))
async def grp_already_done(callback: CallbackQuery):
    await callback.answer("Already completed! ✅", show_alert=True)


# ─────────────────────────────────────
# GROUP: SKIP TODAY (once per week)
#
# Business logic completely untouched.
# Skip token, streak protection, no-points — all identical to original.
# Only display changed: safe_edit() instead of message.answer().
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_skip")
async def grp_skip(callback: CallbackQuery, user, session):
    group_id   = callback.message.chat.id
    today      = datetime.now(timezone.utc).date()
    week_start = get_week_start(today)

    skip_repo = SkipRepo(session)
    existing  = await skip_repo.get_skip_record(user.id, group_id, week_start)

    if existing:
        await callback.answer(
            "❌ You've already used your skip token this week!\nIt resets every Monday.",
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

    await safe_edit(
        callback,
        f"⏭️ <b>Day Skipped!</b>\n\n"
        f"Your streak is protected 🔥 (Day <b>{new_streak}</b>)\n"
        f"No points are awarded for skipped days.\n\n"
        f"<i>Skip token used — resets next Monday.</i>",
        reply_markup=back_to_menu(),
    )
    await callback.answer()


# ─────────────────────────────────────
# GROUP: TODAY SCORE — private popup only, nothing posted to group
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_today_score")
async def grp_today_score(callback: CallbackQuery, user, session):
    group_id        = callback.message.chat.id
    daily_task_repo = DailyTaskRepo(session)
    tasks  = await daily_task_repo.get_today_tasks(user.id, group_id)
    pts    = sum(t.points_awarded for t in tasks)
    n_done = sum(1 for t in tasks if t.is_done)
    n_tot  = len(tasks)
    await callback.answer(
        f"📊 Today's Score\n\nPoints earned : {pts}\nTasks done    : {n_done}/{n_tot}",
        show_alert=True,
    )


# ─────────────────────────────────────
# GROUP: TOTAL SCORE — private popup only, nothing posted to group
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_total_score")
async def grp_total_score(callback: CallbackQuery, user):
    await callback.answer(
        f"🏅 Your Total Score\n\nTotal points: {user.total_points}",
        show_alert=True,
    )


# ─────────────────────────────────────
# GROUP: LEADERBOARD
# ─────────────────────────────────────

@router.callback_query(F.data == "grp_leaderboard")
async def grp_leaderboard(callback: CallbackQuery, session):
    group_id = callback.message.chat.id
    entries  = await leaderboard_service.get_leaderboard(session, group_id)

    if not entries:
        await safe_edit(
            callback,
            "🏆 <b>Leaderboard</b>\n\nNo data yet — start submitting tasks to appear here!",
            reply_markup=back_to_menu(),
        )
        await callback.answer()
        return

    medals = ["🥇", "🥈", "🥉"]
    lines  = ["🏆 <b>Leaderboard</b>\n"]
    for e in entries:
        prefix = medals[e["rank"] - 1] if e["rank"] <= 3 else f"{e['rank']}."
        name   = f"@{e['username']}" if e.get("username") else e["full_name"]
        lines.append(f"{prefix} <b>{name}</b> — {e['points']} pts  🔥{e['streak']}")

    await safe_edit(callback, "\n".join(lines), reply_markup=back_to_menu())
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

    await safe_edit(callback, text, reply_markup=back_to_menu())
    await callback.answer()
