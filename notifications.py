"""
notifications.py - Email and SMS notification engine
Smart Attendance System with Facial Recognition

Supports:
  - Email via smtplib (Gmail, Outlook, or any SMTP server)
  - SMS via Twilio (requires Twilio account + phone number)

Notifications are sent in background threads so they never
block the main attendance-marking flow.
"""

import smtplib
import logging
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════
#   NOTIFICATION SETTINGS  (loaded from DB settings, not hardcoded)
# ════════════════════════════════════════════════════════════════════════

# These are set at runtime by load_notification_settings()
_email_cfg: dict = {}
_sms_cfg:   dict = {}


def load_notification_settings(settings: dict):
    """
    Load notification credentials into module-level config.

    Called by app.py on startup and after the user saves Settings.

    Args:
        settings: dict from database.get_notification_settings()
    """
    global _email_cfg, _sms_cfg

    _email_cfg = {
        "enabled":      settings.get("email_enabled", False),
        "smtp_host":    settings.get("smtp_host", "smtp.gmail.com"),
        "smtp_port":    int(settings.get("smtp_port", 587)),
        "sender_email": settings.get("sender_email", ""),
        "sender_pass":  settings.get("sender_pass", ""),
        "recipient":    settings.get("recipient_email", ""),
    }

    _sms_cfg = {
        "enabled":        settings.get("sms_enabled", False),
        "account_sid":    settings.get("twilio_sid", ""),
        "auth_token":     settings.get("twilio_token", ""),
        "from_number":    settings.get("twilio_from", ""),
        "to_number":      settings.get("twilio_to", ""),
    }

    logger.info(
        "Notifications loaded — Email: %s | SMS: %s",
        "ON" if _email_cfg["enabled"] else "OFF",
        "ON" if _sms_cfg["enabled"]   else "OFF",
    )


# ════════════════════════════════════════════════════════════════════════
#   EMAIL (smtplib)
# ════════════════════════════════════════════════════════════════════════

def _build_email_html(name: str, user_id: str, dept: str, timestamp: str) -> str:
    """Build a styled HTML email body for the attendance notification."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8"/>
      <style>
        body {{ font-family: 'Inter', Arial, sans-serif; background: #0d0f14; margin: 0; padding: 24px; }}
        .card {{
          background: #181c26; border-radius: 12px; padding: 32px;
          max-width: 480px; margin: 0 auto; border: 1px solid #252a38;
        }}
        .header {{ text-align: center; margin-bottom: 24px; }}
        .icon {{ font-size: 48px; }}
        h1 {{ color: #e8eaf0; font-size: 1.4rem; margin: 8px 0 4px; }}
        .subtitle {{ color: #8892a4; font-size: 0.9rem; }}
        .info-row {{
          display: flex; justify-content: space-between; align-items: center;
          padding: 12px 0; border-bottom: 1px solid #252a38;
        }}
        .info-row:last-child {{ border-bottom: none; }}
        .label {{ color: #8892a4; font-size: 0.85rem; }}
        .value {{ color: #e8eaf0; font-weight: 600; font-size: 0.95rem; }}
        .badge {{
          background: rgba(34,197,94,0.15); color: #22c55e;
          padding: 4px 14px; border-radius: 20px; font-size: 0.8rem; font-weight: 700;
        }}
        .footer {{ margin-top: 24px; text-align: center; color: #555f72; font-size: 0.78rem; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <div class="icon">✅</div>
          <h1>Attendance Marked</h1>
          <p class="subtitle">FaceAttend Smart Attendance System</p>
        </div>
        <div class="info-row">
          <span class="label">Name</span>
          <span class="value">{name}</span>
        </div>
        <div class="info-row">
          <span class="label">ID</span>
          <span class="value">{user_id}</span>
        </div>
        <div class="info-row">
          <span class="label">Department</span>
          <span class="value">{dept or 'N/A'}</span>
        </div>
        <div class="info-row">
          <span class="label">Date &amp; Time</span>
          <span class="value">{timestamp}</span>
        </div>
        <div class="info-row">
          <span class="label">Status</span>
          <span class="badge">Present</span>
        </div>
        <p class="footer">This is an automated message from FaceAttend. Do not reply.</p>
      </div>
    </body>
    </html>
    """


def send_email_notification(name: str, user_id: str, dept: str,
                            timestamp: str) -> dict:
    """
    Send an attendance email notification via SMTP.

    Args:
        name:      Student/employee name
        user_id:   Unique ID
        dept:      Department/class
        timestamp: Formatted date + time string

    Returns:
        dict with 'success' (bool) and 'message' (str)
    """
    cfg = _email_cfg
    if not cfg.get("enabled"):
        return {"success": False, "message": "Email notifications disabled"}

    required = ["smtp_host", "smtp_port", "sender_email", "sender_pass", "recipient"]
    missing  = [k for k in required if not cfg.get(k)]
    if missing:
        return {"success": False, "message": f"Missing email config: {missing}"}

    try:
        # Build MIME message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✅ Attendance Marked — {name} ({user_id})"
        msg["From"]    = cfg["sender_email"]
        msg["To"]      = cfg["recipient"]

        # Plain text fallback
        plain_body = (
            f"Attendance Notification\n\n"
            f"Name:      {name}\n"
            f"ID:        {user_id}\n"
            f"Dept:      {dept or 'N/A'}\n"
            f"Timestamp: {timestamp}\n"
            f"Status:    Present\n\n"
            f"-- FaceAttend System"
        )
        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(_build_email_html(name, user_id, dept, timestamp), "html"))

        # Connect and send
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=10) as server:
            server.ehlo()
            server.starttls()          # Upgrade to TLS
            server.login(cfg["sender_email"], cfg["sender_pass"])
            server.sendmail(cfg["sender_email"], cfg["recipient"], msg.as_string())

        logger.info("Email sent to %s for %s (%s)", cfg["recipient"], name, user_id)
        return {"success": True, "message": f"Email sent to {cfg['recipient']}"}

    except smtplib.SMTPAuthenticationError:
        msg = "Email auth failed. Check sender email & app password."
        logger.error(msg)
        return {"success": False, "message": msg}
    except smtplib.SMTPException as e:
        logger.error("SMTP error: %s", e)
        return {"success": False, "message": f"SMTP error: {e}"}
    except Exception as e:
        logger.error("Email send error: %s", e)
        return {"success": False, "message": str(e)}


# ════════════════════════════════════════════════════════════════════════
#   SMS (Twilio)
# ════════════════════════════════════════════════════════════════════════

def send_sms_notification(name: str, user_id: str, timestamp: str) -> dict:
    """
    Send an attendance SMS notification via Twilio.

    Args:
        name:      Student/employee name
        user_id:   Unique ID
        timestamp: Formatted date + time string

    Returns:
        dict with 'success' (bool) and 'message' (str)
    """
    cfg = _sms_cfg
    if not cfg.get("enabled"):
        return {"success": False, "message": "SMS notifications disabled"}

    required = ["account_sid", "auth_token", "from_number", "to_number"]
    missing  = [k for k in required if not cfg.get(k)]
    if missing:
        return {"success": False, "message": f"Missing SMS config: {missing}"}

    try:
        # Import Twilio only when SMS is actually used
        from twilio.rest import Client

        body = (
            f"✅ FaceAttend: Attendance marked!\n"
            f"Name: {name}\n"
            f"ID:   {user_id}\n"
            f"Time: {timestamp}\n"
            f"Status: Present"
        )

        client = Client(cfg["account_sid"], cfg["auth_token"])
        msg    = client.messages.create(
            body=body,
            from_=cfg["from_number"],
            to=cfg["to_number"],
        )

        logger.info("SMS sent (SID: %s) for %s (%s)", msg.sid, name, user_id)
        return {"success": True, "message": f"SMS sent (SID: {msg.sid})"}

    except ImportError:
        return {
            "success": False,
            "message": "Twilio not installed. Run: pip install twilio"
        }
    except Exception as e:
        logger.error("SMS send error: %s", e)
        return {"success": False, "message": str(e)}


# ════════════════════════════════════════════════════════════════════════
#   COMBINED DISPATCHER  (fire-and-forget via background thread)
# ════════════════════════════════════════════════════════════════════════

def notify_attendance(name: str, user_id: str, dept: str = "") -> None:
    """
    Fire email AND SMS notifications in a background thread.

    This function returns immediately — notifications are sent
    asynchronously so they never delay the HTTP response.

    Args:
        name:    Recognized person's name
        user_id: Their unique ID
        dept:    Department/class (optional, used in email)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

    def _send():
        # Send email
        if _email_cfg.get("enabled"):
            result = send_email_notification(name, user_id, dept, timestamp)
            logger.info("Email result: %s", result["message"])

        # Send SMS
        if _sms_cfg.get("enabled"):
            result = send_sms_notification(name, user_id, timestamp)
            logger.info("SMS result: %s", result["message"])

    # Daemon thread — won't block app shutdown
    t = threading.Thread(target=_send, daemon=True)
    t.start()


def test_email(cfg_override: Optional[dict] = None) -> dict:
    """
    Send a test email using current (or overridden) config.
    Used from the Settings page to verify credentials.
    """
    original = dict(_email_cfg)
    if cfg_override:
        _email_cfg.update(cfg_override)

    result = send_email_notification(
        name="Test User", user_id="TEST001",
        dept="Testing", timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    _email_cfg.clear()
    _email_cfg.update(original)
    return result


def test_sms(cfg_override: Optional[dict] = None) -> dict:
    """
    Send a test SMS using current (or overridden) config.
    Used from the Settings page to verify credentials.
    """
    original = dict(_sms_cfg)
    if cfg_override:
        _sms_cfg.update(cfg_override)

    result = send_sms_notification(
        name="Test User", user_id="TEST001",
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    _sms_cfg.clear()
    _sms_cfg.update(original)
    return result
