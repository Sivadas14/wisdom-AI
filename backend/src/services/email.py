"""
Email service for sending OTP codes and password reset links.
Uses Python's smtplib with configurable SMTP settings.
Supports Gmail SMTP, AWS SES SMTP, or any SMTP provider.
"""

import smtplib
import secrets
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from tuneapi import tu

from src.settings import settings


def generate_otp(length: int = 6) -> str:
    """Generate a random numeric OTP code."""
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_reset_token() -> str:
    """Generate a secure random token for password reset."""
    return secrets.token_urlsafe(32)


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email using SMTP. Returns True on success, False on failure."""
    if not settings.smtp_host or not settings.smtp_username:
        tu.logger.error("SMTP not configured — cannot send email")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_sender_name} <{settings.smtp_sender_email}>"
    msg["To"] = to_email

    # Plain text fallback
    plain_text = html_body.replace("<br>", "\n").replace("<br/>", "\n")
    # Strip HTML tags for plain text
    import re
    plain_text = re.sub(r"<[^>]+>", "", plain_text)

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port)

        server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.smtp_sender_email, to_email, msg.as_string())
        server.quit()
        tu.logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        tu.logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_verification_otp(to_email: str, otp_code: str, name: str = "") -> bool:
    """Send an email verification OTP to a user."""
    greeting = f"Hi {name}," if name else "Hi,"
    subject = f"Your verification code: {otp_code}"
    html_body = f"""
    <div style="font-family: 'Georgia', serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #8B4513; font-size: 28px; margin: 0;">Arunachala Samudra</h1>
            <p style="color: #666; font-size: 14px; margin-top: 5px;">Contemplation Flow</p>
        </div>

        <div style="background: #fff; border-radius: 12px; padding: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.08);">
            <p style="color: #333; font-size: 16px; line-height: 1.6;">{greeting}</p>
            <p style="color: #333; font-size: 16px; line-height: 1.6;">
                Welcome! Please verify your email address by entering this code:
            </p>

            <div style="text-align: center; margin: 30px 0;">
                <div style="display: inline-block; background: #FFF3E0; border: 2px solid #E65100; border-radius: 10px; padding: 20px 40px;">
                    <span style="font-size: 36px; letter-spacing: 8px; color: #E65100; font-weight: bold;">{otp_code}</span>
                </div>
            </div>

            <p style="color: #666; font-size: 14px; line-height: 1.6;">
                This code expires in <strong>10 minutes</strong>. If you didn't create an account, please ignore this email.
            </p>
        </div>

        <p style="text-align: center; color: #999; font-size: 12px; margin-top: 30px;">
            &copy; Arunachala Samudra. All rights reserved.
        </p>
    </div>
    """
    return _send_email(to_email, subject, html_body)


def send_password_reset_otp(to_email: str, otp_code: str, name: str = "") -> bool:
    """Send a password reset OTP to a user."""
    greeting = f"Hi {name}," if name else "Hi,"
    subject = f"Password reset code: {otp_code}"
    html_body = f"""
    <div style="font-family: 'Georgia', serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #8B4513; font-size: 28px; margin: 0;">Arunachala Samudra</h1>
            <p style="color: #666; font-size: 14px; margin-top: 5px;">Contemplation Flow</p>
        </div>

        <div style="background: #fff; border-radius: 12px; padding: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.08);">
            <p style="color: #333; font-size: 16px; line-height: 1.6;">{greeting}</p>
            <p style="color: #333; font-size: 16px; line-height: 1.6;">
                We received a request to reset your password. Use this code to proceed:
            </p>

            <div style="text-align: center; margin: 30px 0;">
                <div style="display: inline-block; background: #FFF3E0; border: 2px solid #E65100; border-radius: 10px; padding: 20px 40px;">
                    <span style="font-size: 36px; letter-spacing: 8px; color: #E65100; font-weight: bold;">{otp_code}</span>
                </div>
            </div>

            <p style="color: #666; font-size: 14px; line-height: 1.6;">
                This code expires in <strong>10 minutes</strong>. If you didn't request a password reset, please ignore this email — your password will remain unchanged.
            </p>
        </div>

        <p style="text-align: center; color: #999; font-size: 12px; margin-top: 30px;">
            &copy; Arunachala Samudra. All rights reserved.
        </p>
    </div>
    """
    return _send_email(to_email, subject, html_body)
