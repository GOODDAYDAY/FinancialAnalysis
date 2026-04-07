#!/usr/bin/env python
"""
Diagnostic script for QQ Mail SMTP connectivity.

Run this when the scheduler daemon reports
  'SMTP error: Connection unexpectedly closed'
or any other SMTP failure. The script tries multiple connection
strategies and reports exactly which step fails.

Usage:
    uv run python scripts/test_email_smtp.py
    uv run python scripts/test_email_smtp.py --to other@example.com

Configuration is read from .env (or env vars) and command-line args.
"""

import argparse
import os
import smtplib
import socket
import ssl
import sys
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# UTF-8 console for Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

# Auto-load .env
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass


def color(text: str, code: str) -> str:
    """ANSI color (skipped on Windows where it may not render)."""
    if os.name == "nt":
        return text
    return f"\033[{code}m{text}\033[0m"


def ok(msg):
    print(f"  [PASS] {msg}")


def fail(msg):
    print(f"  [FAIL] {msg}")


def info(msg):
    print(f"  [INFO] {msg}")


def step(num, title):
    print()
    print(f"━━━ Step {num}: {title} ━━━")


def parse_args():
    p = argparse.ArgumentParser(description="Diagnose QQ Mail SMTP connectivity")
    p.add_argument("--host", default=os.getenv("SMTP_HOST", "smtp.qq.com"))
    p.add_argument("--port", type=int, default=int(os.getenv("SMTP_PORT", "465")))
    p.add_argument("--user", default=os.getenv("QQ_EMAIL", ""))
    p.add_argument("--password", default=os.getenv("QQ_EMAIL_PASSWORD", ""))
    p.add_argument("--to", default=None,
                   help="Recipient. Defaults to the first address in QQ_EMAIL_RECIPIENTS, "
                        "or the sender's own address.")
    p.add_argument("--debug", action="store_true",
                   help="Enable smtplib protocol-level debug output")
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 70)
    print(" QQ Mail SMTP Diagnostic")
    print("=" * 70)

    # ── Step 0: Show config ───────────────────────────────────────
    step(0, "Configuration")
    masked_pwd = (args.password[:2] + "***" + args.password[-2:]) if args.password else "(empty)"
    print(f"  SMTP_HOST          = {args.host}")
    print(f"  SMTP_PORT          = {args.port}")
    print(f"  QQ_EMAIL (sender)  = {args.user!r}")
    print(f"  QQ_EMAIL_PASSWORD  = {masked_pwd}  (length {len(args.password)})")

    if not args.user:
        fail("QQ_EMAIL is empty. Set it in .env or pass --user")
        return 1
    if not args.password:
        fail("QQ_EMAIL_PASSWORD is empty. Set it in .env or pass --password")
        return 1
    if len(args.password) != 16:
        info(f"WARNING: QQ Mail authorization code is normally 16 chars; "
             f"yours is {len(args.password)}. If you put your real QQ password "
             f"here, get an authorization code from QQ Mail web settings.")

    recipients_raw = os.getenv("QQ_EMAIL_RECIPIENTS", "")
    if args.to:
        to_addr = args.to
    elif recipients_raw:
        to_addr = recipients_raw.split(",")[0].strip()
    else:
        to_addr = args.user  # send to self
    print(f"  Recipient (--to)   = {to_addr}")

    # ── Step 1: DNS resolution ────────────────────────────────────
    step(1, "DNS resolution")
    try:
        addrs = socket.getaddrinfo(args.host, args.port, type=socket.SOCK_STREAM)
        for fam, _, _, _, addr in addrs[:3]:
            ok(f"{args.host} -> {addr[0]} ({fam.name})")
    except socket.gaierror as e:
        fail(f"DNS resolution failed: {e}")
        return 1

    # ── Step 2: TCP connect ───────────────────────────────────────
    step(2, f"TCP connect to {args.host}:{args.port}")
    try:
        sock = socket.create_connection((args.host, args.port), timeout=15)
        ok(f"Connected: local {sock.getsockname()} -> remote {sock.getpeername()}")
        sock.close()
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        fail(f"TCP connect failed: {e}")
        info("Possible causes: firewall blocks outbound port, "
             "ISP blocks SMTP, wrong port, host unreachable.")
        return 1

    # ── Step 3: SMTP handshake ────────────────────────────────────
    step(3, f"SMTP handshake on port {args.port}")
    use_ssl = args.port == 465
    print(f"  Strategy: {'SMTP_SSL (implicit TLS)' if use_ssl else 'SMTP + STARTTLS'}")

    smtp = None
    try:
        ctx = ssl.create_default_context()
        if use_ssl:
            smtp = smtplib.SMTP_SSL(args.host, args.port, context=ctx, timeout=30)
        else:
            smtp = smtplib.SMTP(args.host, args.port, timeout=30)

        if args.debug:
            smtp.set_debuglevel(2)

        code, msg = smtp.ehlo()
        ok(f"EHLO -> {code} {msg.decode('utf-8', errors='replace')[:120]}")

        if not use_ssl:
            try:
                smtp.starttls(context=ctx)
                ok("STARTTLS upgrade successful")
                code, msg = smtp.ehlo()
                ok(f"EHLO after STARTTLS -> {code}")
            except Exception as e:
                fail(f"STARTTLS failed: {e}")
                smtp.quit()
                return 1
    except smtplib.SMTPServerDisconnected as e:
        fail(f"Server disconnected during handshake: {e}")
        info("This is the 'Connection unexpectedly closed' you reported.")
        info("Most likely causes:")
        info("  1. Wrong port for the protocol "
             "(QQ uses 465 for SSL, 587 for STARTTLS)")
        info("  2. ISP / firewall sniffing SMTP and dropping it")
        info("  3. QQ Mail SMTP service not enabled in your account")
        info("Try: --port 587 (STARTTLS) or --port 465 (SSL).")
        return 1
    except (ssl.SSLError, socket.timeout, OSError) as e:
        fail(f"SMTP handshake failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 1

    # ── Step 4: AUTH ──────────────────────────────────────────────
    step(4, "AUTH login")
    try:
        smtp.login(args.user, args.password)
        ok(f"Login OK as {args.user}")
    except smtplib.SMTPAuthenticationError as e:
        fail(f"Auth failed: {e.smtp_code} {e.smtp_error.decode('utf-8', errors='replace')}")
        info("Most likely cause:")
        info("  - QQ_EMAIL_PASSWORD must be the AUTHORIZATION CODE,")
        info("    not your QQ login password.")
        info("  - Get one at https://mail.qq.com -> Settings -> Account")
        info("    -> POP3/IMAP/SMTP -> Generate authorization code")
        smtp.quit()
        return 1
    except Exception as e:
        fail(f"Auth error: {type(e).__name__}: {e}")
        traceback.print_exc()
        smtp.quit()
        return 1

    # ── Step 5: Send a tiny test message ──────────────────────────
    step(5, f"Send test email to {to_addr}")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[SMTP Test] QQ Mail diagnostic"
    msg["From"] = formataddr(("AI Investment Diagnostic", args.user))
    msg["To"] = to_addr

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = (
        f"This is an SMTP diagnostic test from the AI Investment Research project.\n\n"
        f"If you received this, the QQ Mail SMTP path is working correctly.\n"
        f"Timestamp: {timestamp}\n"
    )
    html = (
        f"<html><body style='font-family:sans-serif;'>"
        f"<h2 style='color:#16a34a;'>SMTP test passed</h2>"
        f"<p>This is an SMTP diagnostic test from the AI Investment Research project.</p>"
        f"<p>If you received this, the QQ Mail SMTP path is working correctly.</p>"
        f"<p><b>Timestamp:</b> {timestamp}</p>"
        f"</body></html>"
    )
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        result = smtp.sendmail(args.user, [to_addr], msg.as_string())
        if result:
            fail(f"Some recipients refused: {result}")
        else:
            ok("sendmail returned no errors")
    except smtplib.SMTPRecipientsRefused as e:
        fail(f"Recipient refused: {e.recipients}")
        smtp.quit()
        return 1
    except smtplib.SMTPDataError as e:
        fail(f"Data error: {e.smtp_code} {e.smtp_error}")
        smtp.quit()
        return 1
    except smtplib.SMTPServerDisconnected as e:
        fail(f"Server disconnected during DATA phase: {e}")
        info("Some servers (especially QQ) close the connection if the")
        info("From: header doesn't match the authenticated account, or if")
        info("the message body trips a spam filter. Verify QQ_EMAIL == sender.")
        return 1

    try:
        smtp.quit()
        ok("QUIT successful")
    except Exception:
        pass

    print()
    print("=" * 70)
    print(" SUCCESS — check the inbox of:", to_addr)
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
