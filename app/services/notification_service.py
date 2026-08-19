"""
Enterprise Notification Service
====================================
Main entry point for the multi-channel notification system.

Architecture:
  - NotificationService.dispatch_for_request(blood_request)
      → DonorMatchingService.find_eligible_donors()
      → For each donor, create Notification + enqueue delivery jobs
  - Background worker polls NotificationQueue and calls channel providers
"""
import json
import logging
from datetime import datetime, timedelta
from app import db
from app.models import (
    Donor, Notification,
    NotificationDeliveryLog, NotificationQueue,
)
from app.services.donor_matching_service import DonorMatchingService
from app.services.providers.email import get_email_provider
from app.services.providers.sms import get_sms_provider
from app.services.providers.push import WebPushProvider, MobilePushProvider, InAppProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel registry
# ---------------------------------------------------------------------------

CHANNEL_PROVIDER_MAP = {
    'email':       get_email_provider,         # callable → provider instance
    'sms':         get_sms_provider,           # callable → provider instance
    'web_push':    WebPushProvider,            # class
    'mobile_push': MobilePushProvider,         # class
    'in_app':      InAppProvider,              # class
}


def _get_provider(channel):
    factory = CHANNEL_PROVIDER_MAP.get(channel)
    if factory is None:
        return None
    if callable(factory) and not isinstance(factory, type):
        return factory()          # factory function (e.g. get_email_provider())
    return factory()              # class instantiation


# ---------------------------------------------------------------------------
# Preference helpers
# ---------------------------------------------------------------------------

def _channels_for_donor(donor):
    """Return the list of channels the donor wants to receive."""
    pref = getattr(donor, 'preference', None)
    channels = []
    # Always include in-app
    if not pref or pref.in_app_alerts:
        channels.append('in_app')
    if not pref or pref.email_alerts:
        channels.append('email')
    if not pref or pref.sms_alerts:
        channels.append('sms')
    if not pref or getattr(pref, 'web_push_alerts', True):
        channels.append('web_push')
    if not pref or getattr(pref, 'mobile_push_alerts', True):
        channels.append('mobile_push')
    return channels


def _in_quiet_hours(pref):
    """Return True if current time falls within the donor's quiet hours."""
    if not pref:
        return False
    qs = getattr(pref, 'quiet_hours_start', None)
    qe = getattr(pref, 'quiet_hours_end', None)
    if not qs or not qe:
        return False
    now_time = datetime.utcnow().time()
    if qs <= qe:
        return qs <= now_time <= qe
    # Wraps midnight
    return now_time >= qs or now_time <= qe


# ---------------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------------

def _enqueue(notification_id, channel, payload_dict, priority=3):
    """Insert a job into the NotificationQueue."""
    item = NotificationQueue(
        notification_id=notification_id,
        channel=channel,
        payload=json.dumps(payload_dict),
        priority=priority,
        status='queued',
        retry_count=0,
        max_retries=3,
        next_attempt_at=datetime.utcnow(),
    )
    db.session.add(item)


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class NotificationService:
    """
    Orchestrates multi-channel donor notification for blood requests.
    """

    def __init__(self):
        self.matcher = DonorMatchingService()

    def dispatch_for_request(self, blood_request, max_donors=50):
        """
        Find eligible donors for blood_request and queue notifications.
        Returns the number of donors queued.
        """
        if not blood_request:
            return 0

        ranked = self.matcher.find_eligible_donors(blood_request)
        if not ranked:
            logger.info("No eligible donors found for request %s", blood_request.request_id)
            return 0

        title = self._build_title(blood_request)
        priority = 1 if getattr(blood_request, 'is_emergency', False) else 3
        queued = 0

        payload = self._build_payload(blood_request)

        for donor, score, reasons in ranked[:max_donors]:
            pref = getattr(donor, 'preference', None)

            # Skip DND entirely (even in emergencies we respect hard DND)
            if pref and getattr(pref, 'dnd_mode', False):
                continue

            # Build message
            message = self._build_message(blood_request, donor, reasons)

            # Create the core Notification record
            notif = Notification(
                donor_id=donor.id,
                blood_request_id=blood_request.id,
                title=title,
                message=message,
                category='blood_request',
                channel='multi',
            )
            db.session.add(notif)
            db.session.flush()  # get notif.id

            in_quiet = _in_quiet_hours(pref)
            channels = _channels_for_donor(donor)

            for ch in channels:
                # Skip non-emergency channels during quiet hours
                if in_quiet and ch != 'in_app' and not getattr(blood_request, 'is_emergency', False):
                    continue
                _enqueue(notif.id, ch, payload, priority=priority)

            queued += 1

        try:
            db.session.commit()
            logger.info("Queued notifications for %d donors for request %s", queued, blood_request.request_id)
        except Exception as e:
            db.session.rollback()
            logger.error("Failed to queue notifications: %s", e)
            return 0

        return queued

    # ------------------------------------------------------------------
    # Background queue worker (called by APScheduler)
    # ------------------------------------------------------------------

    @staticmethod
    def process_queue(batch_size=20):
        """
        Poll the NotificationQueue and dispatch pending items.
        Called by the APScheduler background job.
        """
        now = datetime.utcnow()
        items = (
            NotificationQueue.query
            .filter(
                NotificationQueue.status == 'queued',
                NotificationQueue.next_attempt_at <= now,
            )
            .order_by(NotificationQueue.priority.asc(), NotificationQueue.next_attempt_at.asc())
            .limit(batch_size)
            .all()
        )

        for item in items:
            item.status = 'processing'
            db.session.flush()

            notif = Notification.query.get(item.notification_id)
            if not notif:
                item.status = 'failed'
                item.error_log = 'Notification record missing'
                continue

            donor = Donor.query.get(notif.donor_id)
            if not donor:
                item.status = 'failed'
                item.error_log = 'Donor record missing'
                continue

            try:
                payload = json.loads(item.payload) if item.payload else {}
            except Exception:
                payload = {}

            provider = _get_provider(item.channel)
            if not provider:
                item.status = 'failed'
                item.error_log = f'Unknown channel: {item.channel}'
                db.session.flush()
                continue

            success, error_msg, provider_id = provider.send(
                donor=donor,
                title=notif.title,
                message=notif.message,
                payload=payload,
                request_id=notif.blood_request_id,
            )

            log = NotificationDeliveryLog(
                notification_id=notif.id,
                channel=item.channel,
                status='sent' if success else 'failed',
                error_message=error_msg,
                attempt_count=(item.retry_count or 0) + 1,
                provider_name=item.channel,
                provider_response_id=provider_id,
            )
            db.session.add(log)

            if success:
                item.status = 'completed'
            else:
                item.retry_count = (item.retry_count or 0) + 1
                if item.retry_count >= item.max_retries:
                    item.status = 'dlq'
                    item.error_log = error_msg
                else:
                    # Exponential backoff: 2^retry minutes
                    backoff_mins = 2 ** item.retry_count
                    item.next_attempt_at = datetime.utcnow() + timedelta(minutes=backoff_mins)
                    item.status = 'queued'

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Queue processing commit failed: %s", e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_title(blood_request):
        emergency = getattr(blood_request, 'is_emergency', False)
        prefix = "\U0001f198 EMERGENCY" if emergency else "\U0001f9b8"
        return f"{prefix} Blood Request: {blood_request.blood_group} — {blood_request.hospital}"

    @staticmethod
    def _build_message(blood_request, donor, reasons):
        location = ', '.join(filter(None, [
            blood_request.local_level,
            blood_request.district,
            blood_request.province,
        ]))
        return (
            f"Patient {blood_request.patient_name} urgently needs {blood_request.blood_group} blood at "
            f"{blood_request.hospital}, {location}. "
            f"Contact: {blood_request.contact_person} ({blood_request.contact_number}). "
            f"Request ID: {blood_request.request_id}."
        )

    @staticmethod
    def _build_payload(blood_request):
        try:
            request_url = f"/blood-request/{blood_request.request_id}"
        except Exception:
            request_url = "#"
        return {
            'patient_name': blood_request.patient_name or '',
            'blood_group': blood_request.blood_group or '',
            'hospital': blood_request.hospital or '',
            'province': blood_request.province or '',
            'district': blood_request.district or '',
            'local_level': blood_request.local_level or '',
            'contact_person': blood_request.contact_person or '',
            'contact_number': blood_request.contact_number or '',
            'urgency': 'Emergency' if getattr(blood_request, 'is_emergency', False) else 'Normal',
            'request_id': blood_request.request_id or '',
            'request_url': request_url,
        }
