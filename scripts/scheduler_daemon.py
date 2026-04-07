#!/usr/bin/env python
"""
Scheduler daemon — runs scheduled stock analysis jobs.

Spawned by run.bat / run.sh alongside the Streamlit app so users get
automated stock analysis emails without setting up cron / Task Scheduler.

Two configuration modes:

1. JOB-BASED (preferred): config/schedule.json
   Top-level switches plus an array of jobs, each independent.
   Example schedule.json:
       {
         "enabled": true,
         "run_on_startup": true,
         "jobs": [
           {
             "name": "Morning A-Share Brief",
             "enabled": true,
             "times": ["08:30"],
             "weekdays_only": true,
             "queries": ["分析600519.SS", "分析比亚迪"],
             "recipients": ["alice@qq.com"],
             "summary_only": false
           },
           {
             "name": "Midday Tech Watch",
             "times": ["13:00"],
             "queries": ["Analyze AAPL", "Analyze MSFT"],
             "recipients": ["bob@gmail.com"],
             "summary_only": true
           }
         ]
       }

   Top-level fields:
     enabled         : master switch (default true). False -> daemon exits.
     run_on_startup  : run all jobs once at daemon boot (default true)
     jobs            : array of job objects

   Per-job fields:
     name            : display name (used in log + email subject prefix)
     enabled         : per-job switch (default true)
     times           : array of "HH:MM" 24h local times
     weekdays_only   : skip Sat/Sun (default true)
     queries         : array of natural-language queries (zh/en auto-detected)
     recipients      : array of recipient emails for THIS job
     summary_only    : send one batch email vs one per stock (default false)

2. ENV-BASED (fallback when config/schedule.json is missing):
   AUTO_RUN_SCHEDULE=true                  # master switch
   RUN_ON_STARTUP=true                     # run once at boot
   SCHEDULE_DAILY_TIMES=08:30,13:00,20:00  # one or more HH:MM
   SCHEDULE_WEEKDAYS_ONLY=true             # skip weekends
   WATCHLIST=...                           # comma-separated queries
   QQ_EMAIL_RECIPIENTS=...                 # global recipients

Logs go to logs/scheduler.log.
"""

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# UTF-8 console for Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Auto-load .env from project root
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "scheduler.log"
SCHEDULE_FILE = PROJECT_ROOT / "config" / "schedule.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("scheduler_daemon")


def _bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name, str(default)).strip().lower()
    return val in ("1", "true", "yes", "on")


# ─── Job model ─────────────────────────────────────────────────

@dataclass
class Job:
    """A single scheduled analysis job."""
    name: str
    times: list[tuple[int, int]]   # list of (hour, minute)
    queries: list[str]
    recipients: list[str]          # may be empty -> use env QQ_EMAIL_RECIPIENTS
    weekdays_only: bool = True
    summary_only: bool = False
    enabled: bool = True

    def next_run_after(self, now: datetime) -> datetime:
        """Compute the next firing time for this job after `now`."""
        for day_offset in range(0, 14):
            day = now.date() + timedelta(days=day_offset)
            if self.weekdays_only and day.weekday() >= 5:
                continue
            for hh, mm in self.times:
                candidate = datetime(day.year, day.month, day.day, hh, mm, 0)
                if candidate > now:
                    return candidate
        return now + timedelta(hours=24)  # safety fallback


@dataclass
class ScheduleConfig:
    """Top-level scheduler config: master switches + jobs."""
    enabled: bool = True
    run_on_startup: bool = True
    jobs: list[Job] = field(default_factory=list)


def _parse_time_string(s: str) -> tuple[int, int] | None:
    """Parse 'HH:MM' to (hour, minute), return None on invalid."""
    try:
        parts = s.strip().split(":")
        hh, mm = int(parts[0]), int(parts[1])
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return (hh, mm)
    except (ValueError, IndexError, AttributeError):
        pass
    return None


def _parse_times_list(raw) -> list[tuple[int, int]]:
    """Parse a list of HH:MM strings (or comma-separated string) into tuples."""
    if isinstance(raw, str):
        raw = raw.split(",")
    result = []
    for item in raw or []:
        parsed = _parse_time_string(str(item))
        if parsed is not None:
            result.append(parsed)
        else:
            logger.warning("Skipping invalid time %r", item)
    return sorted(set(result))


def load_schedule_config() -> ScheduleConfig:
    """
    Load scheduler config. Tries config/schedule.json first; falls back
    to env-var-based single job (WATCHLIST + SCHEDULE_DAILY_TIMES).

    Top-level switches `enabled` and `run_on_startup` may live in the
    JSON. If absent, env vars AUTO_RUN_SCHEDULE and RUN_ON_STARTUP are
    used as fallback (defaults: enabled=true, run_on_startup=true).
    """
    if SCHEDULE_FILE.exists():
        return _load_schedule_from_file(SCHEDULE_FILE)
    return _load_schedule_from_env()


def _load_schedule_from_file(path: Path) -> ScheduleConfig:
    logger.info("Loading schedule from %s", path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Failed to read %s: %s", path, e)
        return ScheduleConfig(enabled=False)

    # Top-level switches: JSON wins over env vars; env vars are fallback.
    enabled = bool(data.get("enabled", _bool_env("AUTO_RUN_SCHEDULE", default=True)))
    run_on_startup = bool(data.get("run_on_startup", _bool_env("RUN_ON_STARTUP", default=True)))

    raw_jobs = data.get("jobs", [])
    if not isinstance(raw_jobs, list):
        logger.error("'jobs' must be a list")
        return ScheduleConfig(enabled=enabled, run_on_startup=run_on_startup)

    jobs: list[Job] = []
    for i, raw in enumerate(raw_jobs):
        if not isinstance(raw, dict):
            logger.warning("Skipping non-dict job at index %d", i)
            continue
        if not raw.get("enabled", True):
            logger.info("Skipping disabled job: %s", raw.get("name", f"#{i}"))
            continue

        name = str(raw.get("name") or f"job_{i}")
        times = _parse_times_list(raw.get("times") or [])
        queries = [str(q).strip() for q in (raw.get("queries") or []) if str(q).strip()]
        recipients = [str(r).strip() for r in (raw.get("recipients") or []) if str(r).strip()]
        weekdays_only = bool(raw.get("weekdays_only", True))
        summary_only = bool(raw.get("summary_only", False))

        if not times:
            logger.warning("Job %s has no valid times, skipping", name)
            continue
        if not queries:
            logger.warning("Job %s has no queries, skipping", name)
            continue

        jobs.append(Job(
            name=name,
            times=times,
            queries=queries,
            recipients=recipients,
            weekdays_only=weekdays_only,
            summary_only=summary_only,
        ))
        logger.info(
            "Loaded job '%s': %d times, %d queries, %d recipients, weekdays_only=%s",
            name, len(times), len(queries), len(recipients), weekdays_only,
        )

    return ScheduleConfig(enabled=enabled, run_on_startup=run_on_startup, jobs=jobs)


def _load_schedule_from_env() -> ScheduleConfig:
    """Build a single-job ScheduleConfig from env vars (back-compat)."""
    logger.info("config/schedule.json not found, falling back to env-var config")
    raw_times = os.getenv("SCHEDULE_DAILY_TIMES") or os.getenv("SCHEDULE_DAILY_TIME", "17:30")
    times = _parse_times_list(raw_times)
    if not times:
        times = [(17, 30)]

    raw_watchlist = os.getenv("WATCHLIST", "600519.SS")
    queries = [q.strip() for q in raw_watchlist.split(",") if q.strip()]

    job = Job(
        name="env-default",
        times=times,
        queries=queries,
        recipients=[],
        weekdays_only=_bool_env("SCHEDULE_WEEKDAYS_ONLY", default=True),
        summary_only=False,
    )
    return ScheduleConfig(
        enabled=_bool_env("AUTO_RUN_SCHEDULE", default=False),
        run_on_startup=_bool_env("RUN_ON_STARTUP", default=True),
        jobs=[job],
    )


# ─── Job dispatch ──────────────────────────────────────────────

def run_job(job: Job) -> int:
    """Invoke scripts/scheduled_analysis.py for one job. Returns exit code."""
    script_path = PROJECT_ROOT / "scripts" / "scheduled_analysis.py"
    if not script_path.exists():
        logger.error("scheduled_analysis.py not found at %s", script_path)
        return 1

    cmd = [
        sys.executable, str(script_path),
        "--tickers", ",".join(job.queries),
        "--job-name", job.name,
    ]
    if job.recipients:
        cmd += ["--recipients", ",".join(job.recipients)]
    if job.summary_only:
        cmd.append("--summary-only")

    logger.info("Launching job '%s': %d queries -> %d recipients",
                job.name, len(job.queries), len(job.recipients) or "<env>")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30 * 60,
        )
        if result.stdout:
            logger.info("[%s] stdout tail:\n%s", job.name, result.stdout[-2000:])
        if result.stderr:
            logger.warning("[%s] stderr tail:\n%s", job.name, result.stderr[-2000:])
        logger.info("Job '%s' finished with exit code %d", job.name, result.returncode)
        return result.returncode
    except subprocess.TimeoutExpired:
        logger.error("Job '%s' exceeded 30-minute timeout", job.name)
        return 124
    except Exception as e:
        logger.exception("Job '%s' failed: %s", job.name, e)
        return 1


def sleep_until(target: datetime):
    """Sleep until the given datetime, in 60-second chunks for clean shutdown."""
    while True:
        now = datetime.now()
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        chunk = min(remaining, 60)
        time.sleep(chunk)


def main() -> int:
    logger.info("=" * 60)
    logger.info("Scheduler daemon starting (PID %d)", os.getpid())
    logger.info("Log file: %s", LOG_FILE)
    logger.info("=" * 60)

    schedule = load_schedule_config()

    if not schedule.enabled:
        logger.info("Scheduler disabled (set 'enabled': true in config/schedule.json). Daemon exiting.")
        return 0

    jobs = schedule.jobs
    if not jobs:
        logger.error("No jobs configured. Exiting.")
        return 1
    logger.info("Loaded %d job(s) | enabled=%s | run_on_startup=%s",
                len(jobs), schedule.enabled, schedule.run_on_startup)

    if schedule.run_on_startup:
        logger.info("run_on_startup enabled — running all jobs once immediately")
        for job in jobs:
            run_job(job)
    else:
        logger.info("run_on_startup disabled — waiting for first scheduled time")

    while True:
        try:
            now = datetime.now()
            # Compute next firing time per job, pick the earliest
            schedule = [(job.next_run_after(now), job) for job in jobs]
            schedule.sort(key=lambda pair: pair[0])
            next_time, next_job = schedule[0]
            wait_seconds = (next_time - now).total_seconds()
            logger.info(
                "Next: '%s' at %s (in %.1f hours). %d total job(s) queued.",
                next_job.name,
                next_time.strftime("%Y-%m-%d %H:%M:%S"),
                wait_seconds / 3600,
                len(jobs),
            )
            sleep_until(next_time)
            logger.info("Firing job '%s' at %s", next_job.name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            run_job(next_job)
            # After firing, check if more jobs share the same minute and run them too
            now2 = datetime.now()
            for other_time, other_job in schedule[1:]:
                if other_job is next_job:
                    continue
                if abs((other_time - next_time).total_seconds()) < 60 and other_time <= now2:
                    logger.info("Concurrent job '%s' fires at the same time", other_job.name)
                    run_job(other_job)
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, daemon exiting")
            return 0
        except Exception as e:
            logger.exception("Unexpected error in daemon loop: %s", e)
            time.sleep(60)


if __name__ == "__main__":
    sys.exit(main())
