#!/usr/bin/env python
"""
Scheduled stock analysis task.

Runs the full multi-agent analysis pipeline for each stock in the watchlist
and emails the results via QQ SMTP.

Usage:
    uv run python scripts/scheduled_analysis.py
    uv run python scripts/scheduled_analysis.py --tickers 600519.SS,000858.SZ
    uv run python scripts/scheduled_analysis.py --dry-run

Configuration via .env:
    QQ_EMAIL=xxx@qq.com
    QQ_EMAIL_PASSWORD=<authorization code from QQ Mail settings>
    QQ_EMAIL_RECIPIENTS=xxx@qq.com,yyy@qq.com
    WATCHLIST=600519.SS,000858.SZ,300750.SZ
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(str(PROJECT_ROOT))

# UTF-8 console output for Windows + line buffering for live logs
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scheduled_analysis")


def parse_args():
    parser = argparse.ArgumentParser(description="Scheduled stock analysis with email notification")
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated tickers/queries to analyze. Overrides WATCHLIST env var.",
    )
    parser.add_argument(
        "--recipients",
        type=str,
        default=None,
        help="Comma-separated recipient emails. Overrides QQ_EMAIL_RECIPIENTS env var.",
    )
    parser.add_argument(
        "--job-name",
        type=str,
        default=None,
        help="Job display name (used in log + email subject prefix).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run analysis but skip sending email",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Send one summary email instead of one per stock",
    )
    return parser.parse_args()


def get_watchlist(arg_tickers: str | None) -> list[str]:
    """
    Resolve watchlist from CLI arg, env var, or default.

    Each entry can be either:
      - A bare ticker symbol (e.g. "600519.SS", "AAPL") — wrapped as "Analyze {ticker}"
      - A full natural-language query (e.g. "分析贵州茅台", "Tell me about TSLA")

    The orchestrator will detect the language of each query and emit
    a report in the matching language.

    Comma is the separator. To use a comma inside a query, escape it as \\,
    or use a different separator by setting WATCHLIST_SEPARATOR in .env.
    """
    if arg_tickers:
        raw = arg_tickers
    else:
        raw = os.getenv("WATCHLIST", "600519.SS")

    sep = os.getenv("WATCHLIST_SEPARATOR", ",")
    items = [t.strip() for t in raw.split(sep) if t.strip()]
    return items


def _build_query_from_entry(entry: str) -> str:
    """
    Convert a watchlist entry into a query string.

    If the entry looks like a bare ticker (contains no spaces and matches
    a ticker-ish pattern), wrap it as "Analyze {entry}".
    Otherwise treat it as a raw user query.
    """
    import re
    # Bare ticker heuristic: no spaces, matches AAPL or 600519.SS or 0700.HK style
    if " " not in entry and re.fullmatch(r"[A-Za-z0-9._-]+", entry):
        return f"Analyze {entry}"
    return entry


def main():
    args = parse_args()

    # Lazy import after path setup
    from backend.graph import run_analysis, get_graph
    from backend.notification import send_email, EmailConfig
    from backend.notification.templates import render_analysis_email, render_batch_summary

    job_label = args.job_name or "default"
    logger.info("Job: %s", job_label)

    watchlist = get_watchlist(args.tickers)
    if not watchlist:
        logger.error("Empty watchlist. Set WATCHLIST in .env or use --tickers")
        return 1

    logger.info("Watchlist: %s", watchlist)

    # Pre-flight email config check (unless dry-run)
    email_config: "EmailConfig | None" = None
    if not args.dry_run:
        email_config = EmailConfig.from_env()
        # Override recipients from CLI if provided
        if args.recipients:
            override = [r.strip() for r in args.recipients.split(",") if r.strip()]
            if override:
                email_config.recipients = override
        valid, msg = email_config.is_valid()
        if not valid:
            logger.error("Email config invalid: %s", msg)
            logger.error("Configure QQ_EMAIL, QQ_EMAIL_PASSWORD, QQ_EMAIL_RECIPIENTS in .env or pass --recipients")
            return 1
        logger.info("Email config OK. Will send to: %s", email_config.recipients)

    # Reset graph singleton to ensure fresh state
    import backend.graph
    backend.graph._graph = None
    get_graph()  # Pre-compile

    results = []
    failed = []

    for entry in watchlist:
        query = _build_query_from_entry(entry)
        logger.info("=" * 60)
        logger.info("Analyzing entry: %s", entry)
        logger.info("  Built query: %s", query)
        try:
            result = run_analysis(query)

            if result.get("intent") != "stock_query":
                logger.warning("Skipping %s: intent=%s", entry, result.get("intent"))
                failed.append((entry, f"intent={result.get('intent')}"))
                continue

            errors = result.get("errors", [])
            if errors:
                logger.warning("%s had errors: %s", entry, errors)

            rec = result.get("recommendation", {}).get("recommendation", "?")
            lang = result.get("language", "en")
            logger.info("%s: %s (lang=%s)", entry, rec.upper(), lang)
            results.append(result)

        except Exception as e:
            logger.exception("Failed to analyze %s: %s", entry, e)
            failed.append((entry, str(e)))

    if not results:
        logger.error("No successful analysis results. Aborting email.")
        return 1

    logger.info("=" * 60)
    logger.info("Analysis complete: %d succeeded, %d failed", len(results), len(failed))

    if args.dry_run:
        logger.info("DRY RUN: Skipping email send.")
        for r in results:
            ticker = r.get("ticker")
            rec = r.get("recommendation", {}).get("recommendation")
            logger.info("  %s -> %s", ticker, rec)
        return 0

    # Send emails
    if args.summary_only or len(results) > 1:
        # Batch summary email
        subject, html_body, text_body = render_batch_summary(results)
        if args.job_name:
            subject = f"[{args.job_name}] {subject}"
        success, msg = send_email(
            subject=subject, html_body=html_body, text_body=text_body, config=email_config,
        )
        if success:
            logger.info("Summary email sent: %s", msg)
        else:
            logger.error("Failed to send summary email: %s", msg)
            return 1
    else:
        # Individual emails per stock
        for result in results:
            subject, html_body, text_body = render_analysis_email(result)
            if args.job_name:
                subject = f"[{args.job_name}] {subject}"
            success, msg = send_email(
                subject=subject, html_body=html_body, text_body=text_body, config=email_config,
            )
            if success:
                logger.info("Email for %s sent: %s", result.get("ticker"), msg)
            else:
                logger.error("Failed to send email for %s: %s", result.get("ticker"), msg)

    return 0


if __name__ == "__main__":
    sys.exit(main())
