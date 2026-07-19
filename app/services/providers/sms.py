"""
SMS Notification Provider
Supports: Mock (dev), Sparrow SMS Nepal, and Twilio.
"""
import logging
import requests
from flask import current_app
from .base import NotificationProvider

logger = logging.getLogger(__name__)

_SMS_TEMPLATE = (
    "\U0001f9b8 Blood Request Alert\n"
    "Blood Group: {blood_group}\n"
    "Hospital: {hospital}\n"
    "Patient: {patient_name}\n"
    "Contact: {contact_number}\n"
    "Request ID: {request_id}\n"
    "View: {request_url}"
)


def _build_sms_body(title, message, payload):
    p = payload or {}
    try:
        return _SMS_TEMPLATE.format(
            blood_group=p.get('blood_group', ''),
            hospital=p.get('hospital', ''),
            patient_name=p.get('patient_name', ''),
            contact_number=p.get('contact_number', ''),
            request_id=p.get('request_id', ''),
            request_url=p.get('request_url', ''),
        )
    except Exception:
        return f"{title}\n{message}"


class MockSMSProvider(NotificationProvider):
    """Development mock — logs to console, no actual sending."""

    def send(self, donor, title, message, payload=None, request_id=None):
        if not donor.phone1:
            return False, "Donor has no primary phone number", None
        body = _build_sms_body(title, message, payload)
        self.logger.info("[SMS-MOCK] To: +977-%s | Body: %s", donor.phone1, body[:60])
        return True, None, "mock-sms-id-001"


class SparrowSMSProvider(NotificationProvider):
    """Sparrow SMS Nepal integration."""

    API_URL = "http://api.sparrowsms.com/v2/sms/"

    def send(self, donor, title, message, payload=None, request_id=None):
        if not donor.phone1:
            return False, "Donor has no primary phone number", None

        try:
            token = current_app.config.get('SPARROW_SMS_TOKEN', '')
            sender = current_app.config.get('SPARROW_SMS_SENDER', 'INFO')
            if not token:
                self.logger.warning("[SMS-SPARROW] Token not configured. Falling back to mock.")
                self.logger.info("[SMS-MOCK] To: +977-%s | %s", donor.phone1, title)
                return True, None, "mock-sparrow-fallback"

            body = _build_sms_body(title, message, payload)
            resp = requests.post(
                self.API_URL,
                data={'token': token, 'from': sender, 'to': donor.phone1, 'text': body},
                timeout=10,
            )
            if resp.status_code == 200:
                self.logger.info("[SMS-SPARROW] Sent to %s", donor.phone1)
                return True, None, resp.text[:100]
            self.logger.error("[SMS-SPARROW] HTTP %s: %s", resp.status_code, resp.text)
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}", None

        except Exception as e:
            self.logger.error("[SMS-SPARROW] Failed: %s", e)
            return False, str(e), None


class TwilioSMSProvider(NotificationProvider):
    """Twilio SMS integration."""

    def send(self, donor, title, message, payload=None, request_id=None):
        if not donor.phone1:
            return False, "Donor has no primary phone number", None

        try:
            account_sid = current_app.config.get('TWILIO_ACCOUNT_SID', '')
            auth_token = current_app.config.get('TWILIO_AUTH_TOKEN', '')
            from_number = current_app.config.get('TWILIO_PHONE_NUMBER', '')
            if not account_sid or not auth_token:
                self.logger.warning("[SMS-TWILIO] Credentials not configured. Falling back to mock.")
                return True, None, "mock-twilio-fallback"

            from twilio.rest import Client  # type: ignore
            client = Client(account_sid, auth_token)
            body = _build_sms_body(title, message, payload)
            msg = client.messages.create(
                body=body,
                from_=from_number,
                to=f"+977{donor.phone1}",
            )
            self.logger.info("[SMS-TWILIO] Sent to %s SID=%s", donor.phone1, msg.sid)
            return True, None, msg.sid

        except ImportError:
            self.logger.error("[SMS-TWILIO] twilio package not installed.")
            return False, "twilio package not installed", None
        except Exception as e:
            self.logger.error("[SMS-TWILIO] Failed: %s", e)
            return False, str(e), None


def get_sms_provider():
    """Factory — returns the configured SMS provider."""
    try:
        mode = current_app.config.get('SMS_PROVIDER', 'mock').lower()
    except RuntimeError:
        mode = 'mock'
    if mode == 'sparrow':
        return SparrowSMSProvider()
    if mode == 'twilio':
        return TwilioSMSProvider()
    return MockSMSProvider()
