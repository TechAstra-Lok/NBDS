from flask import Blueprint, jsonify, request
from app import db
from app.models import Donor, BloodRequest, Advertisement, BloodBank, BloodInventory, BloodReservation, BloodTransfer, LowStockAlert
from sqlalchemy import desc, or_, func

api_bp = Blueprint('api', __name__)


def _resolve_api_bank_tenant(bank_id):
    """Resolve tenant context for a bank so tenant-scoped queries work."""
    bank = BloodBank.query.get(bank_id)
    if bank and bank.tenant_id and bank.db_name and bank.tenant_status == 'Active':
        try:
            from app.services.tenant_service import TenantResolutionService
            TenantResolutionService.resolve_tenant(bank.tenant_id)
        except Exception:
            pass


@api_bp.route('/donors/search')
def search_donors():
    blood_group = request.args.get('bg', '')
    district    = request.args.get('district', '')
    q           = request.args.get('q', '')
    limit       = min(request.args.get('limit', 10, type=int), 50)
    
    query = Donor.query.filter_by(availability_status='available')
    
    if blood_group:
        query = query.filter_by(blood_group=blood_group)
    if district:
        query = query.filter(Donor.curr_district.ilike(f'%{district}%'))
    if q:
        query = query.filter(or_(
            Donor.full_name.ilike(f'%{q}%'),
            Donor.curr_local_level.ilike(f'%{q}%'),
        ))
    
    donors = query.order_by(desc(Donor.created_at)).limit(limit).all()
    
    return jsonify({
        'success': True,
        'count': len(donors),
        'donors': [d.to_dict() for d in donors]
    })


@api_bp.route('/requests/active')
def active_requests():
    blood_group = request.args.get('bg', '')
    
    query = BloodRequest.query.filter_by(status='active')
    if blood_group:
        query = query.filter_by(blood_group=blood_group)
    
    requests = query.order_by(
        BloodRequest.is_emergency.desc(),
        desc(BloodRequest.created_at)
    ).limit(20).all()
    
    return jsonify({
        'success': True,
        'count': len(requests),
        'requests': [r.to_dict() for r in requests]
    })


@api_bp.route('/blood-banks')
def blood_banks_api():
    q = request.args.get('q', '').strip()
    query = BloodBank.query.filter_by(is_active=True)

    if q:
        pattern = f'%{q}%'
        query = query.filter(
            or_(
                BloodBank.name.ilike(pattern),
                BloodBank.district.ilike(pattern),
                BloodBank.province.ilike(pattern),
                BloodBank.service_type.ilike(pattern),
            )
        )

    banks = query.order_by(BloodBank.name).all()
    return jsonify({
        'success': True,
        'count': len(banks),
        'blood_banks': [bank.to_dict() for bank in banks]
    })


@api_bp.route('/blood-banks/<int:bank_id>/inventory')
def blood_bank_inventory_api(bank_id):
    _resolve_api_bank_tenant(bank_id)
    inventory_items = BloodInventory.query.filter_by(blood_bank_id=bank_id).order_by(BloodInventory.blood_group).all()
    inventory_payload = []
    for item in inventory_items:
        data = item.to_dict()
        data['movements'] = [movement.to_dict() for movement in item.movements]
        inventory_payload.append(data)

    return jsonify({
        'success': True,
        'count': len(inventory_items),
        'inventory': inventory_payload
    })


@api_bp.route('/blood-banks/<int:bank_id>/reservations')
def blood_bank_reservations_api(bank_id):
    _resolve_api_bank_tenant(bank_id)
    reservations = BloodReservation.query.filter_by(blood_bank_id=bank_id).order_by(BloodReservation.requested_at.desc()).all()
    return jsonify({
        'success': True,
        'count': len(reservations),
        'reservations': [item.to_dict() for item in reservations]
    })


@api_bp.route('/blood-banks/<int:bank_id>/transfers')
def blood_bank_transfers_api(bank_id):
    _resolve_api_bank_tenant(bank_id)
    transfers = BloodTransfer.query.filter((BloodTransfer.source_bank_id == bank_id) | (BloodTransfer.destination_bank_id == bank_id)).order_by(BloodTransfer.created_at.desc()).all()
    return jsonify({
        'success': True,
        'count': len(transfers),
        'transfers': [item.to_dict() for item in transfers]
    })


@api_bp.route('/blood-banks/<int:bank_id>/alerts')
def blood_bank_alerts_api(bank_id):
    _resolve_api_bank_tenant(bank_id)
    alerts = LowStockAlert.query.filter_by(blood_bank_id=bank_id).order_by(LowStockAlert.created_at.desc()).all()
    return jsonify({
        'success': True,
        'count': len(alerts),
        'alerts': [item.to_dict() for item in alerts]
    })


@api_bp.route('/stats')
def stats():
    from app.models import News
    
    return jsonify({
        'total_donors':     Donor.query.count(),
        'available_donors': Donor.query.filter_by(availability_status='available').count(),
        'active_requests':  BloodRequest.query.filter_by(status='active').count(),
        'fulfilled':        BloodRequest.query.filter_by(status='fulfilled').count(),
        'total_news':       News.query.filter_by(is_published=True).count(),
        'districts_covered': db.session.query(func.count(func.distinct(Donor.curr_district))).scalar() or 0,
        'active_emergencies': BloodRequest.query.filter_by(status='active', is_emergency=True).count(),
    })


@api_bp.route('/ad/impression/<int:ad_id>', methods=['POST'])
def track_impression(ad_id):
    ad = Advertisement.query.get(ad_id)
    if ad:
        ad.impressions += 1
        db.session.commit()
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 404

import os
import requests

@api_bp.route('/raktadata-helpher', methods=['POST'])
def raktadata_helpher():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'success': False, 'error': 'No message provided'}), 400

    user_message = data['message'].strip()
    history = data.get('history', [])

    api_key = os.environ.get('GEMINI_API_KEY', '')
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"

    # Build contents array from history and new message
    contents = []
    for msg in history:
        contents.append({
            "role": "model" if msg.get('role') == 'ai' else "user",
            "parts": [{"text": msg.get('content')}]
        })
    
    contents.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    system_instruction = (
        "You are Raktadata Helpher, an ultimate doctor, nurse, and HA (Health Assistant) module. "
        "Your primary role is to answer queries ONLY about health-related problems, blood donation, healthy habits, and medical tips. "
        "You provide suggestions, health tips, and guidance in a professional, empathetic, and strictly medical/health context. "
        "If a user asks about anything outside of health, medical topics, or blood donation (e.g., programming, history, general knowledge, politics, math), "
        "you MUST politely decline to answer, state your purpose, and steer the conversation back to health or blood topics. "
        "Keep your responses concise, well-formatted, and easy to read. You can use markdown."
    )

    payload = {
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 800
        }
    }

    try:
        response = requests.post(
            url, 
            json=payload, 
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        
        response_data = response.json()
        candidates = response_data.get('candidates', [])
        
        if candidates and candidates[0].get('content'):
            reply_text = candidates[0]['content']['parts'][0]['text']
            return jsonify({'success': True, 'reply': reply_text})
        else:
            return jsonify({'success': False, 'error': 'No response from AI model'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to process request: {str(e)}'}), 500

from flask import Response, stream_with_context
import json

@api_bp.route('/raktadata-helpher/stream', methods=['POST'])
def raktadata_helpher_stream():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'success': False, 'error': 'No message provided'}), 400

    user_message = data['message'].strip()
    history = data.get('history', [])

    api_key = os.environ.get('GEMINI_API_KEY', '')
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:streamGenerateContent?key={api_key}&alt=sse"

    contents = []
    for msg in history:
        contents.append({
            "role": "model" if msg.get('role') == 'ai' else "user",
            "parts": [{"text": msg.get('content')}]
        })
    
    contents.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    system_instruction = (
        "You are Raktadata Helpher, an ultimate doctor, nurse, and HA (Health Assistant) module. "
        "Your primary role is to answer queries ONLY about health-related problems, blood donation, healthy habits, and medical tips. "
        "You provide suggestions, health tips, and guidance in a professional, empathetic, and strictly medical/health context. "
        "If a user asks about anything outside of health, medical topics, or blood donation (e.g., programming, history, general knowledge, politics, math), "
        "you MUST politely decline to answer, state your purpose, and steer the conversation back to health or blood topics. "
        "Keep your responses concise, well-formatted, and easy to read. You can use markdown."
    )

    payload = {
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 800
        }
    }

    def generate():
        try:
            with requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        yield decoded_line + '\n\n'
        except Exception as e:
            yield f'data: {json.dumps({"error": str(e)})}\n\n'

    return Response(stream_with_context(generate()), mimetype='text/event-stream')
