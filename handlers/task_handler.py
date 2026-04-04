import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from keyboards.task_keyboard import TaskCallback, submit_task_keyboard, confirm_submission_keyboard
from services import task_service, notification_service
from config import USER_ERRORS

router = Router()

# /submit command
@router.message(Command("submit"))
async def submit_command(message: Message, user):
    group_id = message.chat.id
    await message.answer(
        "Ready to submit? Tap below!",
        reply_markup=submit_task_keyboard(group_id)
    )

# Callback: task:submit:{group_id}
@router.callback_query(TaskCallback.filter(F.action == "submit"))
async def on_submit(callback: CallbackQuery, callback_data: TaskCallback, user):
    try:
        await callback.message.answer("Send your proof text or photo")
    finally:
        await callback.answer()

# When photo or text arrives after /submit
@router.message(lambda m, data: data.get("pending_task_submit"))
async def on_proof_received(message: Message, user):
    group_id = message.chat.id
    await message.answer(
        "Confirm your submission:",
        reply_markup=confirm_submission_keyboard(group_id)
    )

# Callback: task:confirm:{group_id}
@router.callback_query(TaskCallback.filter(F.action == "confirm"))
async def on_confirm(callback: CallbackQuery, callback_data: TaskCallback, session, user, data):
    try:
        # Ownership check
        if callback.from_user.id != user.id:
            await callback.answer("You are not allowed to confirm this submission.", show_alert=True)
            return

        # Extract proof from data (should be set by previous step)
        proof_text = data.get("proof_text")
        proof_file_id = data.get("proof_file_id")

        result = await task_service.submit_task(
            session, user.id, callback_data.group_id, proof_text, proof_file_id
        )
        if result.success:
            await notification_service.send_submission_success(
                callback.bot, callback.message.chat.id, user.id,
                result.points_awarded, result.new_streak, result.achievements_unlocked
            )
            await callback.answer("✅ Submitted!")
        else:
            error_msg = USER_ERRORS.get(result.error_code, "Something went wrong.")
            await callback.answer(error_msg, show_alert=True)
    except Exception as e:
        logging.error(f"Error in confirm callback: {e}", exc_info=True)
        await callback.answer("Something went wrong.", show_alert=True)

# Callback: task:cancel:{group_id}
@router.callback_query(TaskCallback.filter(F.action == "cancel"))
async def on_cancel(callback: CallbackQuery, callback_data: TaskCallback):
    try:
        await callback.message.answer("Submission cancelled.")
    finally:
        await callback.answer()