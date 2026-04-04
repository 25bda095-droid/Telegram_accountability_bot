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