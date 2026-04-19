"""
Send the daily health monitor report via Gmail.
Called by .github/workflows/daily-monitor.yml after monitor.py runs.

Environment variables required:
  GMAIL_USER         - sender address (dassiv67@gmail.com)
  GMAIL_APP_PASSWORD - Gmail App Password (from GitHub secret)
  RECIPIENT          - destination address
  MONITOR_EXIT       - "0" (pass) or "1" (fail)
  MONITOR_OUTPUT     - path to the monitor output file
"""

import os
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── Config ────────────────────────────────────────────────────────────────────

gmail_user   = os.environ["GMAIL_USER"]
app_password = os.environ["GMAIL_APP_PASSWORD"]
recipient    = os.environ["RECIPIENT"]
exit_code    = os.environ.get("MONITOR_EXIT", "1")
output_file  = os.environ.get("MONITOR_OUTPUT", "/tmp/monitor_output.txt")

# ── Read monitor output ───────────────────────────────────────────────────────

try:
    with open(output_file) as f:
        body = f.read()
except Exception as e:
    body = f"(monitor output not available: {e})"

# ── Build email ───────────────────────────────────────────────────────────────

status = "ALL SYSTEMS OK" if exit_code == "0" else "ISSUES FOUND"
icon   = "OK" if exit_code == "0" else "FAIL"
now    = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")

subject = f"[Arunachala Samudra] Daily Health — {icon} — {now}"

divider = "=" * 60
text = "\n".join([
    "Daily Health Monitor Report",
    now,
    "",
    f"Status: {status}",
    "",
    divider,
    body,
    divider,
    "",
    "Quick links:",
    "  App:        https://www.arunachalasamudra.co.in",
    "  Health:     https://www.arunachalasamudra.co.in/health",
    "  App Runner: https://console.aws.amazon.com/apprunner",
])

msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"]    = gmail_user
msg["To"]      = recipient
msg.attach(MIMEText(text, "plain"))

# ── Send ──────────────────────────────────────────────────────────────────────

ctx = ssl.create_default_context()
try:
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ctx)
        smtp.login(gmail_user, app_password)
        smtp.sendmail(gmail_user, recipient, msg.as_string())
    print(f"Email sent to {recipient} — {subject}")
except Exception as e:
    print(f"ERROR: Failed to send email: {e}", file=sys.stderr)
    sys.exit(1)
