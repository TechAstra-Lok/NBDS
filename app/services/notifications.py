import logging
from app import db
from app.models import Notification, NotificationDeliveryLog

logger = logging.getLogger(__name__)

class NotificationProvider:
    """Base interface for all notification channels."""
    def send(self, donor, title, message, request_id=None):
        raise NotImplementedError("Providers must implement send()")

class EmailProvider(NotificationProvider):
    def send(self, donor, title, message, request_id=None):
        if not donor.email:
            return False, "Donor has no email address"
        
        # MOCK IMPLEMENTATION
        # In a real app, you would use Flask-Mail or an API like SendGrid here.
        try:
            logger.info(f"[EMAIL] Sending to {donor.email}: {title}")
            return True, "Mock email sent successfully"
        except Exception as e:
            logger.error(f"[EMAIL] Failed to send email to {donor.email}: {e}")
            return False, str(e)

class SMSProvider(NotificationProvider):
    def send(self, donor, title, message, request_id=None):
        if not donor.phone1:
            return False, "Donor has no primary phone number"
        
        # MOCK IMPLEMENTATION
        # In a real app in Nepal, integrate with Sparrow SMS, Aakash SMS, etc.
        try:
            logger.info(f"[SMS] Sending to +977-{donor.phone1}: {title}")
            return True, "Mock SMS sent successfully"
        except Exception as e:
            logger.error(f"[SMS] Failed to send SMS to +977-{donor.phone1}: {e}")
            return False, str(e)

class InAppProvider(NotificationProvider):
    def send(self, donor, title, message, request_id=None):
        # We don't need to do anything here because the generic dispatcher
        # always creates the Notification record in the DB anyway.
        # This is just a placeholder if we wanted to push real-time web sockets (e.g. Socket.io).
        logger.info(f"[IN-APP] Notification generated for donor {donor.id}")
        return True, "In-app notification generated"


class NotificationDispatcher:
    """Orchestrates sending alerts to a donor across all opted-in channels."""
    
    def __init__(self):
        self.providers = {
            'email': EmailProvider(),
            'sms': SMSProvider(),
            'in_app': InAppProvider(),
        }

    def dispatch(self, donor, title, message, category='alert', request_id=None):
        """
        Send a notification to a donor based on their preferences.
        Avoids duplicates if this request_id has already been alerted to this donor.
        """
        # 1. Duplicate check
        if request_id:
            existing = Notification.query.filter_by(
                donor_id=donor.id, 
                blood_request_id=request_id
            ).first()
            if existing:
                logger.info(f"Notification already sent to Donor {donor.id} for Request {request_id}")
                return False

        # 2. Check Preferences
        pref = donor.preference
        # If no preference record exists, default to True for all.
        channels_to_send = []
        if not pref or pref.in_app_alerts:
            channels_to_send.append('in_app')
        if not pref or pref.email_alerts:
            channels_to_send.append('email')
        if not pref or pref.sms_alerts:
            channels_to_send.append('sms')

        if not channels_to_send:
            logger.info(f"Donor {donor.id} has opted out of all notifications.")
            return False

        # 3. Create Core DB Notification
        notif = Notification(
            donor_id=donor.id,
            blood_request_id=request_id,
            title=title,
            message=message,
            category=category,
            channel=','.join(channels_to_send) # store combined preference
        )
        db.session.add(notif)
        db.session.flush() # flush to get notif.id

        # 4. Dispatch and Log Delivery for each channel
        for channel in channels_to_send:
            provider = self.providers.get(channel)
            if not provider:
                continue
                
            success, error_msg = provider.send(donor, title, message, request_id)
            status = 'sent' if success else 'failed'
            
            log = NotificationDeliveryLog(
                notification_id=notif.id,
                channel=channel,
                status=status,
                error_message=error_msg if not success else None,
                attempt_count=1
            )
            db.session.add(log)
            
        return True
