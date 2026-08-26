import logging
from flask import session, request
from flask_socketio import emit, join_room, leave_room
from app import socketio, db
from app.models import BloodBankAccount

logger = logging.getLogger(__name__)

@socketio.on('connect')
def handle_connect():
    sid = getattr(request, 'sid', 'unknown')
    logger.info("Socket.IO client connected: %s (remote_addr: %s)", sid, request.remote_addr)

@socketio.on('disconnect')
def handle_disconnect():
    sid = getattr(request, 'sid', 'unknown')
    logger.info("Socket.IO client disconnected: %s", sid)

@socketio.on('join_bloodbank')
def handle_join_bloodbank(data=None):
    """
    Securely joins the authenticated Blood Bank room.
    NEVER trusts client-supplied blood_bank_id; strictly resolves from session.
    """
    sid = getattr(request, 'sid', 'unknown')
    account_id = session.get('bloodbank_account_id')
    if not account_id:
        logger.warning("Unauthenticated socket join attempt from SID: %s", sid)
        emit('join_error', {'message': 'Authentication required'})
        return

    account = BloodBankAccount.query.get(account_id)
    if not account or not account.blood_bank_id or not account.is_active:
        logger.warning("Invalid or inactive account socket join attempt: %s", account_id)
        emit('join_error', {'message': 'Account invalid or inactive'})
        return

    room = f"blood_bank_{account.blood_bank_id}"
    join_room(room)
    logger.info("BloodBank Account %s joined room: %s (SID: %s)", account.login_id, room, sid)
    emit('joined_bloodbank', {
        'status': 'ok',
        'blood_bank_id': account.blood_bank_id,
        'room': room,
        'login_id': account.login_id
    })

@socketio.on('leave_bloodbank')
def handle_leave_bloodbank():
    account_id = session.get('bloodbank_account_id')
    if account_id:
        account = BloodBankAccount.query.get(account_id)
        if account and account.blood_bank_id:
            room = f"blood_bank_{account.blood_bank_id}"
            leave_room(room)
            logger.info("BloodBank Account %s left room: %s", account.login_id, room)
