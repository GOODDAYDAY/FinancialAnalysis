#!/usr/bin/env python
"""
Scheduler daemon — runs scheduled_analysis.py at configured intervals.

Spawned by run.bat / run.sh alongside the Streamlit app so users get
automated stock analysis emails without setting up cron / Task Scheduler.

Behavior:
  1. On startup, optionally run once immediately (RUN_ON_STARTUP=true)
  2. Loop forever:
     - Sleep until next scheduled time
     - Run scripts/scheduled_analysis.py
     - On error, log and continue (don't crash the daemon)

Configuration via .env:
  AUTO_RUN_SCHEDULE=true                  # required to spawn this at all
  RUN_ON_STARTUP=true                     # run once at daemon start
  SCHEDULE_MODE=daily                     # interval | daily
  SCHEDULE_INTERVAL_HOURS=24              # used when mode=interval
  SCHEDULE_DAILY_TIMES=08:30,13:00,20:00  # one or more HH:MM times, comma-separated
                                          # (SCHEDULE_DAILY_TIME singular still works for back-compat)
  SCHEDULE_WEEKDAYS_ONLY=true             # skip weekends in daily mode

Logs go to logs/scheduler.log.
"""

import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

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


def _parse_daily_times() -> list[tuple[int, int]]:
    """
    Parse comma-separated HH:MM times from SCHEDULE_DAILY_TIMES.
    Falls back to SCHEDULE_DAILY_TIME (singular) for backward compat.
    Returns sorted list of (hour, minute) tuples. Invalid entries are skipped.
    """
    raw = os.getenv("SCHEDULE_DAILY_TIMES")
    if not raw:
        raw = os.getenv("SCHEDULE_DAILY_TIME", "17:30")

    times = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            hh, mm = part.split(":")
            hh, mm = int(hh), int(mm)
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                times.append((hh, mm))
            else:
                logger.warning("Skipping out-of-range time %r", part)
        except (ValueError, AttributeError):
            logger.warning("Skipping invalid time %r in SCHEDULE_DAILY_TIMES", part)

    if not times:
        logger.warning("No valid times parsed, defaulting to 17:30")
        times = [(17, 30)]

    return sorted(set(times))


def compute_next_run(now: datetime) -> datetime:
    """Compute the next scheduled run time based on env config."""
    mode = os.getenv("SCHEDULE_MODE", "daily").strip().lower()

    if mode == "interval":
        hours = float(os.getenv("SCHEDULE_INTERVAL_HOURS", "24"))
        return now + timedelta(hours=hours)

    # Daily mode: support one or more times per day
    times = _parse_daily_times()
    weekdays_only = _bool_env("SCHEDULE_WEEKDAYS_ONLY", default=True)

    # Try today's remaining times first, then push forward day by day
    for day_offset in range(0, 14):  # at most 2 weeks lookahead (handles long weekends)
        day = now.date() + timedelta(days=day_offset)
        if weekdays_only and day.weekday() >= 5:
            continue
        for hh, mm in times:
            candidate = datetime(day.year, day.month, day.day, hh, mm, 0)
            if candidate > now:
                return candidate

    # Should never happen, but return a safe fallback
    return now + timedelta(hours=24)


def run_analysis_once() -> int:
    """Invoke scripts/scheduled_analysis.py as a subprocess. Returns exit code."""
    script_path = PROJECT_ROOT / "scripts" / "scheduled_analysis.py"
    if not script_path.exists():
        logger.error("scheduled_analysis.py not found at %s", script_path)
        return 1

    cmd = [sys.executable, str(script_path)]
    logger.info("Launching: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30 * 60,  # 30 minute hard timeout per run
        )
        if result.stdout:
            logger.info("stdout:\n%s", result.stdout[-2000:])
        if result.stderr:
            logger.warning("stderr:\n%s", result.stderr[-2000:])
        logger.info("Run finished with exit code %d", result.returncode)
        return result.returncode
    except subprocess.TimeoutExpired:
        logger.error("scheduled_analysis.py exceeded 30-minute timeout")
        return 124
    except Exception as e:
        logger.exception("Failed to run scheduled_analysis.py: %s", e)
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
    if not _bool_env("AUTO_RUN_SCHEDULE", default=False):
        logger.info("AUTO_RUN_SCHEDULE is not enabled. Daemon exiting.")
        return 0

    logger.info("=" * 60)
    logger.info("Scheduler daemon starting (PID %d)", os.getpid())
    logger.info("Log file: %s", LOG_FILE)
    logger.info("=" * 60)

    if _bool_env("RUN_ON_STARTUP", default=True):
        logger.info("RUN_ON_STARTUP enabled — running analysis immediately")
        run_analysis_once()
    else:
        logger.info("RUN_ON_STARTUP disabled — waiting for first scheduled time")

    while True:
        try:
            now = datetime.now()
            next_run = compute_next_run(now)
            wait_seconds = (next_run - now).total_seconds()
            logger.info(
                "Next run scheduled at %s (in %.1f hours)",
                next_run.strftime("%Y-%m-%d %H:%M:%S"),
                wait_seconds / 3600,
            )
            sleep_until(next_run)
            logger.info("Triggering scheduled run at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            run_analysis_once()
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, daemon exiting")
            return 0
        except Exception as e:
            logger.exception("Unexpected error in daemon loop: %s", e)
            time.sleep(60)  # Wait a minute before retrying to avoid tight loop


if __name__ == "__main__":
    sys.exit(main())
