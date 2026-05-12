import logging
import threading
from datetime import datetime
from pathlib import Path

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.extensions import scheduler

logger = logging.getLogger(__name__)

INTERVAL_PREFIX = "interval:"


def _parse_trigger(schedule: str):
    """Parse schedule string into an APScheduler trigger.

    Cron format: "0 6 * * *"
    Interval format: "interval:minutes=30" or "interval:hours=1,minutes=30"
    """
    if schedule.startswith(INTERVAL_PREFIX):
        params_str = schedule[len(INTERVAL_PREFIX):]
        params = {k: int(v) for k, v in (p.split("=") for p in params_str.split(","))}
        return IntervalTrigger(**params)

    parts = schedule.split()
    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
        return CronTrigger(
            minute=minute, hour=hour, day=day,
            month=month, day_of_week=day_of_week,
        )
    raise ValueError(f"Invalid schedule format: {schedule!r}")


def _run_job_fn(app, job_id: int) -> None:
    """Execute an ETL job inside the Flask app context."""
    with app.app_context():
        from app.extensions import db
        from app.models.job import ETLJob
        from app.models.upload_log import UploadLog
        from app.services.csv_processor import parse_csv, profile_csv
        from app.services.db_manager import (
            build_column_map,
            bulk_insert,
            coerce_dataframe,
            create_table_if_not_exists,
        )
        from sqlalchemy import create_engine

        job = db.session.get(ETLJob, job_id)
        if not job:
            logger.warning("Job %d not found — skipping", job_id)
            return

        job.status = "running"
        db.session.commit()

        log = UploadLog(
            filename=job.source_path or "",
            target_table=job.target_table or "",
            triggered_by="scheduler",
        )

        try:
            source = Path(job.source_path)
            if not source.exists():
                raise FileNotFoundError(f"Source file not found: {source}")

            df = parse_csv(source)
            profile = profile_csv(df)
            col_map = build_column_map(profile["columns"])

            engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
            table = create_table_if_not_exists(engine, job.target_table, col_map)
            coerced = coerce_dataframe(df, col_map)
            inserted, failed = bulk_insert(engine, table, coerced)

            log.rows_inserted = inserted
            log.rows_failed = failed
            job.status = "success"

        except Exception as exc:
            logger.error("Job %d failed: %s", job_id, exc, exc_info=True)
            log.error_message = str(exc)
            job.status = "failed"

        finally:
            job.last_run = datetime.utcnow()
            db.session.add(log)
            db.session.commit()


def init_scheduler(app) -> None:
    """Start the scheduler and register all existing ETLJobs from the database."""
    from sqlalchemy.exc import ProgrammingError

    from app.models.job import ETLJob

    if not scheduler.running:
        scheduler.start()

    try:
        for job in ETLJob.query.all():
            if job.source_path and job.target_table:
                register_job(app, job)
    except ProgrammingError:
        # Table doesn't exist yet — normal on first run before migrations
        logger.info("etl_jobs table not found; skipping job registration. Run 'flask db upgrade' to create it.")


def register_job(app, job) -> None:
    """Register an ETLJob with APScheduler."""
    job_id_str = f"etl_job_{job.id}"
    try:
        trigger = _parse_trigger(job.schedule)
        scheduler.add_job(
            func=_run_job_fn,
            trigger=trigger,
            id=job_id_str,
            args=[app, job.id],
            replace_existing=True,
        )
        logger.info("Registered %s with schedule %r", job_id_str, job.schedule)
    except Exception as exc:
        logger.error("Failed to register job %d: %s", job.id, exc)


def unregister_job(job_id: int) -> None:
    """Remove an ETLJob from APScheduler."""
    job_id_str = f"etl_job_{job_id}"
    if scheduler.get_job(job_id_str):
        scheduler.remove_job(job_id_str)
        logger.info("Removed %s from scheduler", job_id_str)


def trigger_job_now(app, job_id: int) -> None:
    """Run an ETL job immediately in a daemon thread."""
    t = threading.Thread(target=_run_job_fn, args=[app, job_id], daemon=True)
    t.start()
