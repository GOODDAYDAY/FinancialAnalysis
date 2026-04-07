from backend.notification.email_sender import send_email, EmailConfig
from backend.notification.templates import render_analysis_email

__all__ = ["send_email", "EmailConfig", "render_analysis_email"]
