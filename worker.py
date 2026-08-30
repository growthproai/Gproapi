"""
Celery app + periodic (beat) schedule. Run with:
  celery -A app.worker worker --loglevel=info
  celery -A app.worker beat --loglevel=info   (separate process, schedules periodic tasks)
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "growthpro",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.rank_tracking_tasks",
        "app.tasks.report_tasks",
        "app.tasks.scheduling_tasks",
        "app.tasks.email_sequence_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Periodic jobs (spec section 52: background processing for heavy/scheduled work)
celery_app.conf.beat_schedule = {
    "daily-rank-check": {
        "task": "app.tasks.rank_tracking_tasks.check_all_tracked_keywords",
        "schedule": crontab(hour=3, minute=0),  # 03:00 UTC daily
    },
    "weekly-reports": {
        "task": "app.tasks.report_tasks.generate_weekly_reports_for_all_workspaces",
        "schedule": crontab(day_of_week=1, hour=6, minute=0),  # Monday 06:00 UTC
    },
    "publish-due-scheduled-posts": {
        "task": "app.tasks.scheduling_tasks.publish_due_posts",
        "schedule": crontab(minute="*/15"),  # every 15 minutes
    },
    "send-due-sequence-emails": {
        "task": "app.tasks.email_sequence_tasks.send_due_sequence_emails",
        "schedule": crontab(minute="*/30"),  # every 30 minutes
    },
}
