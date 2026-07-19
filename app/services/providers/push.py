"""
Web Push & Mobile Push (FCM) Notification Providers.
"""
import json
import logging
from flask import current_app
from .base import NotificationProvider

logger = logging.getLogger(__name__)


class WebPushProvider(NotificationProvider):
    """
    Browser Web Push using VAPID / pywebpush.
    Falls back to mock if credentials are not configured.
    """

    def send(self, donor, title, message, payload=None, request_id=None):
        try:
            from app.models import PushSubscription
            subs = PushSubscription.query.filter_by(
                donor_id=donor.id, platform='web', is_active=True
            ).all()

            if not subs:
                return False, "No active web push subscriptions", None

            vapid_private = current_app.config.get('VAPID_PRIVATE_KEY', '')
            vapid_claims = {
                "sub": f"mailto:{current_app.config.get('CONTACT_EMAIL', 'info@example.com')}"
            }

            sent_ids = []
            errors = []

            for sub in subs:
                try:
                    if not vapid_private:
                        self.logger.info(
                            "[WEB_PUSH-MOCK] To donor %s subscription %s: %s",
                            donor.id, sub.id, title
                        )
                        sent_ids.append(f"mock-webpush-{sub.id}")
                        continue

                    from pywebpush import webpush, WebPushException  # type: ignore
                    push_payload = json.dumps({
                        "title": title,
                        "body": message,
                        "data": payload or {},
                    })
                    sub_info = {
                        "endpoint": sub.token,
                        "keys": {
                            "auth": sub.auth_key,
                            "p256dh": sub.p256dh_key,
                        },
                    }
                    webpush(
                        subscription_info=sub_info,
                        data=push_payload,
                        vapid_private_key=vapid_private,
                        vapid_claims=vapid_claims,
                    )
                    from datetime import datetime
                    sub.last_used_at = datetime.utcnow()
                    sent_ids.append(sub.token[:30])
                except Exception as e:
                    errors.append(str(e))
                    self.logger.error("[WEB_PUSH] Failed sub %s: %s", sub.id, e)

            if sent_ids:
                return True, None, ",".join(sent_ids[:3])
            return False, "; ".join(errors), None

        except Exception as e:
            self.logger.error("[WEB_PUSH] Provider error: %s", e)
            return False, str(e), None


class MobilePushProvider(NotificationProvider):
    """
    Firebase Cloud Messaging (FCM) for Android/iOS.
    Falls back to mock if not configured.
    """

    def send(self, donor, title, message, payload=None, request_id=None):
        try:
            from app.models import PushSubscription
            subs = PushSubscription.query.filter_by(
                donor_id=donor.id, is_active=True
            ).filter(
                PushSubscription.platform.in_(['android', 'ios'])
            ).all()

            if not subs:
                return False, "No active mobile push subscriptions", None

            fcm_key = current_app.config.get('FCM_SERVER_KEY', '')
            sent_ids = []

            for sub in subs:
                if not fcm_key:
                    self.logger.info(
                        "[FCM-MOCK] To donor %s token=%s…: %s",
                        donor.id, sub.token[:20], title
                    )
                    sent_ids.append(f"mock-fcm-{sub.id}")
                    continue

                try:
                    import requests
                    headers = {
                        'Authorization': f'key={fcm_key}',
                        'Content-Type': 'application/json',
                    }
                    data = {
                        "to": sub.token,
                        "notification": {"title": title, "body": message},
                        "data": payload or {},
                    }
                    resp = requests.post(
                        'https://fcm.googleapis.com/fcm/send',
                        headers=headers,
                        json=data,
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        sent_ids.append(resp.json().get('results', [{}])[0].get('message_id', sub.token[:20]))
                    else:
                        self.logger.error("[FCM] HTTP %s", resp.status_code)
                except Exception as e:
                    self.logger.error("[FCM] Token %s failed: %s", sub.token[:20], e)

            if sent_ids:
                return True, None, ",".join(sent_ids[:3])
            return False, "All FCM sends failed", None

        except Exception as e:
            self.logger.error("[FCM] Provider error: %s", e)
            return False, str(e), None


class InAppProvider(NotificationProvider):
    """
    In-app real-time notifications.
    The DB record is created by the dispatcher; this provider
    optionally emits a SocketIO event if the extension is available.
    """

    def send(self, donor, title, message, payload=None, request_id=None):
        try:
            from app import socketio  # type: ignore
            socketio.emit(
                'notification',
                {
                    'title': title,
                    'message': message,
                    'payload': payload or {},
                },
                room=f"donor_{donor.id}",
            )
            self.logger.info("[IN-APP] SocketIO emitted to donor_%s", donor.id)
        except (ImportError, Exception) as e:
            # SocketIO not available or donor not connected — silent fail is fine
            self.logger.debug("[IN-APP] SocketIO emit skipped for donor %s: %s", donor.id, e)
        return True, None, f"in_app_{donor.id}"
