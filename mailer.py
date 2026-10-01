"""Shared SMTP sending for the alert scripts.

Env vars:
  SMTP_USER      Gmail address that sends the email
  SMTP_PASSWORD  Gmail app password (https://myaccount.google.com/apppasswords)
  ALERT_TO       recipient (defaults to SMTP_USER)
  SMTP_HOST / SMTP_PORT  optional, default smtp.gmail.com:465
"""
import os
import re
import smtplib
from email.message import EmailMessage


def send_email(subject, text, body):
    # Secrets pasted into GitHub often pick up stray spaces or newlines
    user = os.environ["SMTP_USER"].strip()
    password = re.sub(r"\s", "", os.environ["SMTP_PASSWORD"])
    if not user or not password:
        raise RuntimeError("SMTP_USER or SMTP_PASSWORD is empty")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = (os.environ.get("ALERT_TO") or user).strip()
    msg.set_content(text)
    msg.add_alternative(body, subtype="html")
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    try:
        with smtplib.SMTP_SSL(host, port, timeout=30) as s:
            s.login(user, password)
            s.send_message(msg)
    except smtplib.SMTPServerDisconnected:
        print(f"{host}:{port} dropped the connection, retrying with STARTTLS on 587")
        with smtplib.SMTP(host, 587, timeout=30) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
