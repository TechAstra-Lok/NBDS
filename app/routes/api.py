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
import json
from flask import Response, stream_with_context

GEMINI_CANDIDATE_MODELS = [
    'gemini-1.5-flash',
    'gemini-2.0-flash',
    'gemini-2.5-flash',
    'gemini-1.5-pro',
    'gemini-flash-latest'
]

def _get_medical_fallback_response(user_message):
    msg = (user_message or '').lower()
    if any(k in msg for k in ['eligib', 'require', 'age', 'weight', 'can i donate', 'rule', 'qualif']):
        return (
            "### 🩸 Basic Blood Donor Eligibility Guidelines\n\n"
            "- **Age:** Must be between **18 and 60 years** old.\n"
            "- **Weight:** Minimum **45 kg (99 lbs)**.\n"
            "- **Hemoglobin Level:** Minimum **12.5 g/dL**.\n"
            "- **Donation Interval:** At least **90 days (3 months)** between whole blood donations.\n"
            "- **Health Status:** Must be in good general health, free from active infections, fever, or cold/flu symptoms."
        )
    elif any(k in msg for k in ['o+', 'o-', 'a+', 'a-', 'b+', 'b-', 'ab+', 'ab-', 'compatib', 'group', 'receive']):
        return (
            "### 🩸 Blood Group Compatibility Overview\n\n"
            "- **O Negative (O-):** Universal Red Cell Donor (can donate to all blood groups).\n"
            "- **AB Positive (AB+):** Universal Red Cell Recipient (can receive from all blood groups).\n"
            "- **O Positive (O+):** Can donate to O+, A+, B+, AB+; receives from O+ and O-.\n"
            "- **A Positive (A+):** Can donate to A+ and AB+; receives from A+, A-, O+, O-.\n"
            "- **B Positive (B+):** Can donate to B+ and AB+; receives from B+, B-, O+, O-."
        )
    elif any(k in msg for k in ['eat', 'food', 'diet', 'iron', 'hemoglobin', 'hb', 'boost', 'vitamin']):
        return (
            "### 🥗 Pre & Post Donation Diet Tips\n\n"
            "- **Iron-Rich Foods:** Eat spinach, lentils, dark leafy greens, beans, and lean meats.\n"
            "- **Vitamin C Pairing:** Pair iron-rich foods with Vitamin C (oranges, lemons, tomatoes) for maximum iron absorption.\n"
            "- **Hydration:** Drink **500ml+ of water or fresh fruit juice** before and after donation.\n"
            "- **Avoid:** Avoid fatty foods, alcohol, and heavy caffeinated beverages before donating."
        )
    elif any(k in msg for k in ['before', 'after', 'care', 'tip', 'pre', 'post']):
        return (
            "### 🩺 Pre & Post Donation Care Instructions\n\n"
            "- **Before Donation:** Get 7-8 hours of sleep, eat a nutritious light meal, and stay well hydrated.\n"
            "- **During Donation:** Relax and inform the staff immediately if you feel dizzy.\n"
            "- **After Donation:** Keep the bandage on for 4 hours, avoid heavy lifting or strenuous exercise for 24 hours, and increase fluid intake."
        )
    else:
        return (
            "Namaste! Raktadata Helpher AI is currently experiencing high demand. Here are essential blood donor guidelines:\n\n"
            "1. **Age Requirement:** 18–60 years old\n"
            "2. **Minimum Weight:** 45 kg\n"
            "3. **Hemoglobin Level:** 12.5 g/dL+\n"
            "4. **Donation Gap:** 90 days between donations\n\n"
            "Please try asking your specific question again in a few moments!"
        )


@api_bp.route('/raktadata-helpher', methods=['POST'])
def raktadata_helpher():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'success': False, 'error': 'No message provided'}), 400

    user_message = data['message'].strip()
    history = data.get('history', [])

    api_key = os.environ.get('GEMINI_API_KEY', '')

    contents = []
    for msg in history:
        contents.append({
            "role": "model" if msg.get('role') in ('ai', 'model') else "user",
            "parts": [{"text": msg.get('content', '')}]
        })
    contents.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    system_instruction = (
        "You are Raktadata Helpher, an ultimate doctor, nurse, and HA (Health Assistant) module for Raktadata Nepal. "
        "Answer queries ONLY about health, medical tips, and blood donation guidelines. "
        "Keep responses concise, empathetic, accurate, and structured with markdown."
    )

    payload = {
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 1000
        }
    }

    # Attempt candidate models
    for model_name in GEMINI_CANDIDATE_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=12)
            if res.status_code == 200:
                res_data = res.json()
                candidates = res_data.get('candidates', [])
                if candidates and candidates[0].get('content'):
                    reply_text = candidates[0]['content']['parts'][0]['text']
                    return jsonify({'success': True, 'reply': reply_text})
        except Exception:
            continue

    # Fallback if API key / service is unavailable
    fallback_reply = _get_medical_fallback_response(user_message)
    return jsonify({'success': True, 'reply': fallback_reply})


@api_bp.route('/raktadata-helpher/stream', methods=['POST'])
def raktadata_helpher_stream():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'success': False, 'error': 'No message provided'}), 400

    user_message = data['message'].strip()
    history = data.get('history', [])

    api_key = os.environ.get('GEMINI_API_KEY', '')

    contents = []
    for msg in history:
        contents.append({
            "role": "model" if msg.get('role') in ('ai', 'model') else "user",
            "parts": [{"text": msg.get('content', '')}]
        })
    contents.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    system_instruction = (
        "You are Raktadata Helpher, an ultimate doctor, nurse, and HA (Health Assistant) module for Raktadata Nepal. "
        "Your primary role is to answer queries ONLY about health-related problems, blood donation, healthy habits, medical guidance, and pre/post donation tips. "
        "Provide complete, thorough, comprehensive, and clear medical guidance. DO NOT truncate or cut off your advice prematurely. "
        "Structure your answers neatly with markdown headings, bullet points, and clear sections."
    )

    payload = {
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 3000
        }
    }

    def generate():
        success = False

        for model_name in GEMINI_CANDIDATE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?key={api_key}&alt=sse"
            try:
                with requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, stream=True, timeout=15) as response:
                    if response.status_code == 200:
                        has_data = False
                        for line in response.iter_lines():
                            if line:
                                decoded_line = line.decode('utf-8')
                                if decoded_line.startswith('data:'):
                                    has_data = True
                                yield decoded_line + '\n\n'
                        if has_data:
                            success = True
                            break
            except Exception:
                continue

        if not success:
            fallback_text = _get_medical_fallback_response(user_message)
            chunk = {
                "candidates": [{
                    "content": {
                        "parts": [{"text": fallback_text}]
                    }
                }]
            }
            yield f'data: {json.dumps(chunk)}\n\n'
            yield 'data: [DONE]\n\n'

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

