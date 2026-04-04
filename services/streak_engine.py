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