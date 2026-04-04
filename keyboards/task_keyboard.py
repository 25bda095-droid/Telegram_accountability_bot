from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData


# ─────────────────────────────────────
# Legacy callback data (kept for admin)
# ─────────────────────────────────────

class TaskCallback(CallbackData, prefix="task"):
    action: str    # "submit" | "confirm" | "cancel"
    group_id: int


def admin_keyboard(group_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Members",   callback_data=f"admin:members:{group_id}")
    builder.button(text="📋 Audit Log", callback_data=f"admin:audit:{group_id}")
    builder.button(text="⚙️ Configure", callback_data=f"admin:config:{group_id}")
    builder.adjust(1)
    return builder.as_markup()


# ─────────────────────────────────────
# Shared menus
# ─────────────────────────────────────

def group_main_menu() -> InlineKeyboardMarkup:
    """Full-feature menu shown in group chats."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Submit Your Task",  callback_data="grp_submit")],
        [
            InlineKeyboardButton(text="📋 Today's Tasks",  callback_data="grp_today_task"),
            InlineKeyboardButton(text="🔄 Update Task",    callback_data="grp_update_task"),
        ],
        [
            InlineKeyboardButton(text="📊 Today Score",    callback_data="grp_today_score"),
            InlineKeyboardButton(text="🏅 Total Score",    callback_data="grp_total_score"),
        ],
        [InlineKeyboardButton(text="🏆 Leaderboard",       callback_data="grp_leaderboard")],
        [InlineKeyboardButton(text="🔥 My Streak",         callback_data="grp_streak")],
    ])


def private_main_menu() -> InlineKeyboardMarkup:
    """Limited menu shown in private / DM chats."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 My Total Score",    callback_data="priv_total_score")],
        [InlineKeyboardButton(text="🔥 My Current Streak", callback_data="priv_streak")],
        [InlineKeyboardButton(text="🏅 My Rank",           callback_data="priv_rank")],
    ])
