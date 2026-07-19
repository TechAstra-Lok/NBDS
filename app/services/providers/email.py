"""
Email Notification Provider
Supports: Mock (dev), SMTP (Gmail/custom), and future Brevo/SendGrid hooks.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app
from .base import NotificationProvider

logger = logging.getLogger(__name__)


def _build_html_body(donor, title, message, payload):
    """Render a rich HTML email body for blood request alerts."""
    req = payload or {}
    patient = req.get('patient_name', 'Unknown')
    blood_group = req.get('blood_group', '')
    hospital = req.get('hospital', '')
    province = req.get('province', '')
    district = req.get('district', '')
    local_level = req.get('local_level', '')
    contact_person = req.get('contact_person', '')
    contact_number = req.get('contact_number', '')
    urgency = req.get('urgency', 'Normal')
    request_id = req.get('request_id', '')
    request_url = req.get('request_url', '#')
    maps_url = req.get('maps_url', '')

    maps_section = f'<p><a href="{maps_url}" style="color:#1d4ed8;">📍 View on Google Maps</a></p>' if maps_url else ''
    urgency_color = '#DC2626' if urgency.lower() in ('emergency', 'critical') else '#D97706'

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;">
<tr><td align="center" style="padding:32px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,0.08);">
  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#DC2626,#991B1B);padding:28px 32px;text-align:center;">
    <h1 style="color:#fff;margin:0;font-size:22px;">🩸 Nepali Blood Donors Society</h1>
    <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:14px;">Blood Request Alert</p>
  </td></tr>
  <!-- Urgency Badge -->
  <tr><td style="padding:20px 32px 0;">
    <p style="display:inline-block;background:{urgency_color};color:#fff;padding:4px 14px;border-radius:999px;font-size:13px;font-weight:bold;margin:0;">
      {urgency.upper()} REQUEST
    </p>
  </td></tr>
  <!-- Body -->
  <tr><td style="padding:20px 32px;">
    <h2 style="color:#111;margin:0 0 16px;font-size:18px;">{title}</h2>
    <p style="color:#374151;margin:0 0 20px;line-height:1.6;">{message}</p>
    <table width="100%" style="background:#FEF2F2;border-radius:8px;border-left:4px solid #DC2626;">
      <tr><td style="padding:16px 20px;">
        <table width="100%" cellspacing="0" cellpadding="4">
          <tr><td style="color:#6B7280;font-size:13px;width:140px;">Patient</td><td style="color:#111;font-weight:600;">{patient}</td></tr>
          <tr><td style="color:#6B7280;font-size:13px;">Blood Group</td><td style="color:#DC2626;font-weight:700;font-size:18px;">{blood_group}</td></tr>
          <tr><td style="color:#6B7280;font-size:13px;">Hospital</td><td style="color:#111;font-weight:600;">{hospital}</td></tr>
          <tr><td style="color:#6B7280;font-size:13px;">Location</td><td style="color:#111;">{province} &rsaquo; {district} &rsaquo; {local_level}</td></tr>
          <tr><td style="color:#6B7280;font-size:13px;">Contact Person</td><td style="color:#111;">{contact_person}</td></tr>
          <tr><td style="color:#6B7280;font-size:13px;">Contact Number</td><td style="color:#111;font-weight:600;">{contact_number}</td></tr>
          <tr><td style="color:#6B7280;font-size:13px;">Request ID</td><td style="color:#111;font-size:12px;">{request_id}</td></tr>
        </table>
      </td></tr>
    </table>
    {maps_section}
  </td></tr>
  <!-- CTA Buttons -->
  <tr><td style="padding:0 32px 28px;">
    <a href="{request_url}" style="display:inline-block;background:#DC2626;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:bold;font-size:14px;">
      🩸 View Request &amp; Respond
    </a>
  </td></tr>
  <!-- Footer -->
  <tr><td style="background:#F9FAFB;padding:20px 32px;text-align:center;border-top:1px solid #E5E7EB;">
    <p style="color:#9CA3AF;font-size:12px;margin:0;">
      You received this email because you are a registered blood donor on the Nepali Blood Donors Society platform.<br>
      To manage your notification preferences, visit your <a href="#" style="color:#DC2626;">donor dashboard</a>.
    </p>
  </td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""


class MockEmailProvider(NotificationProvider):
    """Development mock — logs to console, no actual sending."""

    def send(self, donor, title, message, payload=None, request_id=None):
        if not donor.email:
            return False, "Donor has no email address", None
        self.logger.info("[EMAIL-MOCK] To: %s | Subject: %s", donor.email, title)
        return True, None, "mock-email-id-001"


class SMTPEmailProvider(NotificationProvider):
    """Production SMTP email provider (Gmail / custom SMTP)."""

    def send(self, donor, title, message, payload=None, request_id=None):
        if not donor.email:
            return False, "Donor has no email address", None

        try:
            smtp_host = current_app.config.get('SMTP_HOST', 'smtp.gmail.com')
            smtp_port = int(current_app.config.get('SMTP_PORT', 587))
            smtp_user = current_app.config.get('SMTP_USER', '')
            smtp_pass = current_app.config.get('SMTP_PASS', '')
            sender = current_app.config.get('MAIL_DEFAULT_SENDER', smtp_user)

            if not smtp_user or not smtp_pass:
                self.logger.warning("[EMAIL-SMTP] SMTP credentials not configured. Falling back to mock.")
                self.logger.info("[EMAIL-MOCK] To: %s | Subject: %s", donor.email, title)
                return True, None, "mock-fallback"

            msg = MIMEMultipart('alternative')
            msg['Subject'] = title
            msg['From'] = sender
            msg['To'] = donor.email

            html_body = _build_html_body(donor, title, message, payload)
            msg.attach(MIMEText(message, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(sender, [donor.email], msg.as_string())

            self.logger.info("[EMAIL-SMTP] Sent to %s", donor.email)
            return True, None, f"smtp-{donor.email}"

        except Exception as e:
            self.logger.error("[EMAIL-SMTP] Failed: %s", e)
            return False, str(e), None


def get_email_provider():
    """Factory — returns the configured email provider."""
    try:
        mode = current_app.config.get('EMAIL_PROVIDER', 'mock').lower()
    except RuntimeError:
        mode = 'mock'
    if mode == 'smtp':
        return SMTPEmailProvider()
    return MockEmailProvider()
