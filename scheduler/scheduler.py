from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import settings
from scheduler.jobs import (
    job_open_task_window,
    job_close_task_window,
    job_check_broken_streaks,
    job_weekly_summary,
)

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