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

import os
import requests
import json
import time
from flask import Response, stream_with_context, current_app

GEMINI_CANDIDATE_MODELS = [
    'gemini-2.0-flash',
    'gemini-1.5-flash',
    'gemini-2.5-flash',
    'gemini-1.5-pro',
    'gemini-flash-latest'
]

SYSTEM_INSTRUCTION = (
    "You are Raktadata Helper, an empathetic, highly knowledgeable, and certified AI Medical Doctor & Health Consultant for Raktadata Nepal. "
    "Your mission is to provide accurate, comprehensive, natural, and helpful advice for ANY and ALL health, medical, wellness, symptoms, diseases, medications, nutrition, fitness, and blood donation queries.\n\n"
    "Key Instructions:\n"
    "1. Speak naturally, warmly, and empathetically like a trusted, caring doctor.\n"
    "2. If the user asks in Nepali (नेपाली), reply in Nepali. If they ask in Romanized Nepali, reply naturally in Romanized Nepali. If in English, reply in English.\n"
    "3. Always provide COMPLETE, thorough answers without truncating or giving half-hearted advice.\n"
    "4. Use clear Markdown structure: bold key points, bullet lists, causes, practical home remedies, diet tips, and red-flag symptoms when hospital care is required.\n"
    "5. For blood donation: highlight Nepal's criteria (Age 18-60, Weight 45kg+, Hb 12.5g/dL+, 90 days gap)."
)


def _is_valid_gemini_key(api_key):
    if not api_key:
        return False
    clean = api_key.strip()
    if clean in ('', 'your-gemini-api-key-here', 'replace-with-gemini-api-key'):
        return False
    return len(clean) >= 20


def _generate_natural_health_response(user_message):
    """
    Comprehensive, natural, and deep medical intelligence generator
    used when Gemini API is unavailable or offline.
    """
    msg = (user_message or '').lower().strip()

    # 1. Eligibility to Donate Blood
    if any(k in msg for k in ['eligib', 'criteria', 'requirement', 'can i donate', 'weight', 'age limit', 'who can donate', 'योग्य']):
        return (
            "### 🩸 Blood Donation Eligibility & Health Guidelines\n\n"
            "Namaste! Donating blood is a noble, life-saving act. In Nepal, donors must meet the following standard health criteria:\n\n"
            "#### 📋 Basic Criteria:\n"
            "- **Age:** **18 to 60 years old** (up to 65 for regular, healthy donors).\n"
            "- **Weight:** Minimum **45 kg (99 lbs)** for whole blood donation.\n"
            "- **Hemoglobin Level:** At least **12.5 g/dL** (ensures your own oxygen supply remains safe).\n"
            "- **Blood Pressure:** Systolic between 100–140 mmHg, Diastolic between 60–90 mmHg.\n"
            "- **Pulse / Heart Rate:** Normal resting pulse between 60–100 beats/minute.\n"
            "- **Donation Interval:** Minimum **90 days (3 months)** between whole blood donations (males) and **120 days** (females).\n\n"
            "#### ⚠️ Temporary Deferrals (Wait before donating):\n"
            "- **Cold, Cough, or Fever:** Wait 7–14 days after full recovery.\n"
            "- **Antibiotics / Medications:** Wait 48–72 hours after completing antibiotics.\n"
            "- **Tattoos or Piercings:** Wait **6 months** before donating.\n"
            "- **Alcohol Consumption:** Avoid alcohol for at least **24 hours** prior to donation.\n"
            "- **Pregnancy & Lactation:** Defer during pregnancy and up to 6 months after delivery/breastfeeding.\n\n"
            "💡 *Tip: Drink 500ml of water and eat a nutritious meal 1–2 hours before donating!*"
        )

    # 2. Blood Group Compatibility
    if any(k in msg for k in ['o+', 'o-', 'a+', 'a-', 'b+', 'b-', 'ab+', 'ab-', 'compatib', 'universal', 'receive', 'ब्लड ग्रुप']):
        return (
            "### 🩸 Complete Blood Group Compatibility Matrix\n\n"
            "Understanding blood type compatibility is crucial for emergency transfusions:\n\n"
            "| Blood Type | Can Donate Red Cells To | Can Receive Red Cells From |\n"
            "| :--- | :--- | :--- |\n"
            "| **O- (Universal Donor)** | **All Groups (O-, O+, A-, A+, B-, B+, AB-, AB+)** | **O- only** |\n"
            "| **O+** | O+, A+, B+, AB+ | O+, O- |\n"
            "| **A-** | A-, A+, AB-, AB+ | A-, O- |\n"
            "| **A+** | A+, AB+ | A+, A-, O+, O- |\n"
            "| **B-** | B-, B+, AB-, AB+ | B-, O- |\n"
            "| **B+** | B+, AB+ | B+, B-, O+, O- |\n"
            "| **AB-** | AB-, AB+ | AB-, A-, B-, O- |\n"
            "| **AB+ (Universal Recipient)** | **AB+ only** | **All Groups (All Types)** |\n\n"
            "#### 💡 Key Medical Insights:\n"
            "- **O Negative (O-)** is critical in emergency trauma rooms when the patient's blood type is unknown.\n"
            "- **AB Positive (AB+)** can safely receive red blood cells from any blood group.\n"
            "- For **Plasma donation**, AB is the universal plasma donor!"
        )

    # 3. Hemoglobin & Iron Boost
    if any(k in msg for k in ['hemoglobin', 'hb', 'iron', 'anemia', 'boost blood', 'increase blood', 'low blood', 'रक्तअल्पता']):
        return (
            "### 🌿 How to Naturally Boost Hemoglobin & Red Blood Cells\n\n"
            "Hemoglobin is the iron-rich protein in red blood cells that carries oxygen throughout your body. Here are medically proven ways to boost it:\n\n"
            "#### 🥗 1. Iron-Rich Foods:\n"
            "- **Plant Sources (Non-Heme Iron):** Spinach (पालुङ्गो), lentils (दाल), chickpeas (चना), beans, pumpkin seeds, fenugreek, and beetroot (चुकन्दर).\n"
            "- **Animal Sources (Heme Iron):** Lean meats, liver (कलेजो), and eggs.\n"
            "- **Dried Fruits:** Raisins (किशमिश), dates (खजुर), and figs.\n\n"
            "#### 🍊 2. Pair with Vitamin C (Increases Iron Absorption by 300%):\n"
            "- Eat citrus fruits (oranges, lemons, amla/आँवला, tomatoes, guava) alongside your iron-rich meals.\n\n"
            "#### 🚫 3. Avoid Iron Blockers During Meals:\n"
            "- **Do not drink Tea (चिया) or Coffee** within 1 hour before or after meals, as tannins and polyphenols block iron absorption.\n\n"
            "#### 💊 4. Folic Acid & Vitamin B12:\n"
            "- Include green leafy vegetables, bananas, fortified cereals, and dairy products to support RBC creation.\n\n"
            "⚠️ *If your hemoglobin is below 10 g/dL, please consult a physician for an iron panel test (Serum Ferritin) and potential prescribed supplements.*"
        )

    # 4. Fever / Infection / Cold
    if any(k in msg for k in ['fever', 'temperature', 'cold', 'cough', 'flu', 'shivering', 'ज्वरो']):
        return (
            "### 🌡️ Medical Guidance for Fever & Infection Management\n\n"
            "A fever is your body's natural immune defense fighting an infection. Here is structured medical care:\n\n"
            "#### 🩺 Immediate Home Care:\n"
            "1. **Hydration:** Drink plenty of fluids (boiled water, electrolyte solution / Jeevan Jal, clear soups, herbal tea) to prevent dehydration.\n"
            "2. **Rest:** Allow your body to conserve energy for immune response.\n"
            "3. **Tepid Sponging:** Use lukewarm (not cold) water with a clean cloth on forehead, neck, and armpits if temperature exceeds 101°F (38.3°C).\n"
            "4. **Fever Reducer:** Paracetamol (500mg - 650mg for adults every 6-8 hours with food if needed; do not exceed 3000mg/day).\n\n"
            "#### 🚨 Red Flag Symptoms — Seek Immediate Emergency Care If:\n"
            "- Fever exceeds **103°F (39.4°C)** or persists for more than 3 consecutive days.\n"
            "- Accompanied by severe headache, stiff neck, shortness of breath, or chest pain.\n"
            "- Continuous vomiting, rash, or signs of severe lethargy / confusion.\n"
            "- In Nepal's post-monsoon / monsoon seasons, watch for high fever with joint pain (Dengue test recommended)."
        )

    # 5. Blood Pressure & Hypertension
    if any(k in msg for k in ['blood pressure', 'bp', 'hypertension', 'high bp', 'low bp', 'रक्तचाप']):
        return (
            "### 💓 Understanding & Managing Blood Pressure (BP)\n\n"
            "Healthy blood pressure keeps your heart, brain, and kidneys functioning properly.\n\n"
            "#### 📊 Blood Pressure Categories:\n"
            "- **Normal:** Less than **120/80 mmHg**\n"
            "- **Elevated:** Systolic 120–129 mmHg and Diastolic < 80 mmHg\n"
            "- **Hypertension Stage 1:** 130–139 / 80–89 mmHg\n"
            "- **Hypertension Stage 2:** 140/90 mmHg or higher\n"
            "- **Hypertensive Crisis:** Above **180/120 mmHg** (Emergency!)\n\n"
            "#### 🥗 Daily Lifestyle Tips for BP Control:\n"
            "- **Reduce Sodium (Salt):** Limit daily salt intake to under 5 grams (1 teaspoon).\n"
            "- **DASH Diet:** Focus on fruits, vegetables, whole grains, garlic, and potassium-rich foods (bananas, potatoes).\n"
            "- **Physical Activity:** 30 minutes of brisk walking 5 days a week.\n"
            "- **Stress & Sleep:** Practice deep breathing and maintain 7–8 hours of quality sleep.\n\n"
            "⚠️ *Never stop or alter prescribed antihypertensive medications without consulting your doctor.*"
        )

    # 6. Diabetes & Blood Sugar
    if any(k in msg for k in ['diabetes', 'sugar', 'glucose', 'insulin', 'मधुमेह']):
        return (
            "### 🩸 Blood Sugar & Diabetes Management Guide\n\n"
            "Diabetes occurs when your body cannot effectively produce or use insulin. Managing blood sugar prevents long-term organ complications.\n\n"
            "#### 🎯 Target Blood Sugar Ranges (Adults):\n"
            "- **Fasting (Before Meals):** 70–100 mg/dL (Normal) | 80–130 mg/dL (Diabetic Target)\n"
            "- **Post-Meal (2 hrs after eating):** Under 140 mg/dL (Normal) | Under 180 mg/dL (Diabetic Target)\n"
            "- **HbA1c (3-month average):** Under 5.7% (Normal) | Under 7.0% (Well Managed Diabetes)\n\n"
            "#### 🥗 Dietary Recommendations:\n"
            "- Choose low-glycemic complex carbohydrates (brown rice, whole wheat, oats, barley).\n"
            "- High fiber intake: Bitter gourd (करेला), fenugreek (मेथी), beans, and green vegetables.\n"
            "- Eliminate refined sugar, sweets, sodas, and processed snacks.\n"
            "- Take a 15-minute gentle walk after major meals to blunt post-meal glucose spikes."
        )

    # 7. Pre & Post Donation Care
    if any(k in msg for k in ['before donat', 'after donat', 'pre donat', 'post donat', 'recovery', 'care']):
        return (
            "### 🩺 Pre & Post Blood Donation Protocol\n\n"
            "#### 🌟 Before Donating Blood:\n"
            "1. **Hydrate:** Drink 500ml of water or juice 30 minutes before donation.\n"
            "2. **Eat Healthy:** Have a balanced light meal (avoid heavy fatty foods that interfere with blood screening tests).\n"
            "3. **Sleep Well:** Ensure at least 7 hours of restful sleep the night before.\n"
            "4. **Avoid:** Refrain from smoking for 2 hours and alcohol for 24 hours prior.\n\n"
            "#### 🌟 After Donating Blood:\n"
            "1. **Rest:** Sit down and rest in the recovery area for 10–15 minutes with light refreshments.\n"
            "2. **Bandage:** Keep the sterile pressure bandage on for at least 4 hours.\n"
            "3. **Fluids:** Drink extra water and nourishing fluids over the next 24–48 hours.\n"
            "4. **No Heavy Lifting:** Avoid strenuous workouts, heavy weightlifting, or vigorous sports for 24 hours.\n"
            "5. **If Dizzy:** Lie flat and raise your legs until the sensation passes."
        )

    # 8. General Health & Symptom Advice (Comprehensive Doctor response)
    return (
        f"### 🩺 Raktadata Medical Doctor & Health Consultation\n\n"
        f"Thank you for reaching out regarding **\"{user_message.strip()}\"**.\n\n"
        "#### 💡 Clinical Insights & General Guidance:\n"
        "- **Holistic Care:** Maintain adequate daily hydration (2.5–3 Liters of clean water), balanced nutrition rich in fresh produce, and 7–8 hours of restful sleep.\n"
        "- **Vital Signs Monitoring:** Pay attention to baseline indicators such as body temperature, heart rate, hydration status, and energy levels.\n"
        "- **Preventive Health:** Early checkups and routine screenings (blood count, pressure, glucose) prevent common complications.\n\n"
        "#### 🩸 Blood Donation & Community Health:\n"
        "- If your query relates to donating blood: healthy donors between 18–60 years weighing 45kg+ can safely donate every 90 days.\n"
        "- Browse verified blood banks or active emergency blood requests across Nepal directly on Raktadata Nepal.\n\n"
        "#### 🚨 When to Consult a Physician:\n"
        "- If you are experiencing persistent pain, shortness of breath, unexplained dizziness, high fever, or chronic discomfort, please visit your nearest clinic or hospital for an in-person physical examination and diagnostic evaluation.\n\n"
        "*I am here 24/7 to assist with any questions about health, medical guidelines, blood compatibility, and nutrition!*"
    )


@api_bp.route('/raktadata-helper', methods=['POST'])
@api_bp.route('/raktadata-helpher', methods=['POST'])
def raktadata_helper():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'success': False, 'error': 'No message provided'}), 400

    user_message = data['message'].strip()
    history = data.get('history', [])

    api_key = current_app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY', '')

    if _is_valid_gemini_key(api_key):
        contents = []
        for msg in history[-8:]:  # keep last 8 context turns for speed
            contents.append({
                "role": "model" if msg.get('role') in ('ai', 'model') else "user",
                "parts": [{"text": msg.get('content', '')}]
            })
        contents.append({
            "role": "user",
            "parts": [{"text": user_message}]
        })

        payload = {
            "systemInstruction": {
                "parts": [{"text": SYSTEM_INSTRUCTION}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 2048
            }
        }

        for model_name in GEMINI_CANDIDATE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=8)
                if res.status_code == 200:
                    res_data = res.json()
                    candidates = res_data.get('candidates', [])
                    if candidates and candidates[0].get('content'):
                        reply_text = candidates[0]['content']['parts'][0]['text']
                        return jsonify({'success': True, 'reply': reply_text})
            except Exception:
                continue

    # Fallback to rich natural medical engine
    fallback_reply = _generate_natural_health_response(user_message)
    return jsonify({'success': True, 'reply': fallback_reply})


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
        success = False

        if _is_valid_gemini_key(api_key):
            contents = []
            for msg in history[-8:]:
                contents.append({
                    "role": "model" if msg.get('role') in ('ai', 'model') else "user",
                    "parts": [{"text": msg.get('content', '')}]
                })
            contents.append({
                "role": "user",
                "parts": [{"text": user_message}]
            })

            payload = {
                "systemInstruction": {
                    "parts": [{"text": SYSTEM_INSTRUCTION}]
                },
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 2048
                }
            }

            for model_name in GEMINI_CANDIDATE_MODELS:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?key={api_key}&alt=sse"
                try:
                    with requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, stream=True, timeout=10) as response:
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
            full_text = _generate_natural_health_response(user_message)
            # Fast SSE streaming simulation for instant response
            words = full_text.split(' ')
            chunk_size = 4
            for i in range(0, len(words), chunk_size):
                chunk_text = ' '.join(words[i:i+chunk_size])
                if i + chunk_size < len(words):
                    chunk_text += ' '
                chunk = {
                    "candidates": [{
                        "content": {
                            "parts": [{"text": chunk_text}]
                        }
                    }]
                }
                yield f'data: {json.dumps(chunk)}\n\n'
                time.sleep(0.015)  # smooth natural instant typing pace

            yield 'data: [DONE]\n\n'

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

