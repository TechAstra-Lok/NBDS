from flask import session
import os
from datetime import datetime, timedelta
from datetime import datetime, timezone
from difflib import SequenceMatcher

import math

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, abort, current_app, Response, jsonify
)
from werkzeug.utils import secure_filename
from sqlalchemy import desc, or_
from flask_login import login_required, current_user  # एडमिन सुरक्षाका लागि थपिएको

from app import db
from app.models import (
    Donor, BloodRequest, News, Notice, Advertisement, 
    Contact, SuccessStory, Volunteer, BloodBank, BloodInventory, BloodReservation
)
from app.forms import (
    BloodRequestForm, DonorRegistrationForm, ContactForm, RequestManagementForm,
    DonorLoginForm, VolunteerRegistrationForm, VolunteerLoginForm,
    DonorProfileEditForm, DonationHistoryForm
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user
from app.utils import paginate_query, get_blood_group_stats, rate_limit, generate_qr_code
from app.tasks import alert_matching_donors

try:
    # pyrefly: ignore [missing-import]
    import nepali_datetime
except ImportError:  # pragma: no cover - optional dependency in test/dev environments
    nepali_datetime = None

# ब्लुप्रिन्ट परिभाषा
public_bp = Blueprint('public', __name__)


# ─────────────────────────────────────────────────────────────
#  /health  — UptimeRobot keep-alive endpoint (zero DB overhead)
#  UptimeRobot pings this every 5 min to prevent Render cold-starts
# ─────────────────────────────────────────────────────────────
import time as _time

@public_bp.route('/health')
def health_check():
    return jsonify({
        "status": "ok",
        "message": "Raktadata server active",
        "service": "nepali-blood-donors",
        "timestamp": _time.strftime('%Y-%m-%dT%H:%M:%SZ', _time.gmtime())
    }), 200

ALL_DISTRICTS = [
    'Bhojpur', 'Dhankuta', 'Ilam', 'Jhapa', 'Khotang', 'Morang', 'Okhaldhunga',
    'Panchthar', 'Sankhuwasabha', 'Solukunbu', 'Sunsari', 'Taplejung', 'Terhathum',
    'Udayapur', 'Bara', 'Dhanusha', 'Mahottari', 'Parasi', 'Parsa', 'Rautahat',
    'Sarlahi', 'Saptari', 'Siraha', 'Sindhuli', 'Sindhupalchok', 'Baglung', 'Gorkha',
    'Kaski', 'Lamjung', 'Manang', 'Mustang', 'Myagdi', 'Nawalpur', 'Parbat', 'Syangja',
    'Tanahun', 'Bhaktapur', 'Chitwan', 'Dhading', 'Dolakha', 'Kathmandu',
    'Kavrepalanchok', 'Lalitpur', 'Makwanpur', 'Nuwakot', 'Ramechhap', 'Rasuwa',
    'Arghakhanchi', 'Banke', 'Bardiya', 'Dang', 'Gulmi',
    'Kapilvastu', 'Palpa', 'Pyuthan', 'Rolpa', 'Rupandehi', 'Achham', 'Bajhang',
    'Bajura', 'Baitadi', 'Dadeldhura', 'Darchula', 'Doti', 'Kailali', 'Kanchanpur',
    'Dailekh', 'Dolpa', 'Humla', 'Jajarkot', 'Jumla', 'Kalikot', 'Mugu',
    'Rukum East', 'Rukum West', 'Salyan', 'Surkhet'
]


# ─── AI IMAGE FILTER INTEGRATION (GOOGLE CLOUD VISION) ───
def is_image_safe(image_path):
    """
    गुगल क्लाउड भिजन API प्रयोग गरी तस्बिर सुरक्षित छ कि छैन जाँच गर्ने प्रकार्य।
    यदि गुगल सेट गरिएको छैन भने, सुरक्षाको लागि यो प्रकार्यले पास दिन्छ।
    """
    try:
        # pyrefly: ignore [missing-import]
        from google.cloud import vision
        client = vision.ImageAnnotatorClient()

        with open(image_path, 'rb') as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        response = client.safe_search_detection(image=image)
        safe = response.safe_search_annotation

        # Likelihood levels: UNKNOWN, VERY_UNLIKELY, UNLIKELY, POSSIBLE, LIKELY, VERY_LIKELY
        # POSSIBLE(3), LIKELY(4) वा VERY_LIKELY(5) आएमा असुरक्षित मानिनेछ।
        unsafe_landmarks = [3, 4, 5]
        
        if (safe.adult in unsafe_landmarks or 
            safe.medical in unsafe_landmarks or 
            safe.violence in unsafe_landmarks or 
            safe.racy in unsafe_landmarks):
            return False, "समुदाय निर्देशिका उल्लंघन (नग्नता, अश्लीलता, वा हिंसात्मक सामग्री फेला पर्यो)।"
        
        return True, "Safe"
    except Exception as e:
        # यदि Google Cloud Credentials कन्फिगर गरिएको छैन भने सुरक्षा बाइपास (वैकल्पिक)
        return True, "Skipped"


# ─── AI TEXT VERIFICATION (OPENAI) ───
def is_text_safe(title, content):
    """
    OpenAI API प्रयोग गरी कथाको शीर्षक र विषयवस्तु सुरक्षित/सान्दर्भिक छ कि छैन जाँच गर्ने।
    """
    try:
        import openai
        import json
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return True, "Skipped (No API Key)"
        
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""
        You are a moderation assistant for the 'रक्तदान र रक्तदाता' community website.
        Evaluate the following success story submission for spam, profanity, extreme violence, or completely irrelevant content.
        If it is a legitimate blood donation success story, or a general positive message, approve it.
        Respond strictly in JSON format: {{"is_safe": true/false, "reason": "brief explanation"}}
        
        Title: {title}
        Content: {content}
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        
        result = json.loads(response.choices[0].message.content)
        
        if result.get("is_safe"):
            return True, "Safe"
        else:
            return False, result.get("reason", "Inappropriate content detected.")
            
    except Exception as e:
        return True, f"Skipped (Error: {str(e)})"


# ════════════════════════════════════════════
#   LANGUAGE SWITCHER
# ════════════════════════════════════════════
@public_bp.route('/set-language/<lang>')
def set_language(lang):
    from flask import session
    if lang in ('en', 'ne'):
        session['lang'] = lang
    return redirect(request.referrer or url_for('public.index'))


# ════════════════════════════════════════════
#   SUCCESS STORIES PAGE
# ════════════════════════════════════════════
@public_bp.route('/success-stories', methods=['GET', 'POST'])
@rate_limit(limit=5, window=600, methods=['POST'])  # 5 POST requests per 10 minutes
def success_stories():
    if request.method == 'POST':
        # ─── CSRF टोकन म्यानुअल रूपमा जाँच गर्ने ───
        from flask_wtf.csrf import validate_csrf
        from wtforms.validators import ValidationError
        
        token = request.form.get('csrf_token')
        try:
            validate_csrf(token)
        except ValidationError:
            flash("⚠️ सुरक्षा त्रुटि: CSRF टोकन अमान्य वा प्राप्त भएन। कृपया पुनः प्रयास गर्नुहोस्।", "danger")
            return redirect(url_for('public.success_stories'))
        # ─────────────────────────────────────────────────────────

        author_name = request.form.get('author_name')
        title = request.form.get('title')
        content = request.form.get('content')
        file = request.files.get('story_image')

        if not author_name or not title or not content:
            flash("कृपया सबै आवश्यक क्षेत्रहरू भर्नुहोस्।", "warning")
            return redirect(url_for('public.success_stories'))

        filename = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            upload_folder = os.path.join(current_app.root_path, 'static/uploads/stories')
            os.makedirs(upload_folder, exist_ok=True)
            
            temp_path = os.path.join(upload_folder, filename)
            file.save(temp_path)

            # स्वचालित तस्बिर मध्यस्थता (Automated Image Moderation)
            is_safe, message = is_image_safe(temp_path)
            if not is_safe:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                flash(f"⚠️ चेतावनी: {message}", "danger")
                return redirect(url_for('public.success_stories'))

        # AI Text Moderation
        text_is_safe, text_message = is_text_safe(title, content)
        if not text_is_safe:
            flash(f"⚠️ तपाइँको कथा स्वीकृत भएन: {text_message}", "danger")
            return redirect(url_for('public.success_stories'))

        # डेटाबेसमा सुरक्षित गर्ने
        new_story = SuccessStory(
            # pyrefly: ignore [unexpected-keyword]
            author_name=author_name.strip(),
            # pyrefly: ignore [unexpected-keyword]
            title=title.strip(),
            # pyrefly: ignore [unexpected-keyword]
            content=content.strip(),
            # pyrefly: ignore [unexpected-keyword]
            image_file=filename,
            # pyrefly: ignore [unexpected-keyword]
            social_link='',
            # pyrefly: ignore [unexpected-keyword]
            status='pending',
            # pyrefly: ignore [unexpected-keyword]
            moderation_logs=f"Text Check: {text_message}"
        )
        db.session.add(new_story)
        db.session.commit()
        
        flash("तपाईंको सफलताको कथा सफलतापूर्वक पोस्ट भयो! धन्यवाद।", "success")
        return redirect(url_for('public.success_stories'))

    stories = SuccessStory.query.filter_by(status='approved').order_by(SuccessStory.created_at.desc()).all()
    return render_template('success_stories.html', stories=stories)


# ─── केवल एडमिनका लागि मात्र डिलिट गर्ने राउट (सुरक्षित फिक्स) ───
@public_bp.route('/success-stories/<int:story_id>/delete', methods=['POST'])
@login_required  # अनिवार्य लगइन
def delete_success_story(story_id):
    # प्रयोगकर्ता एडमिन हो कि होइन प्राविधिक पुष्टि गर्ने
    if not getattr(current_user, 'is_admin', False) and getattr(current_user, 'role', '') != 'admin':
        abort(403) # अनुमति नभएमा सिधै ब्लक गर्ने

    story = SuccessStory.query.get_or_404(story_id)
    
    # सर्भरको फोल्डरबाट तस्बिर पनि सफा गर्ने
    if story.image_file:
        image_path = os.path.join(current_app.root_path, 'static/uploads/stories', story.image_file)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass
            
    db.session.delete(story)
    db.session.commit()
    
    flash("सफलताको कथा सफलतापूर्वक डिलिट गरियो।", "danger")
    return redirect(url_for('public.success_stories'))
# ════════════════════════════════════════════
#   BLOOD BANK DIRECTORY
# ════════════════════════════════════════════
@public_bp.route('/blood-banks')
def blood_banks():
    if not BloodBank.query.first():
        from app.seed_blood_banks import seed_blood_banks
        seed_blood_banks()

    query = request.args.get('q', '').strip()
    province = request.args.get('province', '').strip()
    district = request.args.get('district', '').strip()
    emergency_only = request.args.get('emergency_only') == '1'

    banks_query = BloodBank.query.filter_by(is_active=True)

    if province:
        banks_query = banks_query.filter(BloodBank.province.ilike(f'%{province}%'))
    if district:
        banks_query = banks_query.filter(BloodBank.district.ilike(f'%{district}%'))
    if emergency_only:
        banks_query = banks_query.filter((BloodBank.is_emergency_panel == True) | (BloodBank.emergency_available == True))

    if query:
        # Dictionary for English to Nepali mapping for search functionality
        ENG_TO_NEP_MAP = {
            'jhapa': 'झापा', 'morang': 'मोरङ', 'sunsari': 'सुनसरी', 'ilam': 'इलाम',
            'panchthar': 'पाँचथर', 'taplejung': 'ताप्लेजुङ', 'dhankuta': 'धनकुटा',
            'terhathum': 'तेह्रथुम', 'sankhuwasabha': 'संखुवासभा', 'bhojpur': 'भोजपुर',
            'solukhumbu': 'सोलुखुम्बु', 'okhaldhunga': 'ओखलढुङ्गा', 'khotang': 'खोटाङ',
            'udayapur': 'उदयपुर', 'dhanusha': 'धनुषा', 'saptari': 'सप्तरी', 'siraha': 'सिराहा',
            'mahottari': 'महोत्तरी', 'sarlahi': 'सर्लाही', 'rautahat': 'रौतहट', 'bara': 'बारा',
            'parsa': 'पर्सा', 'kathmandu': 'काठमाडौँ', 'lalitpur': 'ललितपुर', 'bhaktapur': 'भक्तपुर',
            'chitwan': 'चितवन', 'kavrepalanchok': 'काभ्रेपलाञ्चोक', 'makwanpur': 'मकवानपुर',
            'dhading': 'धादिङ', 'nuwakot': 'नुवाकोट', 'rasuwa': 'रसुवा', 'sindhupalchowk': 'सिन्धुपाल्चोक',
            'dolakha': 'दोलखा', 'ramechhap': 'रामेछाप', 'sindhuli': 'सिन्धुली', 'kaski': 'कास्की',
            'gorkha': 'गोरखा', 'lamjung': 'लमजुङ', 'tanahun': 'तनहुँ', 'syangja': 'स्याङ्जा',
            'nawalpur': 'नवलपुर', 'myagdi': 'म्याग्दी', 'parbat': 'पर्वत', 'mustang': 'मुस्ताङ',
            'manang': 'मनाङ', 'rupandehi': 'रूपन्देही', 'kapilvastu': 'कपिलवस्तु', 'parasi': 'परासी',
            'dang': 'दाङ', 'banke': 'बाँके', 'bardiya': 'बर्दिया', 'palpa': 'पाल्पा',
            'gulmi': 'गुल्मी', 'arghakhanchi': 'अर्घाखाँची', 'pyuthan': 'प्युठान', 'rolpa': 'रोल्पा',
            'eastern rukum': 'पूर्वी रुकुम', 'surkhet': 'सुर्खेत', 'western rukum': 'पश्चिम रुकुम',
            'salyan': 'सल्यान', 'jajarkot': 'जाजरकोट', 'dailekh': 'दैलेख', 'jumla': 'जुम्ला',
            'kalikot': 'कालिकोट', 'mugu': 'मुगु', 'humla': 'हुम्ला', 'dolpa': 'डोल्पा',
            'kailali': 'कैलाली', 'kanchanpur': 'कञ्चनपुर', 'dadeldhura': 'डडेल्धुरा',
            'doti': 'डोटी', 'achham': 'अछाम', 'baitadi': 'बैतडी', 'darchula': 'दार्चुला',
            'bajhang': 'बझाङ', 'bajura': 'बाजुरा',
            
            'koshi pradesh': 'कोशी प्रदेश', 'koshi': 'कोशी प्रदेश',
            'madhesh pradesh': 'मधेस प्रदेश', 'madhesh': 'मधेस प्रदेश',
            'bagmati pradesh': 'बागमती प्रदेश', 'bagmati': 'बागमती प्रदेश',
            'gandaki pradesh': 'गण्डकी प्रदेश', 'gandaki': 'गण्डकी प्रदेश',
            'lumbini pradesh': 'लुम्बिनी प्रदेश', 'lumbini': 'लुम्बिनी प्रदेश',
            'karnali pradesh': 'कर्णाली प्रदेश', 'karnali': 'कर्णाली प्रदेश',
            'sudurpashchim pradesh': 'सुदूरपश्चिम प्रदेश', 'sudurpashchim': 'सुदूरपश्चिम प्रदेश',
            
            'blood': 'रक्त', 'transfusion': 'सञ्चार', 'service': 'सेवा', 'center': 'केन्द्र',
            'hospital': 'अस्पताल', 'branch': 'शाखा', 'sub branch': 'उपशाखा', 'main': 'मुख्य',
            'provincial': 'प्रादेशिक', 'central': 'केन्द्रीय', 'district': 'जिल्ला',
            'community': 'सामुदायिक', 'unit': 'इकाई', 'red cross': 'रेडक्रस'
        }
        
        # Build search patterns
        query_lower = query.lower()
        patterns = [f'%{query}%']
        
        # If the whole query matches a translation, add it
        if query_lower in ENG_TO_NEP_MAP:
            patterns.append(f'%{ENG_TO_NEP_MAP[query_lower]}%')
        else:
            # Word by word translation attempt
            translated_words = []
            for word in query_lower.split():
                if word in ENG_TO_NEP_MAP:
                    translated_words.append(ENG_TO_NEP_MAP[word])
                else:
                    translated_words.append(word)
            translated_query = ' '.join(translated_words)
            if translated_query != query_lower:
                patterns.append(f'%{translated_query}%')
        
        # Build the OR conditions dynamically
        or_conditions = []
        for pattern in patterns:
            or_conditions.extend([
                BloodBank.name.ilike(pattern),
                BloodBank.display_name.ilike(pattern),
                BloodBank.district.ilike(pattern),
                BloodBank.province.ilike(pattern),
                BloodBank.service_type.ilike(pattern),
                BloodBank.notes.ilike(pattern),
            ])
            
        banks_query = banks_query.filter(or_(*or_conditions))

    blood_banks = banks_query.order_by(BloodBank.province, BloodBank.district, BloodBank.name).all()
    
    # Get all active banks to build the province->districts map
    all_banks = BloodBank.query.filter_by(is_active=True).all()
    provinces_set = set()
    province_districts_map = {}
    
    for b in all_banks:
        if b.province:
            provinces_set.add(b.province)
            if b.province not in province_districts_map:
                province_districts_map[b.province] = set()
            if b.district:
                province_districts_map[b.province].add(b.district)
                
    # Convert sets to sorted lists
    provinces_list = sorted(list(provinces_set))
    for p in province_districts_map:
        province_districts_map[p] = sorted(list(province_districts_map[p]))
        
    districts = db.session.query(BloodBank.district).filter(BloodBank.district.isnot(None), BloodBank.is_active == True).distinct().order_by(BloodBank.district).all()
    
    return render_template(
        'blood_banks.html',
        blood_banks=blood_banks,
        search_query=query,
        province_filter=province,
        district_filter=district,
        emergency_only=emergency_only,
        provinces=provinces_list,
        districts=[value[0] for value in districts if value[0]],
        province_districts_map=province_districts_map
    )

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in kilometers
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat/2) * math.sin(d_lat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(d_lon/2) * math.sin(d_lon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

@public_bp.route('/api/nearest-blood-bank')
def nearest_blood_bank():
    try:
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid coordinates'}), 400

    banks = BloodBank.query.filter(BloodBank.latitude.isnot(None), BloodBank.longitude.isnot(None), BloodBank.is_active == True).all()
    
    if not banks:
        return jsonify({'error': 'No blood banks with coordinates found'}), 404

    nearest = None
    min_dist = float('inf')
    
    for bank in banks:
        dist = haversine(lat, lng, bank.latitude, bank.longitude)
        if dist < min_dist:
            min_dist = dist
            nearest = bank
            
    if nearest:
        return jsonify({
            'id': nearest.id,
            'name': nearest.display_name or nearest.name,
            'distance_km': round(min_dist, 1),
            'address': f"{nearest.district or ''}, {nearest.province or ''}".strip(', '),
            'phone': nearest.contact_number or nearest.phone or '',
            'url': url_for('public.blood_bank_detail', bank_id=nearest.id),
            'maps_url': nearest.google_maps_url
        })
    return jsonify({'error': 'No blood bank found'}), 404


@public_bp.route('/blood-banks/<int:bank_id>')
def blood_bank_detail(bank_id):
    blood_bank = BloodBank.query.get_or_404(bank_id)
    
    # Load from public cache to prevent cross-database tenant engine runtime errors
    from app.models import PublicBloodBankCache
    cache = PublicBloodBankCache.query.filter_by(blood_bank_id=bank_id).first()
    inventory_items = []
    if cache:
        group_mapping = {
            'A+': cache.a_pos, 'A-': cache.a_neg,
            'B+': cache.b_pos, 'B-': cache.b_neg,
            'AB+': cache.ab_pos, 'AB-': cache.ab_neg,
            'O+': cache.o_pos, 'O-': cache.o_neg
        }
        for group, val in group_mapping.items():
            if val > 0:
                inventory_items.append({
                    'blood_group': group,
                    'component': 'Any / Whole Blood',
                    'available_units': val,
                    'units_reserved': 0
                })
    
    # Resolve tenant DB and fetch staff members
    staff_members = []
    if blood_bank.tenant_id:
        try:
            from app.services.tenant_service import TenantResolutionService
            from app.models import StaffMember
            TenantResolutionService.resolve_tenant(blood_bank.tenant_id)
            staff_members = StaffMember.query.filter_by(is_active=True).order_by(StaffMember.created_at.desc()).all()
        except Exception:
            pass  # Tenant not provisioned or inactive — just skip staff
                
    return render_template('blood_bank_detail.html', blood_bank=blood_bank, inventory_items=inventory_items, staff_members=staff_members)


@public_bp.route('/blood-banks/<int:bank_id>/reserve', methods=['GET', 'POST'])
def reserve_blood(bank_id):
    blood_bank = BloodBank.query.get_or_404(bank_id)
    if request.method == 'POST':
        hospital_name = request.form.get('hospital_name', '').strip()
        patient_name = request.form.get('patient_name', '').strip()
        blood_group = request.form.get('blood_group', '').strip()
        component = request.form.get('component', 'Whole Blood').strip() or 'Whole Blood'
        units = int(request.form.get('units', 1) or 1)
        priority = request.form.get('priority', 'normal').strip() or 'normal'
        paper_file = request.files.get('hospital_paper')

        if not hospital_name or not patient_name or not blood_group or not paper_file or not paper_file.filename:
            flash('All required fields, including the Hospital Request Paper, must be provided.', 'danger')
            return redirect(url_for('public.reserve_blood', bank_id=blood_bank.id))

        if blood_bank.tenant_id:
            try:
                from app.services.tenant_service import TenantResolutionService
                TenantResolutionService.resolve_tenant(blood_bank.tenant_id)
            except Exception:
                flash('This blood bank is currently inactive and cannot accept reservations.', 'danger')
                return redirect(url_for('public.blood_bank_detail', bank_id=blood_bank.id))
        else:
            flash('This blood bank is currently not provisioned to accept reservations.', 'danger')
            return redirect(url_for('public.blood_bank_detail', bank_id=blood_bank.id))

        reservation = BloodReservation(
            blood_bank_id=blood_bank.id,
            hospital_name=hospital_name,
            patient_name=patient_name,
            blood_group=blood_group,
            component=component,
            units=units,
            priority=priority,
            status='pending',
        )
        db.session.add(reservation)
        db.session.flush()
        
        import os
        import uuid
        ext = paper_file.filename.rsplit('.', 1)[-1].lower() if '.' in paper_file.filename else 'jpg'
        filename = f"resv_{reservation.id}_{uuid.uuid4().hex[:8]}.{ext}"
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'reservation_papers')
        os.makedirs(upload_dir, exist_ok=True)
        saved_path = os.path.join(upload_dir, filename)
        paper_file.save(saved_path)
        reservation.hospital_paper_file = filename

        reservation.qr_code = generate_qr_code('reservation', reservation.id)
        db.session.commit()
        flash('Reservation request submitted successfully.', 'success')
        return redirect(url_for('public.blood_bank_detail', bank_id=blood_bank.id))

    from app.models import PublicBloodBankCache
    cache = PublicBloodBankCache.query.filter_by(blood_bank_id=bank_id).first()
    inventory_items = []
    if cache:
        group_mapping = {
            'A+': cache.a_pos, 'A-': cache.a_neg,
            'B+': cache.b_pos, 'B-': cache.b_neg,
            'AB+': cache.ab_pos, 'AB-': cache.ab_neg,
            'O+': cache.o_pos, 'O-': cache.o_neg
        }
        for group, val in group_mapping.items():
            if val > 0:
                inventory_items.append({
                    'blood_group': group,
                    'component': 'Any / Whole Blood',
                    'available_units': val,
                    'units_reserved': 0
                })

    return render_template('reserve_blood.html', blood_bank=blood_bank, inventory_items=inventory_items)


# ════════════════════════════════════════════
#    HOMEPAGE
# ════════════════════════════════════════════
@public_bp.route('/')
def index():
    active_requests = BloodRequest.query.filter_by(status='active').order_by(
        BloodRequest.is_emergency.desc(),
        desc(BloodRequest.created_at)
    ).limit(6).all()
    
    total_donors    = Donor.query.count()
    avail_donors    = Donor.query.filter_by(availability_status='available').count()
    total_requests  = BloodRequest.query.count()
    fulfilled       = BloodRequest.query.filter_by(status='fulfilled').count()
    
    bg_stats = get_blood_group_stats()
    
    latest_news = News.query.filter_by(is_published=True).order_by(
        desc(News.created_at)
    ).limit(3).all()
    
    # Updated to timezone-aware UTC check
    now = datetime.now(timezone.utc)
    latest_notices = Notice.query.filter(
        Notice.is_active == True,
        or_(Notice.expiry_date == None, Notice.expiry_date >= now)
    ).order_by(Notice.priority.desc(), desc(Notice.published_date)).limit(5).all()
    
    stories = News.query.filter_by(
        category='story', is_published=True
    ).order_by(desc(News.created_at)).limit(3).all()
    
    banner_ads = Advertisement.query.filter(
        Advertisement.is_active == True,
        Advertisement.ad_type == 'banner',
        or_(Advertisement.end_date == None, Advertisement.end_date >= now)
    ).all()
    
    if banner_ads:
        for ad in banner_ads:
            ad.impressions += 1
        db.session.commit()
    
    return render_template('index.html',
        active_requests=active_requests,
        total_donors=total_donors,
        avail_donors=avail_donors,
        total_requests=total_requests,
        fulfilled=fulfilled,
        bg_stats=bg_stats,
        latest_news=latest_news,
        latest_notices=latest_notices,
        stories=stories,
        banner_ads=banner_ads,
    )

# ════════════════════════════════════════════
#   BLOOD REQUESTS
# ════════════════════════════════════════════
@public_bp.route('/blood-request', methods=['GET', 'POST'])
@rate_limit(limit=5, window=600)  # 5 requests per 10 minutes
def blood_request_form():
    form = BloodRequestForm()
    
    if form.validate_on_submit():
        ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
        normalized_new = ''.join(e for e in form.patient_name.data.lower() if e.isalnum())
        recent = BloodRequest.query.filter(BloodRequest.created_at >= ten_min_ago).all()
        for r in recent:
            normalized_existing = ''.join(e for e in (r.patient_name or '').lower() if e.isalnum())
            if not normalized_existing:
                continue
            ratio = SequenceMatcher(None, normalized_new, normalized_existing).ratio()
            if ratio >= 0.85:
                flash('A similar blood request for this patient was submitted recently. Please wait 10 minutes before submitting another request for the same patient.', 'warning')
                return redirect(url_for('public.blood_request_board'))

        req = BloodRequest(
            patient_name    = form.patient_name.data.strip(),
            request_message = form.request_message.data.strip() if form.request_message.data else "",
            case_details    = form.case_details.data.strip(),
            blood_group     = form.blood_group.data,
            required_component = form.required_component.data or 'Whole Blood',
            units_needed    = form.units_needed.data,
            hospital        = form.hospital.data.strip(),
            province        = form.province.data or "",
            district        = form.district.data.strip() if form.district.data else "",
            local_level     = form.local_level.data.strip() if form.local_level.data else "",
            ward_no         = form.ward_no.data.strip() if form.ward_no.data else "",
            contact_person  = form.contact_person.data.strip(),
            contact_number  = form.contact_number.data.strip(),
            alt_number      = form.alt_number.data.strip() if form.alt_number.data else "",
            pin             = form.pin.data.strip(),
            is_emergency    = form.is_emergency.data,
        )
        db.session.add(req)
        db.session.flush()  # get req.id before commit

        # Handle hospital paper upload
        if form.hospital_paper.data:
            paper_file = form.hospital_paper.data
            from werkzeug.utils import secure_filename
            import uuid
            ext = paper_file.filename.rsplit('.', 1)[-1].lower()
            filename = f"req_{req.id}_{uuid.uuid4().hex[:8]}.{ext}"
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'request_papers')
            os.makedirs(upload_dir, exist_ok=True)
            saved_path = os.path.join(upload_dir, filename)
            paper_file.save(saved_path)
            req.hospital_paper_file = filename
            
            # Verify the uploaded paper
            from app.services.document_verification import verify_blood_request_paper
            verified = verify_blood_request_paper(saved_path)
            req.hospital_paper_verified = verified

        db.session.commit()
        
        # Trigger Intelligent Donor Alert
        try:
            alert_matching_donors(current_app._get_current_object(), req.id)
        except Exception as e:
            current_app.logger.error(f"Error alerting donors: {e}")
        
        flash(f'✅ Blood request submitted! Request ID: {req.request_id}. Donors will be notified.', 'success')
        return redirect(url_for('public.blood_request_board'))

    if request.method == 'POST':
        flash('Please fix the errors in the blood request form and resubmit.', 'danger')
    
    return render_template('blood_request_form.html', form=form)


@public_bp.route('/blood-requests')
def blood_request_board():
    page        = request.args.get('page', 1, type=int)
    blood_group = request.args.get('blood_group', '')
    status      = request.args.get('status', 'active')
    emergency   = request.args.get('emergency', '')
    
    query = BloodRequest.query
    
    if blood_group:
        query = query.filter_by(blood_group=blood_group)
    if status:
        query = query.filter_by(status=status)
    if emergency:
        query = query.filter_by(is_emergency=True)
    
    query = query.order_by(
        BloodRequest.is_emergency.desc(),
        desc(BloodRequest.created_at)
    )
    
    pagination  = paginate_query(query, page, current_app.config['REQUESTS_PER_PAGE'])
    blood_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    
    active_count    = BloodRequest.query.filter_by(status='active').count()
    fulfilled_count = BloodRequest.query.filter_by(status='fulfilled').count()
    closed_count    = BloodRequest.query.filter_by(status='closed').count()
    
    return render_template('blood_request_board.html',
        pagination=pagination,
        blood_groups=blood_groups,
        selected_bg=blood_group,
        selected_status=status,
        active_count=active_count,
        fulfilled_count=fulfilled_count,
        closed_count=closed_count,
    )


@public_bp.route('/blood-requests/<request_ref>')
def single_blood_request(request_ref):
    req = None
    if request_ref.isdigit():
        req = BloodRequest.query.get(int(request_ref))
    if not req:
        req = BloodRequest.query.filter_by(request_id=request_ref).first()
    if not req:
        # Search by partial request_id or fail with 404
        req = BloodRequest.query.filter(BloodRequest.request_id.ilike(f"%{request_ref}%")).first_or_404()
    
    return render_template('blood_request_detail.html', req=req)


@public_bp.route('/blood-requests/manage', methods=['GET', 'POST'])
def manage_blood_request():
    form = RequestManagementForm()
    request_record = None

    if form.validate_on_submit():
        request_record = BloodRequest.query.filter_by(
            request_id=form.request_id.data.strip(),
            pin=form.pin.data.strip()
        ).first()

        if not request_record:
            flash('No matching blood request found. Please verify Request ID and PIN.', 'danger')

    return render_template('blood_request_manage.html', form=form, request_record=request_record)


@public_bp.route('/blood-requests/<int:id>/update-status', methods=['POST'])
def public_update_request_status(id):
    request_record = BloodRequest.query.get_or_404(id)
    request_id = request.form.get('request_id', '').strip()
    pin = request.form.get('pin', '').strip()
    action = request.form.get('action', '').strip()

    if not request_id or not pin or request_record.request_id != request_id or request_record.pin != pin:
        flash('Authorization failed. Please confirm your request details (ID and PIN).', 'danger')
        return redirect(url_for('public.manage_blood_request'))

    if action == 'urgent':
        request_record.is_emergency = True
        flash('Request marked as URGENT.', 'success')
    elif action in ('fulfilled', 'cancelled', 'managed_from_other_source'):
        if request_record.status == action:
            flash(f'Request is already {action.replace("_", " ")}.', 'info')
        else:
            request_record.status = action
            if action == 'fulfilled':
                request_record.fulfilled_date = datetime.utcnow()
            flash(f'Your request has been marked as {action.replace("_", " ")}.', 'success')
    else:
        flash('Invalid action selected.', 'danger')

    db.session.commit()
    return redirect(url_for('public.manage_blood_request'))


# ════════════════════════════════════════════
#   FIND DONORS
# ════════════════════════════════════════════
@public_bp.route('/find-donors')
def find_donors():
    page        = request.args.get('page', 1, type=int)
    blood_group = request.args.get('blood_group', '')
    district    = request.args.get('district', '')
    local_level = request.args.get('local_level', '')
    donor_type  = request.args.get('donor_type', '')
    query = Donor.query.filter_by(is_active=True, is_public=True)
    
    if blood_group:
        query = query.filter_by(blood_group=blood_group)
    if district:
        query = query.filter(Donor.curr_district.ilike(f'%{district}%'))
    if local_level:
        query = query.filter(Donor.curr_local_level.ilike(f'%{local_level}%'))
    if donor_type:
        query = query.filter_by(donor_type=donor_type)
    
    query = query.order_by(
        (Donor.availability_status == 'available').desc(),
        desc(Donor.created_at)
    )
    
    pagination = paginate_query(query, page, current_app.config['DONORS_PER_PAGE'])
    
    total_donors = Donor.query.count()
    avail_donors = Donor.query.filter_by(availability_status='available').count()
    blood_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    districts = ALL_DISTRICTS
    
    return render_template('find_donors.html',
        pagination=pagination,
        blood_groups=blood_groups,
        districts=districts,
        selected_bg=blood_group,
        selected_district=district,
        selected_local_level=local_level,
        selected_type=donor_type,
        total_donors=total_donors,
        avail_donors=avail_donors,
    )


# ════════════════════════════════════════════
#   DONOR REGISTRATION
# ════════════════════════════════════════════
@public_bp.route('/become-donor', methods=['GET', 'POST'])
@rate_limit(limit=10, window=3600)  # 10 registrations per hour
def become_donor():
    form = DonorRegistrationForm()
    
    if form.validate_on_submit():
        ad_date = form.last_donation_date.data
        if ad_date and ad_date.year > 2050:
            bs_date = nepali_datetime.date(ad_date.year, ad_date.month, ad_date.day)
            ad_date = bs_date.to_datetime_date()

        donor = Donor(
            full_name           = form.full_name.data.strip(),
            email               = form.email.data.strip(),
            pin_hash            = generate_password_hash(form.pin.data),
            age                 = form.age.data,
            weight              = form.weight.data,
            perm_province       = form.perm_province.data or "",
            perm_district       = form.perm_district.data.strip() if form.perm_district.data else "",
            perm_local_level    = form.perm_local_level.data.strip() if form.perm_local_level.data else "",
            perm_ward           = form.perm_ward.data.strip() if form.perm_ward.data else "",
            perm_tole           = form.perm_tole.data.strip() if form.perm_tole.data else "",
            curr_province       = form.curr_province.data,
            curr_district       = form.curr_district.data.strip(),
            curr_local_level    = form.curr_local_level.data.strip() if form.curr_local_level.data else "",
            curr_ward           = form.curr_ward.data.strip() if form.curr_ward.data else "",
            curr_tole           = form.curr_tole.data.strip() if form.curr_tole.data else "",
            phone1              = form.phone1.data.strip(),
            phone2              = form.phone2.data.strip() if form.phone2.data else "",
            blood_group         = form.blood_group.data,
            last_donation_date  = ad_date,
            donation_times      = form.donation_times.data or 0,
            donor_type          = form.donor_type.data,
            social_link         = form.social_link.data.strip() if form.social_link.data else "",
        )
        
        # Calculate initial availability
        donor.recalculate_and_save()
        
        db.session.add(donor)
        db.session.commit()
        
        login_user(donor)
        flash(f'🎉 Registration successful! Your Donor ID: {donor.donor_id}.', 'success')
        return redirect(url_for('public.donor_profile', donor_id=donor.donor_id))
    
    return render_template('become_donor.html', form=form, districts=ALL_DISTRICTS)


@public_bp.route('/donor/login', methods=['GET', 'POST'])
@rate_limit(limit=10, window=60)  # 10 attempts per minute
def donor_login():
    if current_user.is_authenticated and hasattr(current_user, 'donor_id'):
        return redirect(url_for('public.donor_profile', donor_id=current_user.donor_id))
        
    form = DonorLoginForm()
    if form.validate_on_submit():
        login_val = form.login_id.data.strip()
        
        # Check if login_val is phone or email
        # To normalize phone, reuse the normalize logic if it looks like a phone
        normalized_phone = login_val
        if login_val.isdigit() or (login_val.startswith('+') and login_val[1:].isdigit()):
            from app.forms import _normalize_nepal_mobile
            normalized_phone = _normalize_nepal_mobile(login_val)
        
        from sqlalchemy import or_
        donor = Donor.query.filter(or_(Donor.phone1 == normalized_phone, Donor.email == login_val)).first()
        
        if donor and check_password_hash(donor.pin_hash, form.pin.data):
            session.permanent = True
            login_user(donor, remember=True)
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('public.donor_profile', donor_id=donor.donor_id))
        else:
            flash('Login Unsuccessful. Please check your mobile number / email and PIN.', 'danger')
            
    return render_template('auth/donor_login.html', form=form)


@public_bp.route('/become-volunteer', methods=['GET', 'POST'])
@rate_limit(limit=10, window=3600)  # 10 registrations per hour
def become_volunteer():
    form = VolunteerRegistrationForm()
    
    if form.validate_on_submit():
        volunteer = Volunteer(
            # pyrefly: ignore [unexpected-keyword]
            full_name           = form.full_name.data.strip(),
            # pyrefly: ignore [unexpected-keyword]
            email               = form.email.data.strip(),
            # pyrefly: ignore [unexpected-keyword]
            pin_hash            = generate_password_hash(form.pin.data),
            # pyrefly: ignore [unexpected-keyword]
            phone1              = form.phone1.data.strip(),
            # pyrefly: ignore [unexpected-keyword]
            phone2              = form.phone2.data.strip() if form.phone2.data else None,
            # pyrefly: ignore [unexpected-keyword]
            designation         = form.designation.data,
            # pyrefly: ignore [unexpected-keyword]
            working_field       = form.working_field.data.strip() if form.working_field.data else None,
            # pyrefly: ignore [unexpected-keyword]
            perm_address        = form.perm_address.data.strip(),
            # pyrefly: ignore [unexpected-keyword]
            curr_address        = form.curr_address.data.strip(),
            # pyrefly: ignore [unexpected-keyword]
            curr_district       = form.curr_district.data.strip(),
            # pyrefly: ignore [unexpected-keyword]
            availability_time   = form.availability_time.data.strip() if form.availability_time.data else None
        )
        db.session.add(volunteer)
        db.session.commit()
        
        login_user(volunteer)
        flash(f'🎉 Thank you for registering as a Volunteer! Your account is pending approval.', 'success')
        return redirect(url_for('public.index'))
    
    return render_template('become_volunteer.html', form=form, districts=ALL_DISTRICTS)


@public_bp.route('/volunteer/login', methods=['GET', 'POST'])
@rate_limit(limit=10, window=60)  # 10 attempts per minute
def volunteer_login():
    if current_user.is_authenticated and hasattr(current_user, 'volunteer_id'):
        return redirect(url_for('public.index'))
        
    form = VolunteerLoginForm()
    if form.validate_on_submit():
        volunteer = Volunteer.query.filter_by(phone1=form.phone1.data.strip()).first()
        if volunteer and check_password_hash(volunteer.pin_hash, form.pin.data):
            login_user(volunteer, remember=form.remember.data)
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('public.index'))
        else:
            flash('Login Unsuccessful. Please check mobile number and PIN.', 'danger')
            
    return render_template('auth/volunteer_login.html', form=form)


@public_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('public.index'))


@public_bp.route('/donor/<string:donor_id>', methods=['GET', 'POST'])
def donor_profile(donor_id):
    donor = Donor.query.filter_by(donor_id=donor_id).first_or_404()
    
    # Recalculate status just in case (fast)
    donor.recalculate_and_save()
    db.session.commit()
    
    profile_form = DonorProfileEditForm(obj=donor)
    
    # Pre-fill preferences if they exist
    if donor.preference:
        profile_form.email_alerts.data = donor.preference.email_alerts
        profile_form.sms_alerts.data = donor.preference.sms_alerts
        profile_form.in_app_alerts.data = donor.preference.in_app_alerts
    else:
        # Default True if no preference object
        profile_form.email_alerts.data = True
        profile_form.sms_alerts.data = True
        profile_form.in_app_alerts.data = True
        
    donation_form = DonationHistoryForm()
    
    is_owner = current_user.is_authenticated and getattr(current_user, 'donor_id', None) == donor.donor_id
    
    if is_owner and request.method == 'POST':
        if 'profile_submit' in request.form and profile_form.validate_on_submit():
            profile_form.populate_obj(donor)
            
            # Save Notification Preferences
            from app.models import DonorNotificationPreference
            if not donor.preference:
                donor.preference = DonorNotificationPreference(donor_id=donor.id)
            donor.preference.email_alerts = profile_form.email_alerts.data
            donor.preference.sms_alerts = profile_form.sms_alerts.data
            donor.preference.in_app_alerts = profile_form.in_app_alerts.data
            
            donor.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Your profile has been updated.', 'success')
            return redirect(url_for('public.donor_profile', donor_id=donor_id))
            
        if 'donation_submit' in request.form and donation_form.validate_on_submit():
            from app.models import DonorDonationHistory
            
            # Check if this date already exists for this donor (basic deduplication)
            existing = DonorDonationHistory.query.filter_by(
                donor_id=donor.id, 
                donation_date=donation_form.donation_date.data
            ).first()
            
            if existing:
                flash(f"A donation record already exists for {donation_form.donation_date.data}.", 'warning')
            else:
                new_donation = DonorDonationHistory(
                    donor_id=donor.id,
                    donation_date=donation_form.donation_date.data,
                    donation_type=donation_form.donation_type.data,
                    location=donation_form.location.data.strip() if donation_form.location.data else "",
                    units=donation_form.units.data,
                    notes=donation_form.notes.data.strip() if donation_form.notes.data else "",
                    created_by='donor'
                )
                db.session.add(new_donation)
                
                # Update donor summary fields
                if not donor.last_donation_date or new_donation.donation_date > donor.last_donation_date:
                    donor.last_donation_date = new_donation.donation_date
                
                donor.donation_times = (donor.donation_times or 0) + 1
                donor.total_donations = (donor.total_donations or 0) + 1
                
                donor.recalculate_and_save()
                db.session.commit()
                flash('Donation record added successfully!', 'success')
            return redirect(url_for('public.donor_profile', donor_id=donor_id))
            
    # Fetch donation history descending
    history = []
    if is_owner or current_user.is_authenticated and getattr(current_user, 'role', None) in ['admin', 'superadmin', 'moderator']:
        from app.models import DonorDonationHistory
        history = DonorDonationHistory.query.filter_by(donor_id=donor.id).order_by(desc(DonorDonationHistory.donation_date)).all()
        
    return render_template('donor_profile.html', 
                           donor=donor, 
                           profile_form=profile_form, 
                           donation_form=donation_form,
                           history=history,
                           is_owner=is_owner)


@public_bp.route('/api/donor/<string:donor_id>/availability')
def donor_availability_api(donor_id):
    """Public API endpoint to check a donor's availability status."""
    donor = Donor.query.filter_by(donor_id=donor_id).first()
    if not donor:
        return jsonify({'error': 'Donor not found'}), 404
        
    status, after_date = donor.calculate_availability()
    return jsonify({
        'status': status,
        'status_display': donor.availability_display,
        'available_after': after_date.isoformat() if after_date else None
    })



from datetime import datetime
from sqlalchemy import or_, desc
from flask import request, current_app, render_template

# ════════════════════════════════════════════
#    NEWS & NOTICES
# ════════════════════════════════════════════
@public_bp.route('/news')
def news_list():
    page     = request.args.get('page', 1, type=int)
    category = request.args.get('category', '').strip().lower()
    
    # Query News Table
    query = News.query.filter_by(is_published=True)
    if category and category != 'notice':
        query = query.filter_by(category=category)
    
    pagination = paginate_query(
        query.order_by(desc(News.created_at)),
        page, 
        current_app.config.get('NEWS_PER_PAGE', 9)
    )
    
    # Fetch Active Notices (Naive UTC timestamp prevents SQLAlchemy TypeError)
    now = datetime.utcnow()
    active_notices = Notice.query.filter(
        Notice.is_active == True,
        or_(Notice.expiry_date == None, Notice.expiry_date >= now)
    ).order_by(
        Notice.priority.desc(), 
        desc(Notice.published_date)
    ).all()
    
    categories = ['news', 'event', 'program', 'story']
    
    return render_template(
        'news.html',
        pagination=pagination,
        active_notices=active_notices,
        categories=categories,
        selected_category=category
    )
# ════════════════════════════════════════════
#   ABOUT & CONTACT
# ════════════════════════════════════════════
@public_bp.route('/about')
def about():
    return render_template('about.html')


@public_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    
    if form.validate_on_submit():
        msg = Contact(
            # pyrefly: ignore [unexpected-keyword]
            name    = form.name.data.strip(),
            # pyrefly: ignore [unexpected-keyword]
            email   = form.email.data.strip(),
            # pyrefly: ignore [unexpected-keyword]
            phone   = form.phone.data.strip() if form.phone.data else None,
            # pyrefly: ignore [unexpected-keyword]
            subject = form.subject.data.strip(),
            # pyrefly: ignore [unexpected-keyword]
            message = form.message.data.strip(),
        )
        db.session.add(msg)
        db.session.commit()
        
        flash('✅ Your message has been sent! We will respond within 24 hours.', 'success')
        return redirect(url_for('public.contact'))
    
    return render_template('contact.html', form=form)


# ════════════════════════════════════════════
#   DONOR GUIDELINES & FAQ
# ════════════════════════════════════════════
@public_bp.route('/donor-guidelines')
def donor_guidelines():
    return render_template('donor_guidelines.html')


@public_bp.route('/ai-assistant')
def ai_assistant():
    return render_template('ai_assistant.html')


@public_bp.route('/faq')
def faq():
    return render_template('faq.html')


# ════════════════════════════════════════════
#   AD CLICK TRACKING
# ════════════════════════════════════════════
@public_bp.route('/ad/click/<int:ad_id>')
def ad_click(ad_id):
    ad = Advertisement.query.get_or_404(ad_id)
    ad.clicks += 1
    db.session.commit()
    
    if ad.redirect_url:
        return redirect(ad.redirect_url)
    return redirect(url_for('public.index'))


# ════════════════════════════════════════════
#   SEO: SITEMAP & ROBOTS.TXT
# ════════════════════════════════════════════
@public_bp.route('/robots.txt')
def robots():
    content = """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /bloodbank/
Disallow: /api/

Sitemap: https://raktadata.lokeshprasai.com.np/sitemap.xml
"""
    return Response(content, mimetype='text/plain')


@public_bp.route('/sitemap.xml', methods=['GET'])
def sitemap():
    today = datetime.utcnow().date().isoformat()
    pages = [
        (url_for('public.index', _external=True), today, '1.0', 'daily'),
        (url_for('public.find_donors', _external=True), today, '0.9', 'daily'),
        (url_for('public.blood_request_board', _external=True), today, '0.9', 'hourly'),
        (url_for('public.blood_banks', _external=True), today, '0.8', 'weekly'),
        (url_for('public.ai_assistant', _external=True), today, '0.8', 'weekly'),
        (url_for('public.become_donor', _external=True), today, '0.8', 'monthly'),
        (url_for('public.news_list', _external=True), today, '0.8', 'daily'),
        (url_for('public.about', _external=True), today, '0.6', 'monthly'),
        (url_for('public.contact', _external=True), today, '0.6', 'monthly'),
        (url_for('public.faq', _external=True), today, '0.6', 'monthly'),
        (url_for('public.donor_guidelines', _external=True), today, '0.6', 'monthly'),
        (url_for('public.success_stories', _external=True), today, '0.7', 'weekly'),
    ]
    
    try:
        for n in News.query.filter_by(is_published=True).order_by(desc(News.created_at)).limit(50).all():
            lastmod = n.updated_at.date().isoformat() if n.updated_at else n.created_at.date().isoformat()
            pages.append((url_for('public.news_detail', slug=n.slug, _external=True), lastmod, '0.7', 'monthly'))
    except Exception:
        pass

    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for loc, lastmod, prio, freq in pages:
        xml_parts.append('  <url>')
        xml_parts.append(f'    <loc>{loc}</loc>')
        xml_parts.append(f'    <lastmod>{lastmod}</lastmod>')
        xml_parts.append(f'    <changefreq>{freq}</changefreq>')
        xml_parts.append(f'    <priority>{prio}</priority>')
        xml_parts.append('  </url>')
    xml_parts.append('</urlset>')
    
    return Response('\n'.join(xml_parts), mimetype='application/xml')


# ════════════════════════════════════════════
#   GLOBAL SEARCH ENGINE
# ════════════════════════════════════════════
@public_bp.route('/search')
def global_search():
    query = request.args.get('q', '').strip()
    results = {
        'donors': [],
        'requests': [],
        'news': [],
        'notices': []
    }
    
    if query:
        # Search Donors
        donor_query = Donor.query.filter(
            or_(
                Donor.full_name.ilike(f'%{query}%'),
                Donor.blood_group.ilike(f'%{query}%'),
                Donor.curr_district.ilike(f'%{query}%')
            )
        )
        results['donors'] = donor_query.limit(10).all()
        
        # Search Blood Requests
        req_query = BloodRequest.query.filter(
            or_(
                BloodRequest.patient_name.ilike(f'%{query}%'),
                BloodRequest.blood_group.ilike(f'%{query}%'),
                BloodRequest.hospital.ilike(f'%{query}%'),
                BloodRequest.district.ilike(f'%{query}%')
            )
        )
        results['requests'] = req_query.limit(10).all()
        
        # Search News
        news_query = News.query.filter(
            News.is_published == True
        ).filter(
            or_(
                News.title.ilike(f'%{query}%'),
                News.author.ilike(f'%{query}%'),
                News.tags.ilike(f'%{query}%')
            )
        )
        results['news'] = news_query.limit(10).all()
        
        # Search Notices
        notice_query = Notice.query.filter(
            Notice.is_active == True
        ).filter(
            or_(
                Notice.title.ilike(f'%{query}%'),
                Notice.content.ilike(f'%{query}%')
            )
        )
        results['notices'] = notice_query.limit(10).all()
        
    return render_template('search_results.html', query=query, results=results)
