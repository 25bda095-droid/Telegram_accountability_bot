from datetime import date


def calculate_new_streak(last_submission_date: date | None, current_streak: int) -> int:
    """
    - No previous submission  → streak = 1
    - Last submission yesterday → streak = current_streak + 1
    - Last submission today     → streak unchanged (already counted)
    - Gap > 1 day               → streak resets to 1
    """
    today = date.today()
    if last_submission_date is None:
        return 1
    delta = (today - last_submission_date).days
    if delta == 1:
        return current_streak + 1
    elif delta == 0:
        return current_streak      # Already updated today (skip case)
    else:
        return 1                   # Streak broken


def is_streak_milestone(streak: int) -> bool:
    milestones = {3, 7, 14, 30, 60, 100}
    return streak in milestones


def get_milestone_bonus(new_streak: int) -> tuple[int, str]:
    """
    Return (bonus_points, label) when a streak crosses a milestone.

    Rules:
      • Every 7 days  → +100 pts  (day 7, 14, 21, 28 …)
      • Every 30 days → +300 pts  (day 30, 60, 90 …)
        (the 30-day check takes priority over the 7-day check)

    Returns (0, "") when no milestone is hit this day.
    """
    if new_streak <= 0:
        return 0, ""

    # Monthly milestone takes priority
    if new_streak % 30 == 0:
        months = new_streak // 30
        label = f"{months} month{'s' if months > 1 else ''} streak"
        return 300, label

    # Weekly milestone
    if new_streak % 7 == 0:
        weeks = new_streak // 7
        label = f"{weeks} week{'s' if weeks > 1 else ''} streak"
        return 100, label

    return 0, ""
