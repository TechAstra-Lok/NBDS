"""
Notification REST API & Donor Preference Center Routes
======================================================
Provides endpoints for:
- In-app notification feed (GET, mark read, delete)
- Notification preference management
- Web Push subscription management
- Donor response to blood requests
- Queue & analytics (admin)
"""
from datetime import datetime
from flask import Blueprint, jsonify, request, session, redirect, url_for, flash, render_template
from app import db
from app.models import (
    Notification,
    DonorNotificationPreference, PushSubscription,
    DonorResponse, BloodRequest, Donor,
)

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_current_donor():
    """Return the logged-in Donor or None."""
    donor_id = session.get('donor_id')
    if not donor_id:
        return None
    return Donor.query.get(donor_id)


def _api_auth():
    """Return (donor, error_response) — checks donor session."""
    donor = _get_current_donor()
    if not donor:
        return None, jsonify({'error': 'Unauthorized. Please log in.'}), 401
    return donor, None, None


# ---------------------------------------------------------------------------
# In-App Notification Feed API
# ---------------------------------------------------------------------------

@notifications_bp.route('/api/list', methods=['GET'])
def api_list():
    """GET /notifications/api/list — Paginated list of donor's notifications."""
    donor = _get_current_donor()
    if not donor:
        return jsonify({'error': 'Unauthorized'}), 401

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 50)
    category = request.args.get('category', '')
    unread_only = request.args.get('unread', 'false').lower() == 'true'

    q = Notification.query.filter_by(donor_id=donor.id)
    if category:
        q = q.filter_by(category=category)
    if unread_only:
        q = q.filter_by(is_read=False)

    paginated = q.order_by(Notification.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'notifications': [n.to_dict() for n in paginated.items],
        'total': paginated.total,
        'pages': paginated.pages,
        'page': page,
        'unread_count': Notification.query.filter_by(donor_id=donor.id, is_read=False).count(),
    })


@notifications_bp.route('/api/unread-count', methods=['GET'])
def api_unread_count():
    """Quick endpoint for the notification bell badge."""
    donor = _get_current_donor()
    if not donor:
        return jsonify({'unread_count': 0})
    count = Notification.query.filter_by(donor_id=donor.id, is_read=False).count()
    return jsonify({'unread_count': count})


@notifications_bp.route('/api/mark-read/<int:notif_id>', methods=['POST'])
def api_mark_read(notif_id):
    donor = _get_current_donor()
    if not donor:
        return jsonify({'error': 'Unauthorized'}), 401
    notif = Notification.query.filter_by(id=notif_id, donor_id=donor.id).first_or_404()
    notif.is_read = True
    notif.read_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})


@notifications_bp.route('/api/mark-all-read', methods=['POST'])
def api_mark_all_read():
    donor = _get_current_donor()
    if not donor:
        return jsonify({'error': 'Unauthorized'}), 401
    Notification.query.filter_by(donor_id=donor.id, is_read=False).update({
        'is_read': True,
        'read_at': datetime.utcnow(),
    })
    db.session.commit()
    return jsonify({'success': True})


@notifications_bp.route('/api/delete/<int:notif_id>', methods=['DELETE'])
def api_delete(notif_id):
    donor = _get_current_donor()
    if not donor:
        return jsonify({'error': 'Unauthorized'}), 401
    notif = Notification.query.filter_by(id=notif_id, donor_id=donor.id).first_or_404()
    db.session.delete(notif)
    db.session.commit()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Donor Response to Blood Request
# ---------------------------------------------------------------------------

@notifications_bp.route('/api/respond', methods=['POST'])
def api_respond():
    """POST /notifications/api/respond — Donor responds to a blood request."""
    donor = _get_current_donor()
    if not donor:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    request_id = data.get('request_id', '')
    response_type = data.get('response_type', '')

    VALID_RESPONSES = {'available', 'maybe', 'unavailable', 'already_donated', 'contact_later'}
    if response_type not in VALID_RESPONSES:
        return jsonify({'error': 'Invalid response type'}), 400

    blood_req = BloodRequest.query.filter_by(request_id=request_id).first()
    if not blood_req:
        return jsonify({'error': 'Blood request not found'}), 404

    # Upsert donor response
    existing = DonorResponse.query.filter_by(
        blood_request_id=request_id, donor_id=donor.id
    ).first()
    if existing:
        existing.response_type = response_type
        existing.message = data.get('message', '')
        existing.created_at = datetime.utcnow()
    else:
        resp = DonorResponse(
            blood_request_id=request_id,
            donor_id=donor.id,
            response_type=response_type,
            message=data.get('message', ''),
        )
        db.session.add(resp)

    db.session.commit()
    return jsonify({'success': True, 'response_type': response_type})


# ---------------------------------------------------------------------------
# Notification Preferences
# ---------------------------------------------------------------------------

@notifications_bp.route('/preferences', methods=['GET', 'POST'])
def preferences():
    """Donor notification preference center."""
    donor = _get_current_donor()
    if not donor:
        flash('Please log in to manage notification preferences.', 'warning')
        return redirect(url_for('public.donor_login'))

    pref = DonorNotificationPreference.query.filter_by(donor_id=donor.id).first()
    if not pref:
        pref = DonorNotificationPreference(donor_id=donor.id)
        db.session.add(pref)
        db.session.commit()

    if request.method == 'POST':
        pref.email_alerts = 'email_alerts' in request.form
        pref.sms_alerts = 'sms_alerts' in request.form
        pref.in_app_alerts = 'in_app_alerts' in request.form
        pref.web_push_alerts = 'web_push_alerts' in request.form
        pref.mobile_push_alerts = 'mobile_push_alerts' in request.form
        pref.dnd_mode = 'dnd_mode' in request.form

        qhs = request.form.get('quiet_hours_start', '').strip()
        qhe = request.form.get('quiet_hours_end', '').strip()
        try:
            pref.quiet_hours_start = datetime.strptime(qhs, '%H:%M').time() if qhs else None
        except ValueError:
            pref.quiet_hours_start = None
        try:
            pref.quiet_hours_end = datetime.strptime(qhe, '%H:%M').time() if qhe else None
        except ValueError:
            pref.quiet_hours_end = None

        db.session.commit()
        flash('Notification preferences updated.', 'success')
        return redirect(url_for('notifications.preferences'))

    return render_template('notifications/preferences.html', donor=donor, pref=pref)


@notifications_bp.route('/api/preferences', methods=['GET', 'PUT'])
def api_preferences():
    """REST endpoint for preference management."""
    donor = _get_current_donor()
    if not donor:
        return jsonify({'error': 'Unauthorized'}), 401

    pref = DonorNotificationPreference.query.filter_by(donor_id=donor.id).first()
    if not pref:
        pref = DonorNotificationPreference(donor_id=donor.id)
        db.session.add(pref)
        db.session.commit()

    if request.method == 'PUT':
        data = request.get_json(silent=True) or {}
        for field in ['email_alerts', 'sms_alerts', 'in_app_alerts', 'web_push_alerts', 'mobile_push_alerts', 'dnd_mode']:
            if field in data:
                setattr(pref, field, bool(data[field]))
        db.session.commit()
        return jsonify({'success': True, 'preferences': pref.to_dict()})

    return jsonify({'preferences': pref.to_dict()})


# ---------------------------------------------------------------------------
# Web Push Subscription Management
# ---------------------------------------------------------------------------

@notifications_bp.route('/api/push/subscribe', methods=['POST'])
def api_push_subscribe():
    """Register a Web Push subscription for the logged-in donor."""
    donor = _get_current_donor()
    if not donor:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint', '').strip()
    auth_key = data.get('auth', '').strip()
    p256dh = data.get('p256dh', '').strip()

    if not endpoint:
        return jsonify({'error': 'Missing endpoint'}), 400

    existing = PushSubscription.query.filter_by(token=endpoint).first()
    if existing:
        existing.donor_id = donor.id
        existing.auth_key = auth_key
        existing.p256dh_key = p256dh
        existing.is_active = True
        existing.last_used_at = datetime.utcnow()
    else:
        sub = PushSubscription(
            donor_id=donor.id,
            platform='web',
            token=endpoint,
            auth_key=auth_key,
            p256dh_key=p256dh,
            is_active=True,
        )
        db.session.add(sub)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Push subscription registered.'})


@notifications_bp.route('/api/push/unsubscribe', methods=['POST'])
def api_push_unsubscribe():
    """Deactivate a Web Push subscription."""
    donor = _get_current_donor()
    if not donor:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint', '').strip()
    sub = PushSubscription.query.filter_by(token=endpoint, donor_id=donor.id).first()
    if sub:
        sub.is_active = False
        db.session.commit()
    return jsonify({'success': True})
