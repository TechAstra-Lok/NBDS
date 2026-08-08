# app/ai_assistant.py
# ════════════════════════════════════════════════════════════════
#   Raktadata Health & Blood AI Assistant (Full-Scale Doctor & Guidance Engine)
# ════════════════════════════════════════════════════════════════

import os
import re
from flask import current_app

SYSTEM_PROMPT = """
You are "Raktadata Health AI", a world-class Medical Doctor, Transfusion Medicine Specialist, and Health Advisor dedicated to helping users in Nepal and globally.

Your Expertise & Capabilities:
1. Finding Blood & Emergency Support: Guiding users on how to locate blood donors, contact blood banks across Nepal, and submit emergency blood requests.
2. Blood Compatibility & Genetics: Detailed ABO & Rh blood group compatibility, universal donors (O-), universal recipients (AB+), rare types (Bombay phenotype, Rh-null).
3. Donor Eligibility & Medical Deferrals: Accurate guidelines regarding age (18-60/65), weight (min 45kg), hemoglobin (min 12.5g/dL), donation intervals (90 days for whole blood, 14 days for apheresis platelets), and deferral periods for:
   - Tattoos/Piercings (6 months)
   - Alcohol (avoid 24 hours before) / Smoking (avoid 2 hours before & after)
   - Surgery / Dental procedures / Blood transfusion history
   - Medications (antibiotics, aspirin, blood thinners, acne meds like isotretinoin)
   - Infections (Fever/Cold: wait till fully recovered; Malaria: 3 months to 3 years; Dengue/Typhoid: 6 months after recovery)
   - Pregnancy / Breastfeeding (12 months post-delivery)
4. Nutrition & Hemoglobin Boosting: Dietary advice to naturally increase iron (spinach, lentils, red meat, liver, jaggery, beetroot) paired with Vitamin C (lemons, oranges, amla) while avoiding calcium/tannin inhibitors during meals.
5. General Health & Wellness Advice: Hydration, sleep, healthy lifestyle, cardiovascular benefits of regular blood donation, and managing post-donation recovery (dizziness, bruising).

Rules:
- Language: Respond fluently in English if asked in English, or in Nepali (नेपाली) if the user asks in Nepali!
- Tone: Empathetic, highly knowledgeable, professional, reassuring, and clear.
- Formatting: Use rich markdown with headers, bullet points, and bold text for readability.
- Website Integration: Refer users to Raktadata platform features when applicable:
  - Find Donors: [Find Donors](/find-donors)
  - Emergency Blood Request: [Post Blood Request](/blood-request)
  - Blood Banks List: [Blood Banks Directory](/blood-banks)
- Safety: If a user describes a life-threatening emergency (severe bleeding, shock, trauma), advise calling emergency services immediately.
"""

MEDICAL_DISCLAIMER = "\n\n---\n*⚠️ **Medical Disclaimer**: Raktadata AI provides medical & health guidance for informational purposes. For acute trauma, emergency diagnosis, or specific clinical conditions, please consult a certified healthcare professional immediately.*"

# Comprehensive 24/7 Smart Knowledge Engine for Offline / Fallback Operations
KNOWLEDGE_BASE = {
    'find_blood': """
🩸 **How & Where to Find Blood for Your Patient in Nepal:**

If your patient requires blood, follow these immediate actionable steps:

1. 🔍 **Search Registered Donors:**
   Visit our **[Find Donors](/find-donors)** page to filter active, verified blood donors by **Blood Group** and **District / City** in Nepal. You can view primary contact numbers and call donors directly.

2. 🆘 **Post an Emergency Request:**
   Submit an urgent request on our **[Post Blood Request](/blood-request)** page. Your request will be published live on the Emergency Board and broadcasted to matching registered donors in your area.

3. 🏥 **Contact Hospital & Red Cross Blood Banks:**
   Check our **[Blood Banks Directory](/blood-banks)** for verified blood centers, including:
   - **Central Blood Transfusion Service (NRCS), Exhibition Road, Kathmandu:** 📞 +977-1-4225344
   - **Bhaktaapur Blood Bank:** 📞 +977-1-6612266
   - **Lalitpur Blood Bank (Pulchowk):** 📞 +977-1-5527045
   - **Teaching Hospital Blood Bank (Maharajgunj):** 📞 +977-1-4412404
   - **Kanti Children's Hospital Blood Bank:** 📞 +977-1-4411140
   - **Bir Hospital Blood Bank:** 📞 +977-1-4221988

4. 📞 **24/7 Emergency Assistance:**
   Call Raktadata Emergency Helpline: **+977 9816003020** or Red Cross Emergency Blood Line.

*Tip: Make sure you have your doctor's requisition form specifying the required blood group and number of units (Pint/Bag).*
""",

    'find_blood_ne': """
🩸 **तपाईंको बिरामीको लागि रगत कहाँ र कसरी खोज्ने:**

यदि बिरामीलाई तत्काल रगत चाहिएको छ भने, यी मुख्य उपायहरू अपनाउनुहोस्:

1. 🔍 **रक्तदाता खोज्नुहोस्:**
   हाम्रो **[रक्तदाता खोज्नुहोस् (/find-donors)](/find-donors)** पेजमा गई आफ्नो जिल्ला र रक्त समूह (Blood Group) अनुसार सक्रिय रक्तदाताहरू खोज्नुहोस् र सिधै सम्पर्क गर्नुहोस्।

2. 🆘 **आकस्मिक रक्त अनुरोध पोस्ट गर्नुहोस्:**
   **[रक्त अनुरोध पोस्ट गर्नुहोस् (/blood-request)](/blood-request)** पेजमा गई बिरामीको विवरण पेश गर्नुहोस्। तपाईंको अनुरोध तुरुन्तै आपतकालीन बोर्डमा देखिनेछ र सम्बन्धित जिल्लाका रक्तदाताहरूलाई खबर हुनेछ।

3. 🏥 **ब्लड बैंकहरूमा सम्पर्क गर्नुहोस्:**
   हाम्रो **[ब्लड बैंक डाइरेक्टरी (/blood-banks)](/blood-banks)** मा गई नजिकैको ब्लड बैंकमा फोन गर्नुहोस्:
   - **केन्द्रीय रक्तसञ्चार सेवा (रेडक्रस), भृकुटीमण्डप काठमाडौँ:** 📞 ०१-४२२५३४४
   - **भक्तपुर ब्लड बैंक:** 📞 ०१-६६१२२६६
   - **ललितपुर ब्लड बैंक (पुल्चोक):** 📞 ०१-५५२७०४५
   - **शिक्षण अस्पताल ब्लड बैंक (महाराजगञ्ज):** 📞 ०१-४४१२४०४

4. 📞 **२४/७ आपतकालीन हटलाइन:**
   रक्तदान र रक्तदाता हेल्पलाइन: **+977 9816003020** मा सम्पर्क गर्नुहोस्।
""",

    'compatibility': """
🩸 **Blood Group Compatibility & Transfusion Guide:**

- **O Negative (O-):** Universal Red Cell Donor (Can donate to O-, O+, A-, A+, B-, B+, AB-, AB+).
- **AB Positive (AB+):** Universal Red Cell Recipient (Can receive from all blood groups).
- **O Positive (O+):** Can donate to O+, A+, B+, AB+. Can receive from O+ and O-.
- **A Positive (A+):** Can donate to A+ and AB+. Can receive from A+, A-, O+, O-.
- **B Positive (B+):** Can donate to B+ and AB+. Can receive from B+, B-, O+, O-.
- **A Negative (A-):** Can donate to A+, A-, AB+, AB-. Can receive from A- and O-.
- **B Negative (B-):** Can donate to B+, B-, AB+, AB-. Can receive from B- and O-.
- **AB Negative (AB-):** Can donate to AB+ and AB-. Can receive from AB-, A-, B-, O-.

*Need blood right now? Filter donors by group on [Find Donors](/find-donors).*
""",

    'eligibility': """
📋 **Complete Blood Donor Eligibility Criteria:**

1. **Age:** 18 – 60 years old (up to 65 for regular donors in good health).
2. **Weight:** Minimum **45 kg** (100 lbs).
3. **Hemoglobin Level:** Minimum **12.5 g/dL** (checked via quick finger-prick test before donation).
4. **Vital Signs:** Blood Pressure (Systolic 100-140, Diastolic 60-90 mmHg), Pulse (60-100 bpm), Temperature (Normal).
5. **Donation Frequency:**
   - Whole Blood: Minimum **90 days (3 months)** between donations.
   - Platelets / Plasma (Apheresis): Minimum **14 days**.

🚫 **Common Temporary Medical Deferrals:**
- **Tattoo / Body Piercing:** Wait 6 months.
- **Alcohol Intake:** Avoid alcohol for 24 hours prior.
- **Smoking:** Avoid 2 hours before and after.
- **Minor Infections / Fever / Cold:** Wait until 7-14 days after full recovery.
- **Antibiotics:** Wait 7 days after finishing the course.
- **Dengue / Typhoid / Malaria:** Wait 6 months after full recovery.
- **Pregnancy / Breastfeeding:** Wait 12 months after delivery/stopping breastfeeding.
""",

    'before_donation': """
🍎 **Pre-Donation Preparation & Diet Guide:**

1. 💧 **Hydration:** Drink at least 500ml (2-3 large glasses) of water or natural fruit juice 1-2 hours before donating.
2. 🥗 **Nutritious Meal:** Eat a balanced, wholesome meal 2-3 hours before. Avoid greasy or high-fat foods (fried items, fast food) as lipids in blood affect lab testing.
3. 😴 **Adequate Sleep:** Ensure 7-8 hours of sound sleep the night before.
4. 🚭 **Avoid Alcohol & Tobacco:** Abstain from alcohol for at least 24 hours and refrain from smoking for 2 hours before.
5. 🆔 **Preparation:** Carry a valid government ID card and list of any current medications.
""",

    'after_donation': """
💪 **Post-Donation Care & Speedy Recovery:**

1. 🥪 **Rest & Refreshment:** Relax in the recovery area for 15 minutes post-donation. Consume juices, tea, or biscuits.
2. 🥤 **Fluid Replenishment:** Drink extra fluids (water, coconut water, fresh juices) over the next 24 to 48 hours.
3. 🚫 **Avoid Heavy Exertion:** Refrain from heavy lifting, strenuous gym workouts, or driving long distances immediately after.
4. 🩹 **Bandage Care:** Keep the bandage on your arm for 4-5 hours. Clean gently if bruised.
5. 😵 **If You Feel Dizziness or Lightheadedness:** Sit or lie down immediately with your feet elevated above heart level until fully recovered.
""",

    'hemoglobin': """
🥦 **How to Naturally Increase Hemoglobin & Iron Levels:**

1. 🥬 **Plant-Based Iron (Non-Heme Iron):**
   - Dark leafy greens: Spinach (palungo), fenugreek (methi), mustard greens (rayo).
   - Legumes: Black chickpeas (chana), lentils (daal), kidney beans (rajma), soybeans.
   - Vegetables & Fruits: Beetroot, pomegranates, apples, raisins, dates, and jaggery (gud).
2. 🥩 **Animal-Based Iron (Heme Iron):**
   - Red meat, liver, chicken, eggs, and fish (heme iron is absorbed more efficiently).
3. 🍋 **Vitamin C Power Booster:**
   - Always pair iron-rich foods with Vitamin C (lemon juice, oranges, tomatoes, amla). Vitamin C boosts iron absorption by up to 300%!
4. ☕ **Avoid Inhibitors:**
   - Do NOT drink tea, coffee, or milk during or immediately after meals, as tannins and calcium block iron absorption.
""",

    'deferral_tattoo_meds': """
💉 **Medical Deferrals: Tattoos, Alcohol, Medications & Surgeries:**

- **Tattoos & Piercings:** Deferred for **6 months** due to potential blood-borne infection risks.
- **Alcohol:** Do not consume alcohol for **24 hours** before donation to prevent dehydration.
- **Smoking:** Avoid smoking **2 hours before and after** donation.
- **Antibiotics:** Deferred until **7 days after completing** your full antibiotic course.
- **Aspirin / Blood Thinners:** Deferred **48 hours** for platelet donation (whole blood donation is generally permitted).
- **Surgeries:** Major surgeries require a **6-month deferral**; minor procedures require **1-3 months**.
- **Vaccinations:** COVID-19/Flu vaccines: wait 14 days if asymptomatic; Live vaccines (MMR, Yellow Fever): wait 4 weeks.
""",

    'nepali_general': """
🇳🇵 **नमस्कार! रक्तदान र स्वास्थ्य सम्बन्धी सहायता:**

म **रक्तदान र रक्तदाता AI सहायक** हुँ। म तपाईंलाई सहयोग गर्न सक्छु:

- 🩸 **रगत कहाँ पाउने:** [रक्तदाता खोज्नुहोस्](/find-donors) वा [रक्त अनुरोध पोस्ट गर्नुहोस्](/blood-request)
- 📋 **रक्तदानको मापदण्ड:** उमेर (१८-६०), तौल (कम्तिमा ४५ केजी), हिमोग्लोबिन (कम्तिमा १२.५)
- 🧪 **रक्त समूह योग्यता:** O- (सबैलाई दिन मिल्ने), AB+ (सबैबाट लिन मिल्ने)
- 🍎 **खानपान र हेरचाह:** हिमोग्लोबिन बढाउने उपाय र रक्तदान अघि/पछिको खानपान

तपाईंको प्रश्न सोध्नुहोस्, म मद्दत गर्न तयार छु!
""",

    'default': """
🏥 **Welcome to Raktadata Health & Blood AI Guidance System!**

I can assist you with:
- 🩸 **Locating Blood for Patients:** Find donors in your district or submit urgent requests.
- 📋 **Donor Eligibility & Deferrals:** Weight, age, tattoos, alcohol, medication rules.
- 🧪 **Blood Group Compatibility:** Universal donors, recipients, and Rh factors.
- 🥦 **Hemoglobin & Nutrition:** Iron-rich diets and Vitamin C absorption.
- 🏥 **Blood Banks in Nepal:** Direct contacts for Red Cross and hospital transfusion centers.

*How can I help with your health or blood query today?*
"""
}


def generate_ai_response(user_query: str) -> str:
    """
    Generates a full-scale health response using Gemini API (with candidate fallback models),
    OpenAI API, or the 24/7 Smart Knowledge Engine.
    """
    query_clean = user_query.strip()
    if not query_clean:
        return "Please ask any question about blood donation, health tips, blood group compatibility, or finding blood in Nepal."

    # 1. Try Google Gemini API with candidate model aliases
    gemini_key = (
        os.environ.get('GEMINI_API_KEY') or 
        os.environ.get('GOOGLE_API_KEY') or 
        current_app.config.get('GEMINI_API_KEY') or 
        current_app.config.get('GOOGLE_API_KEY')
    )
    
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            
            # Candidate models ordered by speed and availability
            candidate_models = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
            prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {query_clean}"
            
            for m_name in candidate_models:
                try:
                    model = genai.GenerativeModel(m_name)
                    response = model.generate_content(prompt)
                    if response and response.text:
                        return response.text.strip() + MEDICAL_DISCLAIMER
                except Exception:
                    continue
        except Exception:
            pass

    # 2. Try OpenAI API
    openai_key = os.environ.get('OPENAI_API_KEY') or current_app.config.get('OPENAI_API_KEY')
    if openai_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key)
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": query_clean}
                ],
                max_tokens=600,
                temperature=0.7,
            )
            if completion.choices and completion.choices[0].message.content:
                return completion.choices[0].message.content.strip() + MEDICAL_DISCLAIMER
        except Exception:
            pass

    # 3. Enhanced Intent-Driven Smart Knowledge Engine (24/7 Guaranteed Guidance)
    q_lower = query_clean.lower()

    # Intent 1: Finding Blood / Emergency Requests / Blood Banks
    if any(k in q_lower for k in [
        'where can i find', 'find blood', 'need blood', 'where to get', 'search blood', 
        'blood for patient', 'urgent blood', 'emergency blood', 'locate blood', 'how to get blood',
        'blood bank', 'hospital blood', 'red cross', 'kathmandu blood', 'pokhara blood',
        'रगत कहाँ', 'रगत चाहिएको', 'रगत पाइन्छ', 'बिरामीको लागि रगत', 'ब्लड बैंक'
    ]):
        if any(k in q_lower for k in ['रगत', 'बिरामी', 'कहाँ', 'पाइन्छ', 'चाहियो']):
            reply = KNOWLEDGE_BASE['find_blood_ne']
        else:
            reply = KNOWLEDGE_BASE['find_blood']

    # Intent 2: Deferrals (Tattoos, Alcohol, Meds, Surgery, Infections)
    elif any(k in q_lower for k in [
        'tattoo', 'piercing', 'alcohol', 'drink', 'beer', 'smoking', 'cigarette',
        'medication', 'antibiotic', 'surgery', 'dengue', 'malaria', 'typhoid', 'fever', 'cold',
        'pregnancy', 'breastfeed', 'vaccine'
    ]):
        reply = KNOWLEDGE_BASE['deferral_tattoo_meds']

    # Intent 3: Compatibility / Blood Groups
    elif any(k in q_lower for k in [
        'compatib', 'group', 'type', 'receive', 'donate to', 'o+', 'o-', 'a+', 'a-', 'b+', 'b-', 'ab+', 'ab-',
        'universal donor', 'universal recipient', 'rh factor', 'rh negative', 'rare blood'
    ]):
        reply = KNOWLEDGE_BASE['compatibility']

    # Intent 4: Eligibility Criteria
    elif any(k in q_lower for k in [
        'eligib', 'who can', 'requirement', 'weight', 'age', 'gap', 'interval', 'how often',
        'कति उमेर', 'कति तौल', 'कसले गर्न पाउँछ'
    ]):
        reply = KNOWLEDGE_BASE['eligibility']

    # Intent 5: Before Donation Care
    elif any(k in q_lower for k in ['before', 'prep', 'eat before', 'drink before', 'prior', 'अघि']):
        reply = KNOWLEDGE_BASE['before_donation']

    # Intent 6: After Donation Care
    elif any(k in q_lower for k in ['after', 'post', 'recover', 'care', 'dizzy', 'faint', 'rest', 'पछि']):
        reply = KNOWLEDGE_BASE['after_donation']

    # Intent 7: Hemoglobin & Iron
    elif any(k in q_lower for k in ['hemoglobin', 'hb', 'iron', 'blood count', 'beetroot', 'spinach', 'anemia', 'हिमोग्लोबिन']):
        reply = KNOWLEDGE_BASE['hemoglobin']

    # Intent 8: Greetings / General Help in Nepali
    elif any(k in q_lower for k in ['नमस्ते', 'नमस्कार', 'सोध्न', 'नेपाली']):
        reply = KNOWLEDGE_BASE['nepali_general']

    # Intent 9: Greetings / General Help in English
    elif any(k in q_lower for k in ['hi', 'hello', 'namaste', 'hey', 'start', 'help', 'who are you', 'what can you do']):
        reply = KNOWLEDGE_BASE['default']

    # Intent 10: General Smart Health Guidance Fallback
    else:
        reply = f"""
🏥 **Raktadata Health AI Guidance regarding: "{query_clean}"**

For any health or blood donation query:
- **Finding Blood:** Visit our **[Find Donors](/find-donors)** page to filter active donors by blood group & district, or post a live request on **[Post Blood Request](/blood-request)**.
- **Blood Banks:** Access contacts for Red Cross and hospital transfusion centers on **[Blood Banks](/blood-banks)**.
- **Donor Safety:** Donors must be 18-60 years old, weigh at least 45 kg, have a minimum 12.5 g/dL hemoglobin level, and maintain a 90-day interval between donations.
- **Nutrition:** Maintain healthy hydration (2-3 liters/day) and consume iron-rich foods (spinach, lentils, beetroot, jaggery) paired with Vitamin C.

*Feel free to ask specific questions about blood group compatibility, donor eligibility, medical deferrals, or blood bank locations!*
"""

    return reply.strip() + MEDICAL_DISCLAIMER

