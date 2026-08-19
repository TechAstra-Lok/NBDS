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
import time
from flask import Response, stream_with_context, current_app

# Try fastest/best model first
GEMINI_CANDIDATE_MODELS = [
    'gemini-2.5-flash',
    'gemini-2.0-flash',
    'gemini-1.5-flash',
    'gemini-1.5-pro',
]

SYSTEM_INSTRUCTION = (
    "You are Raktadata Helper — a conversational AI assistant for Raktadata Nepal, "
    "a blood donation and health platform.\n\n"
    "Your personality:\n"
    "- Natural, warm, and direct — like a knowledgeable friend who is also a doctor.\n"
    "- Keep responses CONCISE and focused on exactly what was asked. No padding, no generic filler.\n"
    "- For a simple greeting like 'hello' or 'hi', just greet back naturally and ask how you can help.\n"
    "- For a health or medical question, give a clear, accurate, and practical answer.\n"
    "- For a blood donation question, give specific guidance including Nepal's criteria where relevant.\n"
    "- Match the length of your reply to the complexity of the question. Short question = short answer.\n\n"
    "Rules:\n"
    "1. NEVER give a generic response — always reply to exactly what the user said.\n"
    "2. Reply in the same language the user writes in (English, Nepali, or Romanized Nepali).\n"
    "3. Use simple formatting: bold for key points, short bullet lists only when needed.\n"
    "4. If something requires a doctor's physical assessment, say so clearly but still provide helpful context.\n"
    "5. You can answer ANY health, medical, wellness, fitness, nutrition, or blood donation question.\n"
    "6. Do NOT add disclaimers or long safety warnings unless genuinely needed.\n"
    "7. Do NOT repeat the user's question back to them. Just answer it."
)


def _is_valid_gemini_key(api_key):
    if not api_key:
        return False
    clean = api_key.strip()
    if clean in ('', 'your-gemini-api-key-here', 'replace-with-gemini-api-key'):
        return False
    return len(clean) >= 20


def _build_gemini_contents(history, user_message):
    """Build the Gemini contents array from chat history + current message."""
    contents = []
    for msg in history[-10:]:  # last 10 turns for context
        role = "model" if msg.get('role') in ('ai', 'model', 'assistant') else "user"
        text = msg.get('content', '').strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    return contents


def _gemini_payload(contents):
    return {
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024,
            "topP": 0.95,
        }
    }


@api_bp.route('/raktadata-helper', methods=['POST'])
@api_bp.route('/raktadata-helpher', methods=['POST'])
def raktadata_helper():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'success': False, 'error': 'No message provided'}), 400

    user_message = data['message'].strip()
    history = data.get('history', [])
    api_key = current_app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY', '')

    if not _is_valid_gemini_key(api_key):
        return jsonify({
            'success': False,
            'reply': 'AI service is not configured. Please contact the administrator.'
        }), 503

    contents = _build_gemini_contents(history, user_message)
    payload = _gemini_payload(contents)

    for model_name in GEMINI_CANDIDATE_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            res = requests.post(
                url, json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=12
            )
            if res.status_code == 200:
                res_data = res.json()
                candidates = res_data.get('candidates', [])
                if candidates and candidates[0].get('content'):
                    reply_text = candidates[0]['content']['parts'][0]['text']
                    return jsonify({'success': True, 'reply': reply_text})
        except Exception:
            continue

    return jsonify({
        'success': False,
        'reply': 'I\'m having trouble connecting right now. Please try again in a moment.'
    }), 503


@api_bp.route('/raktadata-helper/stream', methods=['POST'])
@api_bp.route('/raktadata-helpher/stream', methods=['POST'])
def raktadata_helper_stream():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'success': False, 'error': 'No message provided'}), 400

    user_message = data['message'].strip()
    history = data.get('history', [])
    api_key = current_app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY', '')

    def generate():
        if not _is_valid_gemini_key(api_key):
            error_chunk = {
                "candidates": [{"content": {"parts": [{"text": (
                    "⚠️ Raktadata Helper is not configured yet. "
                    "Please ask the administrator to set up the Gemini API key."
                )}]}}]
            }
            yield f'data: {json.dumps(error_chunk)}\n\n'
            yield 'data: [DONE]\n\n'
            return

        contents = _build_gemini_contents(history, user_message)
        payload = _gemini_payload(contents)

        for model_name in GEMINI_CANDIDATE_MODELS:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_name}:streamGenerateContent?key={api_key}&alt=sse"
            )
            try:
                with requests.post(
                    url, json=payload,
                    headers={'Content-Type': 'application/json'},
                    stream=True, timeout=15
                ) as response:
                    if response.status_code == 200:
                        has_data = False
                        for line in response.iter_lines():
                            if line:
                                decoded = line.decode('utf-8')
                                if decoded.startswith('data:'):
                                    has_data = True
                                yield decoded + '\n\n'
                        if has_data:
                            return  # success — stop trying other models
            except Exception:
                continue

        # All models failed — stream a clean error
        error_chunk = {
            "candidates": [{"content": {"parts": [{"text": (
                "I'm having trouble connecting right now. Please try again in a moment."
            )}]}}]
        }
        yield f'data: {json.dumps(error_chunk)}\n\n'
        yield 'data: [DONE]\n\n'

    return Response(stream_with_context(generate()), mimetype='text/event-stream')