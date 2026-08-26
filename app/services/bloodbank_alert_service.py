import json
import math
import logging
from datetime import datetime, timezone
from flask import url_for
from app import db, socketio
from app.models import (
    BloodBank, BloodBankAccount, BloodBankNotification,
    BloodBankAlertSettings, BloodBankNotificationDelivery,
    BloodReservation, BloodRequest, SiteConfig
)

logger = logging.getLogger(__name__)


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points in kilometers."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    try:
        lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        r = 6371.0 # Earth's radius in km
        return round(r * c, 2)
    except Exception as e:
        logger.warning("Error calculating Haversine distance: %s", e)
        return None


def get_default_alert_radius():
    """Retrieve global default radius setting from SiteConfig or fallback to 25 km."""
    try:
        cfg = SiteConfig.query.filter_by(key='blood_bank_request_alert_radius_km').first()
        if cfg and cfg.value:
            return int(cfg.value)
    except Exception:
        pass
    return 25


def dispatch_reservation_alert(reservation):
    """
    Triggers real-time alerts when a blood reservation is created (status=pending).
    Strictly notifies ONLY the corresponding Blood Bank portal.
    """
    if not reservation or not reservation.blood_bank_id:
        return None

    blood_bank_id = reservation.blood_bank_id
    blood_bank = BloodBank.query.get(blood_bank_id)
    if not blood_bank or not blood_bank.is_active:
        return None

    # Check Blood Bank Alert Settings
    settings = BloodBankAlertSettings.query.filter_by(blood_bank_id=blood_bank_id).first()
    if settings and not settings.reservation_alerts_enabled:
        logger.info("Reservation alerts disabled for Blood Bank %s", blood_bank_id)
        return None

    # Deduplication Check
    existing = BloodBankNotification.query.filter_by(
        blood_bank_id=blood_bank_id,
        notification_type='RESERVATION',
        reservation_id=reservation.id
    ).first()

    if existing:
        logger.info("Duplicate reservation notification skipped for Res ID %s", reservation.id)
        return existing

    priority = 'EMERGENCY' if getattr(reservation, 'priority', '').lower() == 'emergency' else 'HIGH'
    title = f"Blood Reservation #{reservation.id:05d} Received"
    message = (
        f"New reservation for {reservation.units} unit(s) of {reservation.blood_group} "
        f"({reservation.component or 'Whole Blood'}) for patient {reservation.patient_name} at {reservation.hospital_name}."
    )

    meta_payload = {
        'event': 'blood_reservation_received',
        'reservation_id': reservation.id,
        'blood_bank_id': blood_bank_id,
        'patient_name': reservation.patient_name,
        'hospital_name': reservation.hospital_name,
        'blood_group': reservation.blood_group,
        'component': reservation.component or 'Whole Blood',
        'units': reservation.units,
        'urgency': reservation.priority or 'Normal',
        'contact_person': getattr(reservation, 'contact_person', '') or '',
        'contact_number': getattr(reservation, 'contact_number', '') or '',
        'required_date': reservation.required_date.strftime('%Y-%m-%d') if getattr(reservation, 'required_date', None) else '',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'sound_enabled': settings.sound_enabled if settings else True,
    }

    # 1. Store Notification
    notif = BloodBankNotification(
        blood_bank_id=blood_bank_id,
        notification_type='RESERVATION',
        title=title,
        message=message,
        reservation_id=reservation.id,
        priority=priority,
        meta_json=json.dumps(meta_payload),
        is_read=False,
        is_archived=False,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(notif)
    db.session.flush()

    # 2. Real-time Socket.IO emission to the blood bank's private room
    room = f"blood_bank_{blood_bank_id}"
    try:
        socketio.emit('blood_reservation_received', meta_payload, to=room)
        logger.info("Emitted blood_reservation_received to room %s for Res ID %s", room, reservation.id)
        delivery = BloodBankNotificationDelivery(
            notification_id=notif.id,
            channel='socket',
            status='sent',
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(delivery)
        notif.delivered_at = datetime.now(timezone.utc)
    except Exception as sock_err:
        logger.warning("Socket emission failed for Res ID %s: %s", reservation.id, sock_err)
        delivery = BloodBankNotificationDelivery(
            notification_id=notif.id,
            channel='socket',
            status='failed',
            error_message=str(sock_err),
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(delivery)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to commit reservation notification: %s", e)
        return None

    return notif


def dispatch_nearby_request_alert(blood_request):
    """
    Detects blood banks geographically near the posted public blood request
    and dispatches real-time alerts to their respective portals.
    """
    if not blood_request:
        return 0

    req_lat = getattr(blood_request, 'latitude', None)
    req_lon = getattr(blood_request, 'longitude', None)
    req_district = getattr(blood_request, 'district', '') or ''
    req_province = getattr(blood_request, 'province', '') or ''
    req_is_emergency = getattr(blood_request, 'is_emergency', False) or getattr(blood_request, 'urgency', '') == 'Emergency'

    global_default_radius = get_default_alert_radius()
    all_banks = BloodBank.query.filter_by(is_active=True).all()
    notified_count = 0

    for bank in all_banks:
        settings = BloodBankAlertSettings.query.filter_by(blood_bank_id=bank.id).first()
        if settings and not settings.nearby_request_alerts_enabled:
            continue

        # Check emergency-only filter
        if settings and settings.emergency_only and not req_is_emergency:
            continue

        # Check blood group filter
        if settings and settings.alert_blood_groups:
            allowed_groups = [g.strip().upper() for g in settings.alert_blood_groups.split(',') if g.strip()]
            if allowed_groups and (blood_request.blood_group or '').upper() not in allowed_groups:
                continue

        radius_km = settings.alert_radius_km if settings and settings.alert_radius_km else global_default_radius

        # Distance calculation
        distance_km = None
        is_nearby = False

        if req_lat is not None and req_lon is not None and bank.latitude is not None and bank.longitude is not None:
            distance_km = haversine_distance(req_lat, req_lon, bank.latitude, bank.longitude)
            if distance_km is not None and distance_km <= radius_km:
                is_nearby = True
        else:
            # Fallback: Location name matching (District or Province)
            if req_district and bank.district and req_district.strip().lower() == bank.district.strip().lower():
                is_nearby = True
                distance_km = 0.0 # Same district approximation
            elif req_province and bank.province and req_province.strip().lower() == bank.province.strip().lower():
                is_nearby = True
                distance_km = 15.0 # Same province approximation

        if not is_nearby:
            continue

        # Deduplication Check
        existing = BloodBankNotification.query.filter_by(
            blood_bank_id=bank.id,
            notification_type='NEARBY_REQUEST',
            blood_request_id=str(blood_request.request_id)
        ).first()

        if existing:
            continue

        priority = 'EMERGENCY' if req_is_emergency else 'HIGH'
        dist_str = f" (~{distance_km:.1f} km away)" if distance_km is not None and distance_km > 0 else ""
        title = f"Blood Request {blood_request.blood_group} Near Your Location"
        message = (
            f"Urgent blood request for {blood_request.patient_name or 'Patient'} "
            f"({blood_request.blood_group}) at {blood_request.hospital or 'Hospital'}"
            f"{dist_str} in {blood_request.district or bank.district}."
        )

        meta_payload = {
            'event': 'nearby_blood_request',
            'request_id': str(blood_request.request_id),
            'blood_bank_id': bank.id,
            'blood_group': blood_request.blood_group or '',
            'patient_name': blood_request.patient_name or '',
            'hospital': blood_request.hospital or '',
            'district': blood_request.district or bank.district or '',
            'local_level': getattr(blood_request, 'local_level', '') or '',
            'urgency': 'Emergency' if req_is_emergency else 'Normal',
            'distance_km': distance_km,
            'contact_person': getattr(blood_request, 'contact_person', '') or '',
            'contact_number': getattr(blood_request, 'contact_number', '') or '',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'sound_enabled': settings.sound_enabled if settings else True,
        }

        notif = BloodBankNotification(
            blood_bank_id=bank.id,
            notification_type='NEARBY_REQUEST',
            title=title,
            message=message,
            blood_request_id=str(blood_request.request_id),
            priority=priority,
            meta_json=json.dumps(meta_payload),
            is_read=False,
            is_archived=False,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(notif)
        db.session.flush()

        room = f"blood_bank_{bank.id}"
        try:
            socketio.emit('nearby_blood_request', meta_payload, to=room)
            db.session.add(BloodBankNotificationDelivery(
                notification_id=notif.id,
                channel='socket',
                status='sent',
                created_at=datetime.now(timezone.utc)
            ))
            notif.delivered_at = datetime.now(timezone.utc)
        except Exception as err:
            logger.warning("Failed to emit nearby request to room %s: %s", room, err)
            db.session.add(BloodBankNotificationDelivery(
                notification_id=notif.id,
                channel='socket',
                status='failed',
                error_message=str(err),
                created_at=datetime.now(timezone.utc)
            ))

        notified_count += 1

    try:
        db.session.commit()
    except Exception as commit_err:
        db.session.rollback()
        logger.error("Failed to commit nearby request notifications: %s", commit_err)

    return notified_count
