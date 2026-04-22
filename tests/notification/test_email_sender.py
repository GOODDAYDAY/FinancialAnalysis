"""Tests for QQ email sender (no real SMTP send)."""

from backend.notification.email_sender import EmailConfig, send_email


class TestEmailConfig:
    """Configuration validation."""

    def test_default_smtp_settings(self):
        """Default SMTP host should be QQ Mail."""
        cfg = EmailConfig()
        assert cfg.smtp_host == "smtp.qq.com"
        assert cfg.smtp_port == 465

    def test_invalid_when_email_missing(self):
        """Empty sender email should fail validation."""
        cfg = EmailConfig(sender_email="", sender_password="pwd", recipients=["a@qq.com"])
        valid, msg = cfg.is_valid()
        assert not valid
        assert "QQ_EMAIL" in msg

    def test_invalid_when_password_missing(self):
        """Empty password should fail validation."""
        cfg = EmailConfig(sender_email="a@qq.com", sender_password="", recipients=["b@qq.com"])
        valid, msg = cfg.is_valid()
        assert not valid
        assert "PASSWORD" in msg

    def test_invalid_when_no_recipients(self):
        """Empty recipients should fail validation."""
        cfg = EmailConfig(sender_email="a@qq.com", sender_password="pwd", recipients=[])
        valid, msg = cfg.is_valid()
        assert not valid
        assert "RECIPIENTS" in msg

    def test_valid_complete_config(self):
        cfg = EmailConfig(
            sender_email="a@qq.com",
            sender_password="abcd1234",
            recipients=["b@qq.com"],
        )
        valid, msg = cfg.is_valid()
        assert valid

    def test_from_env_parses_recipients(self, monkeypatch):
        """Comma-separated recipients should split correctly."""
        monkeypatch.setenv("QQ_EMAIL_RECIPIENTS", "a@qq.com, b@qq.com,c@qq.com")
        cfg = EmailConfig.from_env()
        assert len(cfg.recipients) == 3
        assert cfg.recipients[0] == "a@qq.com"
        assert cfg.recipients[2] == "c@qq.com"


class TestSendEmail:
    """Send email error paths (no real SMTP)."""

    def test_send_fails_with_invalid_config(self, monkeypatch):
        """Send should return False when config is invalid."""
        cfg = EmailConfig(sender_email="", sender_password="", recipients=[])
        success, msg = send_email("Test", "<p>Body</p>", config=cfg)
        assert not success
        assert msg
