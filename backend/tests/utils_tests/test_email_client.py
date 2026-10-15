"""Tests for invitation email delivery over SMTP and Resend."""

import ssl
from collections.abc import Iterator
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from app.config import settings
from app.utils import email_client
from app.utils.email_client import send_invitation_email

INVITE_URL = "https://portal.example.com/accept-invite?token=abc"


@pytest.fixture
def email_settings() -> Iterator[None]:
    with (
        patch.object(settings, "email_from_address", "invites@example.com"),
        patch.object(settings, "email_from_name", "Open Wearables"),
        patch.object(settings, "resend_api_key", None),
        patch.object(settings, "smtp_host", None),
        patch.object(settings, "smtp_port", 587),
        patch.object(settings, "smtp_username", None),
        patch.object(settings, "smtp_password", None),
        patch.object(settings, "smtp_security", "starttls"),
    ):
        yield


@pytest.mark.usefixtures("email_settings")
class TestSendInvitationEmail:
    def test_not_configured_skips_send(self) -> None:
        with (
            patch.object(email_client.smtplib, "SMTP") as smtp,
            patch.object(email_client.resend.Emails, "send") as resend_send,
        ):
            assert send_invitation_email("dev@example.com", INVITE_URL) is False
        smtp.assert_not_called()
        resend_send.assert_not_called()

    def test_resend_used_when_only_api_key_set(self) -> None:
        with (
            patch.object(settings, "resend_api_key", SecretStr("re_test")),
            patch.object(email_client.smtplib, "SMTP") as smtp,
            patch.object(email_client.resend.Emails, "send", return_value={"id": "1"}) as resend_send,
        ):
            assert send_invitation_email("dev@example.com", INVITE_URL) is True

        smtp.assert_not_called()
        params = resend_send.call_args.args[0]
        assert params["from"] == "Open Wearables <invites@example.com>"
        assert params["to"] == ["dev@example.com"]
        assert INVITE_URL in params["html"]
        assert INVITE_URL in params["text"]

    def test_smtp_takes_precedence_over_resend(self) -> None:
        with (
            patch.object(settings, "resend_api_key", SecretStr("re_test")),
            patch.object(settings, "smtp_host", "smtp.example.com"),
            patch.object(email_client.smtplib, "SMTP") as smtp,
            patch.object(email_client.resend.Emails, "send") as resend_send,
        ):
            assert send_invitation_email("dev@example.com", INVITE_URL) is True

        smtp.assert_called_once()
        resend_send.assert_not_called()

    def test_smtp_starttls_with_login(self) -> None:
        with (
            patch.object(settings, "smtp_host", "smtp.example.com"),
            patch.object(settings, "smtp_username", "user"),
            patch.object(settings, "smtp_password", SecretStr("pass")),
            patch.object(email_client.smtplib, "SMTP") as smtp,
        ):
            assert send_invitation_email("dev@example.com", INVITE_URL, invited_by_email="admin@example.com") is True

        smtp.assert_called_once_with("smtp.example.com", 587, timeout=email_client.SMTP_TIMEOUT_SECONDS)
        server = smtp.return_value
        context = server.starttls.call_args.kwargs["context"]
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True
        server.login.assert_called_once_with("user", "pass")

        msg: EmailMessage = server.send_message.call_args.args[0]
        assert msg["From"] == "Open Wearables <invites@example.com>"
        assert msg["To"] == "dev@example.com"
        html_part = msg.get_body(preferencelist=("html",))
        assert html_part is not None
        html = html_part.get_content()
        assert INVITE_URL in html
        assert "admin@example.com" in html

        text_part = msg.get_body(preferencelist=("plain",))
        assert text_part is not None
        assert INVITE_URL in text_part.get_content()

    def test_from_name_with_special_characters_is_not_html_escaped(self) -> None:
        with (
            patch.object(settings, "email_from_name", "R&D, Acme"),
            patch.object(settings, "smtp_host", "smtp.example.com"),
            patch.object(email_client.smtplib, "SMTP") as smtp,
        ):
            assert send_invitation_email("dev@example.com", INVITE_URL) is True

        msg: EmailMessage = smtp.return_value.send_message.call_args.args[0]
        assert msg["From"] == '"R&D, Acme" <invites@example.com>'
        assert msg["Subject"] == "You've been invited to join R&D, Acme"

    def test_smtp_ssl_uses_implicit_tls(self) -> None:
        with (
            patch.object(settings, "smtp_host", "smtp.example.com"),
            patch.object(settings, "smtp_port", 465),
            patch.object(settings, "smtp_security", "ssl"),
            patch.object(email_client.smtplib, "SMTP") as smtp,
            patch.object(email_client.smtplib, "SMTP_SSL") as smtp_ssl,
        ):
            assert send_invitation_email("dev@example.com", INVITE_URL) is True

        smtp.assert_not_called()
        assert smtp_ssl.call_args.args == ("smtp.example.com", 465)
        context = smtp_ssl.call_args.kwargs["context"]
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True
        smtp_ssl.return_value.starttls.assert_not_called()

    def test_smtp_none_without_credentials_skips_tls_and_login(self) -> None:
        with (
            patch.object(settings, "smtp_host", "localhost"),
            patch.object(settings, "smtp_port", 1025),
            patch.object(settings, "smtp_security", "none"),
            patch.object(email_client.smtplib, "SMTP") as smtp,
        ):
            assert send_invitation_email("dev@example.com", INVITE_URL) is True

        server = smtp.return_value
        server.starttls.assert_not_called()
        server.login.assert_not_called()
        server.send_message.assert_called_once()

    def test_smtp_none_with_credentials_skips_send(self) -> None:
        with (
            patch.object(settings, "smtp_host", "smtp.example.com"),
            patch.object(settings, "smtp_security", "none"),
            patch.object(settings, "smtp_username", "user"),
            patch.object(settings, "smtp_password", SecretStr("pass")),
            patch.object(email_client.smtplib, "SMTP") as smtp,
        ):
            assert send_invitation_email("dev@example.com", INVITE_URL) is False

        smtp.assert_not_called()

    def test_smtp_error_returns_false(self) -> None:
        smtp = MagicMock(side_effect=OSError("connection refused"))
        with (
            patch.object(settings, "smtp_host", "smtp.example.com"),
            patch.object(email_client.smtplib, "SMTP", smtp),
        ):
            assert send_invitation_email("dev@example.com", INVITE_URL) is False
