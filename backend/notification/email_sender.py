"""
QQ Mail SMTP sender.

QQ Mail SMTP servers:
  - smtp.qq.com:465 (SSL)
  - smtp.qq.com:587 (STARTTLS)

Authentication requires an "Authorization Code" (授权码) generated from
QQ Mail web settings -> Account -> POP3/IMAP/SMTP service.
The regular QQ password will NOT work.

How to get an authorization code:
  1. Open https://mail.qq.com
  2. Settings -> Account
  3. Enable IMAP/SMTP service
  4. Generate authorization code (16 chars)
  5. Use the code as QQ_EMAIL_PASSWORD in .env
"""

import logging
import os
import smtplib
import ssl
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    """SMTP configuration for sending emails."""
    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 465  # SSL
    sender_email: str = ""
    sender_password: str = ""  # QQ authorization code, NOT account password
    sender_name: str = "AI Investment Research"
    recipients: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "EmailConfig":
        """Load config from environment variables."""
        recipients_raw = os.getenv("QQ_EMAIL_RECIPIENTS", "")
        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
        return cls(
            smtp_host=os.getenv("SMTP_HOST", "smtp.qq.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "465")),
            sender_email=os.getenv("QQ_EMAIL", ""),
            sender_password=os.getenv("QQ_EMAIL_PASSWORD", ""),
            sender_name=os.getenv("QQ_EMAIL_SENDER_NAME", "AI Investment Research"),
            recipients=recipients,
        )

    def is_valid(self) -> tuple[bool, str]:
        """Check if config is complete."""
        if not self.sender_email:
            return False, "QQ_EMAIL not set"
        if not self.sender_password:
            return False, "QQ_EMAIL_PASSWORD not set (use authorization code, not account password)"
        if not self.recipients:
            return False, "QQ_EMAIL_RECIPIENTS not set"
        return True, "OK"


def send_email(
    subject: str,
    html_body: str,
    config: EmailConfig | None = None,
    text_body: str | None = None,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """
    Send an email via QQ SMTP.

    Args:
        subject: Email subject line
        html_body: HTML body content
        config: Optional EmailConfig. If None, loads from env.
        text_body: Optional plain-text alternative
        dry_run: If True, validate and build email but do not send.

    Returns:
        (success, message)
    """
    if config is None:
        config = EmailConfig.from_env()

    valid, msg = config.is_valid()
    if not valid:
        logger.error("Email config invalid: %s", msg)
        return False, msg

    # Build multipart email
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = formataddr((config.sender_name, config.sender_email))
    message["To"] = ", ".join(config.recipients)

    if text_body:
        message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    if dry_run:
        logger.info("Dry run — email would be sent to %s with subject '%s'", config.recipients, subject)
        return True, f"[DRY RUN] Would send to {len(config.recipients)} recipient(s)"

    try:
        context = ssl.create_default_context()
        if config.smtp_port == 465:
            # SSL
            with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, context=context, timeout=30) as server:
                server.login(config.sender_email, config.sender_password)
                server.sendmail(config.sender_email, config.recipients, message.as_string())
        else:
            # STARTTLS
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as server:
                server.starttls(context=context)
                server.login(config.sender_email, config.sender_password)
                server.sendmail(config.sender_email, config.recipients, message.as_string())

        logger.info("Email sent successfully to %s", config.recipients)
        return True, f"Sent to {len(config.recipients)} recipient(s)"

    except smtplib.SMTPAuthenticationError as e:
        msg = f"SMTP authentication failed: {e}. Check QQ_EMAIL_PASSWORD (use authorization code)."
        logger.error(msg)
        return False, msg
    except smtplib.SMTPException as e:
        msg = f"SMTP error: {e}"
        logger.error(msg)
        return False, msg
    except Exception as e:
        msg = f"Failed to send email: {e}"
        logger.exception(msg)
        return False, msg
