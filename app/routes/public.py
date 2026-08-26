import os
import math
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, abort, current_app, Response, jsonify, session
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import desc, or_, func
from flask_login import login_required, current_user, login_user, logout_user

from app import db
from app.models import (
    Donor, BloodRequest, News, Notice, Advertisement, 
    Contact, SuccessStory, Volunteer, BloodBank, BloodReservation
)
from app.forms import (
    BloodRequestForm, DonorRegistrationForm, ContactForm, RequestManagementForm,
    DonorLoginForm, VolunteerRegistrationForm, VolunteerLoginForm,
    DonorProfileEditForm, DonationHistoryForm
)
from app.utils import paginate_query, get_blood_group_stats, rate_limit, generate_qr_code
from app.tasks import alert_matching_donors

try:
    import nepali_datetime  # type: ignore
except ImportError:
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
       
        from google.cloud import vision
        client = vision.ImageAnnotatorClient()

        with open(image_path, 'rb') as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        response = client.safe_search_detection(image=image)  # type: ignore[attr-defined]  # dynamically generated gRPC method
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
    except Exception:
        # यदि Google Cloud Credentials कन्फिगर गरिएको छैन भने सुरक्षा बाइपास (वैकल्पिक)
        return True, "Skipped"


# ─── AI TEXT VERIFICATION (OPENAI) ───
def is_text_safe(title, content):
    """
    OpenAI API प्रयोग गरी कथाको शीर्षक र विषयवस्तु सुरक्षित/सान्दर्भिक छ कि छैन जाँच गर्ने।
    """
    try:
        import openai  # type: ignore
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
        
        result = json.loads(response.choices[0].message.content or '{}')
        
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
        if file and file.filename:
            filename = secure_filename(file.filename or '')
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

NEPAL_DISTRICT_COORDINATES = {
    'Achham': (29.1126, 81.3000), 'Arghakhanchi': (27.9000, 83.1500), 'Baglung': (28.2667, 83.6000),
    'Baitadi': (29.5333, 80.4500), 'Bajhang': (29.5833, 81.2000), 'Bajura': (29.5000, 81.5000),
    'Banke': (28.1667, 81.6500), 'Bara': (27.0500, 85.0500), 'Bardiya': (28.3333, 81.3333),
    'Bhaktapur': (27.6710, 85.4298), 'Bhojpur': (27.1667, 87.0500), 'Chitwan': (27.6000, 84.4500),
    'Dadeldhura': (29.3000, 80.5833), 'Dailekh': (28.8333, 81.7167), 'Dang': (28.0000, 82.3000),
    'Darchula': (29.8500, 80.5333), 'Dhading': (27.8667, 84.9000), 'Dhankuta': (26.9833, 87.3333),
    'Dhanusha': (26.7333, 85.9167), 'Dolakha': (27.7833, 86.0833), 'Dolpa': (29.0014, 82.6812),
    'Doti': (29.2500, 80.9500), 'Gorkha': (28.0000, 84.6333), 'Gulmi': (28.0833, 83.2500),
    'Humla': (29.9667, 81.8333), 'Ilam': (26.9089, 87.9281), 'Jajarkot': (28.7000, 82.2000),
    'Jhapa': (26.6343, 87.9961), 'Jumla': (29.2748, 82.1837), 'Kailali': (28.6847, 80.5921),
    'Kalikot': (29.1333, 81.7333), 'Kanchanpur': (28.8333, 80.2500), 'Kapilvastu': (27.5500, 83.0500),
    'Kaski': (28.2120, 83.9912), 'Kathmandu': (27.7018, 85.3184), 'Kavrepalanchok': (27.5500, 85.5500),
    'Khotang': (27.2000, 86.8000), 'Lalitpur': (27.6775, 85.3167), 'Lamjung': (28.2333, 84.4000),
    'Mahottari': (26.8333, 85.8000), 'Makwanpur': (27.4500, 85.0333), 'Manang': (28.6667, 84.0167),
    'Morang': (26.6500, 87.4500), 'Mugu': (29.6000, 82.1667), 'Mustang': (28.7845, 83.7215),
    'Myagdi': (28.3500, 83.5667), 'Nawalpur': (27.6500, 84.1500), 'Nawalparasi': (27.6000, 83.8000),
    'Nuwakot': (27.9167, 85.1667), 'Okhaldhunga': (27.3167, 86.5000), 'Palpa': (27.8667, 83.5500),
    'Panchthar': (27.2000, 87.8333), 'Parasi': (27.5333, 83.6667), 'Parbat': (28.2000, 83.6833),
    'Parsa': (27.1500, 84.8500), 'Pyuthan': (28.1000, 82.8500), 'Ramechhap': (27.3333, 86.0833),
    'Rasuwa': (28.1167, 85.3000), 'Rautahat': (26.9500, 85.3000), 'Rolpa': (28.3333, 82.6667),
    'Rukum East': (28.6333, 82.7833), 'Rukum West': (28.6333, 82.4833), 'Rupandehi': (27.7006, 83.4661),
    'Salyan': (28.3667, 82.1667), 'Sankhuwasabha': (27.5833, 87.2167), 'Saptari': (26.5412, 86.7521),
    'Sarlahi': (26.9667, 85.5500), 'Sindhuli': (27.2500, 85.9667), 'Sindhupalchok': (27.9500, 85.7000),
    'Siraha': (26.6500, 86.2000), 'Solukhumbu': (27.7000, 86.7167), 'Sunsari': (26.7000, 87.1500),
    'Surkhet': (28.6000, 81.6333), 'Syangja': (28.1000, 83.8667), 'Tanahun': (27.9500, 84.2500),
    'Taplejung': (27.3500, 87.6667), 'Terhathum': (27.1333, 87.5500), 'Udayapur': (26.9000, 86.5167),
}


def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on the earth (specified in decimal degrees)"""
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    except (TypeError, ValueError):
        return float('inf')
    R = 6371.0  # Earth radius in kilometers
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@public_bp.route('/api/nearest-blood-bank')
def nearest_blood_bank():
    lat_str = request.args.get('lat')
    lng_str = request.args.get('lng')
    district_param = (request.args.get('district') or '').strip()

    user_lat = None
    user_lng = None

    if lat_str and lng_str:
        try:
            user_lat = float(lat_str)
            user_lng = float(lng_str)
        except (TypeError, ValueError):
            user_lat = None
            user_lng = None

    # If GPS coordinates are not provided, use the district centroid
    if (user_lat is None or user_lng is None) and district_param:
        for dist_name, coords in NEPAL_DISTRICT_COORDINATES.items():
            if dist_name.lower() == district_param.lower():
                user_lat, user_lng = coords
                break

    # If still no coordinates, default to Kathmandu centroid
    if user_lat is None or user_lng is None:
        user_lat, user_lng = 27.7018, 85.3184

    banks = BloodBank.query.filter(
        BloodBank.latitude.isnot(None),
        BloodBank.longitude.isnot(None),
        BloodBank.is_active != False
    ).all()

    if not banks:
        return jsonify({'error': 'No blood banks found in directory'}), 404

    calculated = []
    for bank in banks:
        dist = haversine(user_lat, user_lng, bank.latitude, bank.longitude)
        is_same_district = bool(
            district_param and bank.district and
            district_param.lower() in bank.district.lower()
        )
        calculated.append({
            'id': bank.id,
            'name': bank.resolved_display_name,
            'district': bank.district or '',
            'province': bank.province or '',
            'distance_km': round(dist, 1),
            'is_same_district': is_same_district,
            'address': f"{bank.district or ''}, {bank.province or ''}".strip(', '),
            'phone': bank.contact_number or bank.phone or '',
            'emergency_available': bool(bank.is_emergency_panel or bank.emergency_available),
            'url': url_for('public.blood_bank_detail', bank_id=bank.id),
            'reserve_url': url_for('public.reserve_blood', bank_id=bank.id),
            'maps_url': bank.google_maps_url or bank.maps_url or ''
        })

    # Sort: 1) Same district first, 2) Closest distance in km
    calculated.sort(key=lambda b: (not b['is_same_district'], b['distance_km']))

    nearest = calculated[0]
    return jsonify({
        'id': nearest['id'],
        'name': nearest['name'],
        'district': nearest['district'],
        'province': nearest['province'],
        'distance_km': nearest['distance_km'],
        'address': nearest['address'],
        'phone': nearest['phone'],
        'emergency_available': nearest['emergency_available'],
        'url': nearest['url'],
        'reserve_url': nearest['reserve_url'],
        'maps_url': nearest['maps_url'],
        'query_district': district_param,
        'nearby_banks': calculated[:5]
    })


@public_bp.route('/blood-banks/<int:bank_id>')
def blood_bank_detail(bank_id):
    blood_bank = BloodBank.query.get_or_404(bank_id)
    
    from app.models import BloodInventory, BloodReservation, PublicBloodBankCache
    real_inventories = BloodInventory.query.filter_by(blood_bank_id=bank_id).order_by(BloodInventory.blood_group, BloodInventory.component).all()
    inventory_items = []
    
    if real_inventories:
        for item in real_inventories:
            active_reserved = db.session.query(func.sum(BloodReservation.units)).filter(
                BloodReservation.blood_bank_id == bank_id,
                BloodReservation.blood_group == item.blood_group,
                BloodReservation.component == item.component,
                BloodReservation.status.in_(['approved', 'locked'])
            ).scalar()
            
            reserved_units = int(active_reserved) if active_reserved is not None else (item.units_reserved or 0)
            avail_units = max((item.units_available or 0) - reserved_units, 0)
            
            if (item.units_available or 0) > 0 or reserved_units > 0:
                inventory_items.append({
                    'blood_group': item.blood_group,
                    'component': item.component,
                    'available_units': avail_units,
                    'units_reserved': reserved_units
                })
    else:
        cache = PublicBloodBankCache.query.filter_by(blood_bank_id=bank_id).first()
        if cache:
            group_mapping = {
                'A+': cache.a_pos, 'A-': cache.a_neg,
                'B+': cache.b_pos, 'B-': cache.b_neg,
                'AB+': cache.ab_pos, 'AB-': cache.ab_neg,
                'O+': cache.o_pos, 'O-': cache.o_neg
            }
            for group, val in group_mapping.items():
                active_reserved = db.session.query(func.sum(BloodReservation.units)).filter(
                    BloodReservation.blood_bank_id == bank_id,
                    BloodReservation.blood_group == group,
                    BloodReservation.status.in_(['approved', 'locked'])
                ).scalar() or 0
                
                reserved_units = int(active_reserved)
                avail_units = max((val or 0) - reserved_units, 0)
                if (val or 0) > 0 or reserved_units > 0:
                    inventory_items.append({
                        'blood_group': group,
                        'component': 'Any / Whole Blood',
                        'available_units': avail_units,
                        'units_reserved': reserved_units
                    })
    
    # Fetch 3-Shift breakdown and publicly visible staff members strictly for this blood bank
    from app.services.shift_service import ShiftService
    from app.models import StaffMember
    
    three_shifts = ShiftService.get_three_shifts(blood_bank.id)
    staff_members = StaffMember.query.filter_by(
        blood_bank_id=blood_bank.id,
        is_active=True,
        profile_visibility='public'
    ).order_by(StaffMember.created_at.desc()).all()
                
    return render_template(
        'blood_bank_detail.html',
        blood_bank=blood_bank,
        inventory_items=inventory_items,
        staff_members=staff_members,
        three_shifts=three_shifts
    )


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

        # Trigger Real-Time Alert to Blood Bank Portal
        try:
            from app.services.bloodbank_alert_service import dispatch_reservation_alert
            dispatch_reservation_alert(reservation)
        except Exception as res_alert_err:
            current_app.logger.warning("Failed to dispatch reservation alert: %s", res_alert_err)

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
        ten_min_ago = datetime.now() - timedelta(minutes=10)
        p_name = form.patient_name.data or ''
        normalized_new = ''.join(e for e in p_name.lower() if e.isalnum())
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
            patient_name    = (form.patient_name.data or '').strip(),
            request_message = (form.request_message.data or '').strip(),
            case_details    = (form.case_details.data or '').strip(),
            blood_group     = form.blood_group.data,
            required_component = form.required_component.data or 'Whole Blood',
            units_needed    = form.units_needed.data,
            hospital        = (form.hospital.data or '').strip(),
            province        = form.province.data or "",
            district        = (form.district.data or '').strip(),
            local_level     = (form.local_level.data or '').strip(),
            ward_no         = (form.ward_no.data or '').strip(),
            contact_person  = (form.contact_person.data or '').strip(),
            contact_number  = (form.contact_number.data or '').strip(),
            alt_number      = (form.alt_number.data or '').strip(),
            pin             = (form.pin.data or '').strip(),
            is_emergency    = form.is_emergency.data,
        )
        db.session.add(req)
        db.session.flush()  # get req.id before commit

        # Handle hospital paper upload
        if form.hospital_paper.data:
            paper_file = form.hospital_paper.data
            import uuid
            ext = (paper_file.filename or '').rsplit('.', 1)[-1].lower() if '.' in (paper_file.filename or '') else 'jpg'
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
            app_obj = getattr(current_app, '_get_current_object')()
            alert_matching_donors(app_obj, req.id)
        except Exception as e:
            current_app.logger.error(f"Error alerting donors: {e}")

        # Trigger Real-Time Alerts to Nearby Blood Banks
        try:
            from app.services.bloodbank_alert_service import dispatch_nearby_request_alert
            dispatch_nearby_request_alert(req)
        except Exception as bb_alert_err:
            current_app.logger.warning("Failed to dispatch nearby blood bank alerts: %s", bb_alert_err)
        
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
            request_id=(form.request_id.data or '').strip(),
            pin=(form.pin.data or '').strip()
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
                request_record.fulfilled_date = datetime.now()
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
    blood_group = request.args.get('blood_group', '').strip()
    district    = request.args.get('district', '').strip()
    local_level = (request.args.get('local_level') or request.args.get('city') or '').strip()
    donor_type  = request.args.get('donor_type', '').strip()
    status      = request.args.get('status', '').strip()
    
    # Query all active registered donors (available, recently donated, and unavailable)
    query = Donor.query.filter(Donor.is_active != False)
    
    if blood_group:
        query = query.filter_by(blood_group=blood_group)
    if district:
        query = query.filter(Donor.curr_district.ilike(f'%{district}%'))
    if local_level:
        query = query.filter(
            or_(
                Donor.curr_local_level.ilike(f'%{local_level}%'),
                Donor.curr_tole.ilike(f'%{local_level}%')
            )
        )
    if donor_type:
        query = query.filter_by(donor_type=donor_type)
    if status:
        query = query.filter_by(availability_status=status)
    
    query = query.order_by(
        (Donor.availability_status == 'available').desc(),
        desc(Donor.created_at)
    )
    
    per_page = current_app.config.get('DONORS_PER_PAGE', 12)
    pagination = paginate_query(query, page, per_page)
    
    total_donors = Donor.query.filter(Donor.is_active != False).count()
    avail_donors = Donor.query.filter(Donor.is_active != False, Donor.availability_status == 'available').count()
    blood_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    districts = ALL_DISTRICTS
    
    return render_template('find_donors.html',
        pagination=pagination,
        blood_groups=blood_groups,
        districts=districts,
        selected_bg=blood_group,
        selected_district=district,
        selected_local_level=local_level,
        selected_city=local_level,
        selected_type=donor_type,
        selected_status=status,
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
        if ad_date and hasattr(ad_date, 'year') and ad_date.year > 2050 and nepali_datetime:
            try:
                bs_date = nepali_datetime.date(ad_date.year, ad_date.month, ad_date.day)
                ad_date = bs_date.to_datetime_date()
            except Exception:
                pass

        donor = Donor(
            full_name           = (form.full_name.data or '').strip(),
            email               = (form.email.data or '').strip() if form.email.data and form.email.data.strip() else None,
            pin_hash            = generate_password_hash(form.pin.data or '1234'),
            age                 = form.age.data,
            weight              = form.weight.data,
            perm_province       = form.perm_province.data or "",
            perm_district       = (form.perm_district.data or '').strip(),
            perm_local_level    = (form.perm_local_level.data or '').strip(),
            perm_ward           = (form.perm_ward.data or '').strip(),
            perm_tole           = (form.perm_tole.data or '').strip(),
            curr_province       = form.curr_province.data,
            curr_district       = (form.curr_district.data or '').strip(),
            curr_local_level    = (form.curr_local_level.data or '').strip(),
            curr_ward           = (form.curr_ward.data or '').strip(),
            curr_tole           = (form.curr_tole.data or '').strip(),
            phone1              = (form.phone1.data or '').strip(),
            phone2              = (form.phone2.data or '').strip(),
            blood_group         = form.blood_group.data,
            last_donation_date  = ad_date,
            donation_times      = form.donation_times.data or 0,
            donor_type          = form.donor_type.data,
            social_link         = (form.social_link.data or '').strip(),
        )
        
        # Calculate initial availability
        donor.recalculate_and_save()
        
        db.session.add(donor)
        db.session.commit()
        
        login_user(donor)
        flash(f'🎉 Registration successful! Your Donor ID: {donor.donor_id}.', 'success')
        return redirect(url_for('public.donor_profile', donor_id=donor.donor_id))
    
    return render_template('become_donor.html', form=form, districts=ALL_DISTRICTS)


# ── Donor PIN Security Interceptor ────────────────────────
@public_bp.before_request
def enforce_donor_forced_pin_change():
    if current_user.is_authenticated and hasattr(current_user, 'donor_id') and getattr(current_user, 'pin_reset_required', False):
        allowed_endpoints = [
            'public.donor_force_change_pin',
            'public.logout',
            'public.donor_photo',
            'public.donor_qr',
            'static'
        ]
        if request.endpoint and request.endpoint not in allowed_endpoints:
            return redirect(url_for('public.donor_force_change_pin'))


@public_bp.route('/donor/login', methods=['GET', 'POST'])
@rate_limit(limit=10, window=60)  # 10 attempts per minute
def donor_login():
    if current_user.is_authenticated and hasattr(current_user, 'donor_id'):
        if getattr(current_user, 'pin_reset_required', False):
            return redirect(url_for('public.donor_force_change_pin'))
        return redirect(url_for('public.donor_profile', donor_id=current_user.donor_id))
        
    form = DonorLoginForm()
    if form.validate_on_submit():
        login_val = (form.login_id.data or '').strip()
        
        # Check if login_val is phone or email
        normalized_phone = login_val
        if login_val.isdigit() or (login_val.startswith('+') and login_val[1:].isdigit()):
            from app.forms import _normalize_nepal_mobile
            normalized_phone = _normalize_nepal_mobile(login_val)
        
        from sqlalchemy import or_
        donor = Donor.query.filter(or_(Donor.phone1 == normalized_phone, Donor.email == login_val)).first()
        
        if donor and check_password_hash(donor.pin_hash, form.pin.data or ''):
            session.permanent = True
            login_user(donor, remember=True)
            
            # Forced PIN change enforcement
            if donor.pin_reset_required:
                flash('Your PIN has been reset by an administrator. Please create a new PIN to access your account.', 'warning')
                return redirect(url_for('public.donor_force_change_pin'))
                
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('public.donor_profile', donor_id=donor.donor_id))
        else:
            flash('Login Unsuccessful. Please check your mobile number / email and PIN.', 'danger')
            
    return render_template('auth/donor_login.html', form=form)


@public_bp.route('/donor/forgot-pin')
def donor_forgot_pin():
    """Contact portal for donor PIN reset assistance through Admin and Super Admin."""
    from urllib.parse import quote

    base_msg = 'Hello, I need help resetting my NBDS Donor Portal PIN.'
    donor_info = None

    if current_user.is_authenticated and hasattr(current_user, 'donor_id'):
        donor_info = {
            'donor_id': current_user.donor_id,
            'phone': current_user.phone1,
            'full_name': current_user.full_name,
        }
        full_msg = (
            f"Hello, I need help resetting my NBDS Donor Portal PIN.\n\n"
            f"Donor ID: {current_user.donor_id}\n"
            f"Contact No: {current_user.phone1}\n"
            f"Full Name: {current_user.full_name}"
        )
    else:
        full_msg = base_msg

    encoded_msg = quote(full_msg, safe='')
    wa_admin_url  = f"https://wa.me/9779824915245?text={encoded_msg}"
    wa_super_url  = f"https://wa.me/9779816003020?text={encoded_msg}"

    return render_template(
        'auth/donor_forgot_pin.html',
        donor_info=donor_info,
        wa_admin_url=wa_admin_url,
        wa_super_url=wa_super_url,
    )


@public_bp.route('/donor/force-change-pin', methods=['GET', 'POST'])
@login_required
def donor_force_change_pin():
    """Mandatory PIN change page for donors whose PIN was reset by an administrator."""
    if not hasattr(current_user, 'donor_id'):
        return redirect(url_for('public.index'))
    
    donor = current_user
    if not getattr(donor, 'pin_reset_required', False):
        return redirect(url_for('public.donor_profile', donor_id=donor.donor_id))
        
    from app.forms import DonorForcedPinChangeForm
    form = DonorForcedPinChangeForm()
    
    if form.validate_on_submit():
        new_pin = (form.new_pin.data or '').strip()
        donor.set_pin(new_pin)
        donor.pin_reset_required = False
        donor.pin_last_changed_at = datetime.now(timezone.utc)
        donor.failed_pin_attempts = 0
        donor.pin_locked_until = None
        
        from app.models import AuditLog
        log = AuditLog(
            action='DONOR_PIN_CHANGED_AFTER_ADMIN_RESET',
            entity_id=donor.id,
            details=f"Donor {donor.donor_id} ({donor.full_name}) successfully changed temporary PIN 1234 to new private PIN.",
            actor=donor.donor_id
        )
        db.session.add(log)
        db.session.commit()
        
        flash('🎉 PIN changed successfully! You can now access your full donor dashboard and donor card.', 'success')
        return redirect(url_for('public.donor_profile', donor_id=donor.donor_id))
        
    return render_template('auth/donor_force_change_pin.html', form=form, donor=donor)


@public_bp.route('/become-volunteer', methods=['GET', 'POST'])
@rate_limit(limit=10, window=3600)  # 10 registrations per hour
def become_volunteer():
    form = VolunteerRegistrationForm()
    
    if form.validate_on_submit():
        volunteer = Volunteer(
            full_name           = (form.full_name.data or '').strip(),
            email               = (form.email.data or '').strip(),
            
            pin_hash            = generate_password_hash(form.pin.data or '1234'),
            
            phone1              = (form.phone1.data or '').strip(),
            
            phone2              = (form.phone2.data or '').strip() if form.phone2.data else None,
            
            designation         = form.designation.data,
            
            working_field       = (form.working_field.data or '').strip() if form.working_field.data else None,
            
            perm_address        = (form.perm_address.data or '').strip(),
            
            curr_address        = (form.curr_address.data or '').strip(),
            
            curr_district       = (form.curr_district.data or '').strip(),
            
            availability_time   = (form.availability_time.data or '').strip() if form.availability_time.data else None
        )
        db.session.add(volunteer)
        db.session.commit()
        
        login_user(volunteer)
        flash('🎉 Thank you for registering as a Volunteer! Your account is pending approval.', 'success')
        return redirect(url_for('public.index'))
    
    return render_template('become_volunteer.html', form=form, districts=ALL_DISTRICTS)


@public_bp.route('/volunteer/login', methods=['GET', 'POST'])
@rate_limit(limit=10, window=60)  # 10 attempts per minute
def volunteer_login():
    if current_user.is_authenticated and hasattr(current_user, 'volunteer_id'):
        return redirect(url_for('public.index'))
        
    form = VolunteerLoginForm()
    if form.validate_on_submit():
        volunteer = Volunteer.query.filter_by(phone1=(form.phone1.data or '').strip()).first()
        if volunteer and check_password_hash(volunteer.pin_hash, form.pin.data or ''):
            login_user(volunteer, remember=form.remember.data)
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('public.index'))
        else:
            flash('Login Unsuccessful. Please check your mobile number and PIN.', 'danger')
            
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
            # Handle profile photo upload (before populate_obj to avoid FileStorage being written to text field)
            photo_file = request.files.get('profile_photo')
            if photo_file and photo_file.filename:
                try:
                    from PIL import Image
                    import io
                    # Open and compress the image
                    img = Image.open(photo_file.stream)  # type: ignore[arg-type]
                    img = img.convert('RGB')  # Convert to RGB (handles PNG transparency, etc.)
                    # Resize to max 400x400 maintaining aspect ratio
                    resample_filter = getattr(Image, 'Resampling', Image).LANCZOS  # type: ignore[attr-defined]
                    img.thumbnail((400, 400), resample_filter)
                    # Save as compressed JPEG
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=65, optimize=True)
                    donor.profile_photo_data = buffer.getvalue()
                    donor.profile_photo_mimetype = 'image/jpeg'
                except Exception as photo_err:
                    flash(f'Photo upload failed: {photo_err}', 'warning')
            
            profile_form.populate_obj(donor)
            
            # Save Notification Preferences
            from app.models import DonorNotificationPreference
            if not donor.preference:
                donor.preference = DonorNotificationPreference(donor_id=donor.id)
            donor.preference.email_alerts = profile_form.email_alerts.data
            donor.preference.sms_alerts = profile_form.sms_alerts.data
            donor.preference.in_app_alerts = profile_form.in_app_alerts.data
            
            donor.updated_at = datetime.now(timezone.utc)
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


@public_bp.route('/donor/<string:donor_id>/photo')
def donor_photo(donor_id):
    """Serve the donor's profile photo from the database."""
    donor = Donor.query.filter_by(donor_id=donor_id).first_or_404()
    if not donor.profile_photo_data:
        abort(404)
    return Response(
        donor.profile_photo_data,
        mimetype=donor.profile_photo_mimetype or 'image/jpeg',
        headers={'Cache-Control': 'public, max-age=86400'}
    )


@public_bp.route('/donor/<string:donor_id>/qr')
def donor_qr(donor_id):
    """Generate a QR code image for the donor's public profile URL."""
    donor = Donor.query.filter_by(donor_id=donor_id).first_or_404()
    import qrcode
    import io
    profile_url = url_for('public.donor_profile', donor_id=donor.donor_id, _external=True)
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(profile_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#991B1B', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')  # type: ignore[call-arg]
    buffer.seek(0)
    return Response(
        buffer.getvalue(),
        mimetype='image/png',
        headers={'Cache-Control': 'public, max-age=86400'}
    )

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
    now = datetime.now()
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
            
            name    = (form.name.data or '').strip(),
            
            email   = (form.email.data or '').strip(),
            
            phone   = (form.phone.data or '').strip() if form.phone.data else None,
            
            subject = (form.subject.data or '').strip(),
            
            message = (form.message.data or '').strip(),
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
#   SEO: SITEMAP & ROBOTS.TXT (Delegated to seo_bp)
# ════════════════════════════════════════════


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
