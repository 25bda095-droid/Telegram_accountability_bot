from config import settings

def calculate_points(base: int, streak_day: int) -> int:
    """
    Apply streak multiplier to base points.
    streak_day=1 = first day (no bonus).
    multiplier = 1 + (streak_day - 1) * settings.streak_multiplier
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