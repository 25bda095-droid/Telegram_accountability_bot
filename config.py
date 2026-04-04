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