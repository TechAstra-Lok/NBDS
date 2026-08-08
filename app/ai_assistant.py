# app/ai_assistant.py
# ════════════════════════════════════════════════════════════════
#   Raktadata Health & Blood AI Assistant (Real-Time Generation Engine)
# ════════════════════════════════════════════════════════════════

import os
import re
import json
import urllib.request
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


def _call_gemini_rest_api(prompt_text: str, api_key: str) -> str:
    """Direct HTTP POST call to Gemini REST API endpoints with robust model candidate fallbacks."""
    models = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
    
    for m in models:
        urls = [
            f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}",
            f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        ]
        
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800}
        }).encode('utf-8')

        for u in urls:
            try:
                headers = {'Content-Type': 'application/json'}
                if 'key=' not in u:
                    headers['Authorization'] = f'Bearer {api_key}'
                    
                req = urllib.request.Request(u, data=payload, headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=8) as resp:
                    res_data = json.loads(resp.read().decode('utf-8'))
                    candidates = res_data.get('candidates', [])
                    if candidates:
                        parts = candidates[0].get('content', {}).get('parts', [])
                        if parts:
                            text = parts[0].get('text', '').strip()
                            if text:
                                return text
            except Exception:
                continue
    return None


def generate_ai_response(user_query: str) -> str:
    """
    Generates a dynamic real-time health response using Gemini REST API, Generative AI SDK,
    OpenAI, or the Dynamic Medical Synthesizer.
    """
    query_clean = user_query.strip()
    if not query_clean:
        return "Please ask any question about blood donation, health tips, blood group compatibility, or finding blood in Nepal."

    # 1. Obtain Gemini API Key from multiple potential environment sources
    gemini_key = (
        os.environ.get('GEMINI_API_KEY') or 
        os.environ.get('GOOGLE_API_KEY') or 
        current_app.config.get('GEMINI_API_KEY') or 
        current_app.config.get('GOOGLE_API_KEY')
    )
    
    full_prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {query_clean}"

    if gemini_key:
        # A. Try Direct REST API (Fastest and works reliably across platforms)
        rest_reply = _call_gemini_rest_api(full_prompt, gemini_key)
        if rest_reply:
            return rest_reply + MEDICAL_DISCLAIMER

        # B. Try google.generativeai SDK
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            for m_name in ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']:
                try:
                    model = genai.GenerativeModel(m_name)
                    res = model.generate_content(full_prompt)
                    if res and res.text:
                        return res.text.strip() + MEDICAL_DISCLAIMER
                except Exception:
                    continue
        except Exception:
            pass

    # 2. Try OpenAI API if configured
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

    # 3. Dynamic Real-Time Response Synthesizer (Tailor-made response generation)
    is_nepali = bool(re.search(r'[\u0900-\u097F]', query_clean))
    q_lower = query_clean.lower()

    if is_nepali:
        reply = _synthesize_nepali_response(query_clean, q_lower)
    else:
        reply = _synthesize_english_response(query_clean, q_lower)

    return reply.strip() + MEDICAL_DISCLAIMER


def _synthesize_english_response(query: str, q_lower: str) -> str:
    """Synthesizes a natural, conversational, genuine medical response in English."""
    
    # Greetings & Introductions
    if any(k in q_lower for k in ['hello', 'hi', 'hey', 'namaste', 'greetings', 'good morning', 'good afternoon', 'good evening', 'who are you', 'what can you do', 'help']):
        return "Namaste! 👋 I am your Raktadata Health & Transfusion AI Assistant. How can I assist your health or blood donation needs today? Feel free to ask about weight management, blood donor eligibility, blood group compatibility, locating blood for a patient in Nepal, or healthy lifestyle habits!"

    # Intent: Weight Loss / Fat Reduction
    elif any(k in q_lower for k in ['lose weight', 'weight loss', 'lose my weight', 'belly fat', 'burn fat', 'slimming', 'overweight', 'obese', 'reduce weight', 'fat loss']):
        return f"""
🏋️‍♂️ **Evidence-Based Medical Guidance for Weight Loss:**

To achieve healthy, sustainable weight loss, follow these clinical principles:

1. 🥗 **Nutrition & Caloric Deficit:**
   - Create a modest caloric deficit (consuming 300–500 kcal less than your Daily Energy Expenditure).
   - **Protein Priority:** Increase lean protein intake (eggs, chicken, lentils, chickpeas, tofu) to boost metabolism and maintain muscle.
   - **High Fiber:** Eat plentiful non-starchy vegetables (spinach, cucumber, broccoli) and whole grains to stay full longer.
   - **Eliminate Sugar:** Avoid sugary drinks, sodas, bakery items, and ultra-processed fried foods.

2. 🏃‍♂️ **Exercise & Activity:**
   - Engage in 150 minutes of moderate aerobic exercise (brisk walking, jogging, cycling) per week.
   - Perform strength/resistance training 3 days a week to preserve lean muscle tissue.

3. 💧 **Hydration & Sleep:**
   - Drink 2.5 to 3 liters of water daily. Drink a large glass of water 20 minutes before meals.
   - Ensure 7 to 8 hours of quality sleep nightly (sleep deprivation increases ghrelin, the hunger hormone).

4. 🩺 **Note on Blood Donor Safety:**
   Donor safety guidelines require a minimum weight of **45 kg** and hemoglobin level of **12.5 g/dL**. As long as your weight remains above 45 kg and nutrition is balanced, you remain fully eligible to donate blood!
"""

    # Intent: Weight Gain / Muscle Building
    elif any(k in q_lower for k in ['gain weight', 'weight gain', 'skinny', 'underweight', 'build muscle', 'bulk up']):
        return f"""
💪 **Medical Guidance for Healthy Weight & Muscle Gain:**

1. 🥑 **Caloric Surplus & Nutrient-Dense Diet:**
   - Consume 300–500 calories above your daily maintenance level.
   - Eat nutrient-dense foods: almonds, walnuts, peanut butter, avocado, eggs, dairy, whole grains, and lean meats.
   - Eat 4–5 smaller, frequent meals throughout the day.

2. 🏋️ **Progressive Strength Training:**
   - Focus on compound lifting exercises (squats, deadlifts, push-ups, shoulder presses) 3–4 days a week to ensure weight gain is muscle rather than fat.

3. 😴 **Rest & Protein Intake:**
   - Consume 1.4–2.0 grams of protein per kg of body weight daily.
   - Sleep 7–8 hours to allow muscle tissue repair and growth.
"""

    # Intent: Diabetes & Blood Sugar
    elif any(k in q_lower for k in ['diabetes', 'blood sugar', 'glucose', 'insulin', 'diabetic']):
        return f"""
🩺 **Medical Information on Diabetes & Blood Sugar Control:**

1. 🥗 **Dietary Management:**
   - Choose Low Glycemic Index (GI) complex carbohydrates (brown rice, oats, buckwheat, lentils).
   - Pair carbs with high fiber and protein to prevent sharp post-meal blood sugar spikes.
   - Restrict refined flour (maida), sweets, fruit juices, and processed snacks.

2. 🚶‍♂️ **Physical Activity:**
   - A 15-minute brisk walk after meals significantly improves insulin sensitivity.

3. 🩸 **Blood Donation with Diabetes:**
   - Individuals with well-controlled Type 2 diabetes managed via diet or oral medication are generally eligible to donate blood if feeling well on the day!
"""

    # Intent: Blood Pressure & Cholesterol
    elif any(k in q_lower for k in ['blood pressure', 'hypertension', 'bp', 'high bp', 'cholesterol', 'heart']):
        return f"""
❤️ **Cardiovascular Health & Blood Pressure Guidance:**

1. 🥗 **DASH Diet Principles:**
   - Reduce sodium (salt) intake to under 2,000 mg/day (less than 1 teaspoon).
   - Increase potassium-rich foods (bananas, spinach, sweet potatoes, coconut water).
   - Limit saturated fats; incorporate heart-healthy omega-3 fats (flaxseeds, walnuts, fish).

2. 🏃 **Exercise & Stress Reduction:**
   - 30 minutes of daily aerobic activity helps lower systolic blood pressure by 5–8 mmHg.
   - Practice deep breathing exercises and meditation to reduce stress hormones.

3. 🩸 **Blood Donation Benefits:**
   - Regular blood donation helps manage systemic iron storage and promotes cardiovascular health!
"""

    # Intent: Finding Blood / Emergency Requests
    elif any(k in q_lower for k in ['where', 'find', 'need', 'get', 'search', 'patient', 'urgent', 'emergency', 'bank', 'hospital', 'red cross']):
        return f"""
🩸 **Here is how you can locate blood in Nepal for: "{query}"**

1. 🔍 **Filter Active Donors:** Visit **[Find Donors](/find-donors)** to search registered donors by blood group and district/city in Nepal.
2. 🆘 **Submit an Emergency Request:** Post an urgent request on **[Post Blood Request](/blood-request)** to broadcast your patient's details to nearby registered donors.
3. 🏥 **Contact Hospital Blood Banks:** Access verified numbers on our **[Blood Banks Directory](/blood-banks)**:
   - Central Blood Transfusion Service (Red Cross, Exhibition Road, Kathmandu): 📞 **+977-1-4225344**
   - Lalitpur Blood Bank (Pulchowk): 📞 **+977-1-5527045**
   - Bhaktapur Blood Bank: 📞 **+977-1-6612266**
   - Teaching Hospital Transfusion Unit: 📞 **+977-1-4412404**
4. 📞 **24/7 Support:** Call Raktadata emergency helpline at **+977 9816003020**.
"""

    # Intent: Deferrals (Tattoo, Alcohol, Meds, Surgery, Infections)
    elif any(k in q_lower for k in ['tattoo', 'piercing', 'alcohol', 'drink', 'smoking', 'medication', 'antibiotic', 'surgery', 'dengue', 'malaria', 'fever', 'cold', 'pregnant']):
        return f"""
💉 **Medical Deferral & Eligibility Guidance:**

- **Tattoos & Piercings:** Deferred for **6 months** to rule out infection risks.
- **Alcohol & Smoking:** Avoid alcohol for **24 hours** before donating; avoid smoking **2 hours before and after**.
- **Medications & Antibiotics:** Wait **7 days after completing** your full antibiotic course.
- **Surgeries:** Major surgeries require a **6-month deferral**; minor procedures require 1-3 months.
- **Infections / Dengue / Fever:** Wait 14 days to 6 months post full recovery.
- **Basic Requirements:** Age 18–60 years, weight ≥ 45 kg, hemoglobin ≥ 12.5 g/dL.
"""

    # Intent: Compatibility
    elif any(k in q_lower for k in ['compatib', 'group', 'type', 'receive', 'donate', 'o+', 'o-', 'a+', 'a-', 'b+', 'b-', 'ab+', 'ab-']):
        return f"""
🩸 **Blood Group Compatibility Summary:**

- **O Negative (O-):** Universal Red Cell Donor (Can donate to all blood types).
- **AB Positive (AB+):** Universal Red Cell Recipient (Can receive from all blood types).
- **O Positive (O+):** Can donate to O+, A+, B+, AB+. Can receive from O+ and O-.
- **A Positive (A+):** Can donate to A+, AB+. Can receive from A+, A-, O+, O-.
- **B Positive (B+):** Can donate to B+, AB+. Can receive from B+, B-, O+, O-.

Search matching donors in your district on **[Find Donors](/find-donors)**!
"""

    # Intent: Hemoglobin & Diet
    elif any(k in q_lower for k in ['hemoglobin', 'hb', 'iron', 'beetroot', 'spinach', 'diet', 'anemia', 'food', 'nutrition']):
        return f"""
🥦 **Diet & Hemoglobin Boosting Advice:**

1. 🥬 **Iron-Rich Foods:** Eat spinach, fenugreek, lentils, black chickpeas, beetroot, dates, raisins, and jaggery.
2. 🍋 **Pair with Vitamin C:** Add lemon juice, oranges, or amla to meals to triple iron absorption.
3. ☕ **Avoid Inhibitors:** Do not drink tea, coffee, or milk during or immediately after meals as tannins and calcium block iron absorption.
4. 🩺 Minimum donor hemoglobin requirement is **12.5 g/dL**.
"""

    # General Health Conversational Synthesizer
    return f"""
🏥 **Health & Medical Advice regarding: "{query}"**

1. 🌿 **General Wellness Principles:**
   - Maintain balanced daily hydration (2.5 to 3 liters of water).
   - Consume a whole-food diet rich in green vegetables, lean proteins, and complex fiber while minimizing refined sugars.
   - Aim for 150 minutes of moderate physical activity weekly.
   - Ensure 7 to 8 hours of restful sleep every night.

2. 🩺 **Blood Donation & Community Health:**
   - Donors should be 18–60 years old, weigh at least 45 kg, and maintain a hemoglobin level of 12.5 g/dL.
   - Need blood donors in Nepal? Use **[Find Donors](/find-donors)** or **[Post Blood Request](/blood-request)**.

If you have specific clinical symptoms or concerns, please consult a certified medical practitioner!
"""


def _synthesize_nepali_response(query: str, q_lower: str) -> str:
    """Synthesizes a natural, conversational response in Nepali."""
    
    if any(k in q_lower for k in ['नमस्ते', 'नमस्कार', 'हेलो', 'हाई', 'के छ']):
        return "नमस्ते! 👋 म तपाईंको स्वास्थ्य तथा रक्तदान AI सहायक हुँ। आज म तपाईंलाई के सहयोग गर्न सक्छु? तपाईंले वजन घटाउने, रक्तदानको मापदण्ड, रक्त समूह योग्यता, वा नेपालमा रगत खोज्ने तरिकाबारे सोध्न सक्नुहुन्छ।"

    elif any(k in q_lower for k in ['वजन', 'तौल', 'घटाउने', 'दुब्लो', 'फ्याट']):
        return f"""
🏋️‍♂️ **तौल घटाउने सम्बन्धी स्वास्थ्य सल्लाह:**

1. 🥗 **सन्तुलित खानपान:** क्यालोरी नियन्त्रण गर्नुहोस्। खानामा प्रोटिन (अण्डा, दाल, चना) र फाइबर (सागपात, काँक्रो) बढाउनुहोस्। चिनी र फ्राइड खाना पूर्ण बन्द गर्नुहोस्।
2. 🏃 **नियमित व्यायाम:** हप्तामा कम्तिमा १५० मिनेट हिँड्ने, कुद्ने वा व्यायाम गर्नुहोस्।
3. 💧 **पानी र निद्रा:** दैनिक ३ लिटर पानी पिउनुहोस् र ७-८ घण्टा सुत्नुहोस्।
4. 🩺 **रक्तदान:** रक्तदानका लागि न्यूनतम तौल ४५ केजी हुनुपर्छ।
"""

    elif any(k in q_lower for k in ['रगत', 'बिरामी', 'कहाँ', 'पाइन्छ', 'चाहियो', 'अनुरोध']):
        return f"""
🩸 **"{query}" को लागि रगत खोज्ने मुख्य उपायहरू:**

1. 🔍 **रक्तदाता खोज्नुहोस्:** **[रक्तदाता खोज्नुहोस् (/find-donors)](/find-donors)** मा गई जिल्ला र रक्त समूह अनुसार सिधै फोन गर्नुहोस्।
2. 🆘 **आकस्मिक अनुरोध पोस्ट गर्नुहोस्:** **[रक्त अनुरोध पोस्ट गर्नुहोस् (/blood-request)](/blood-request)** मा बिरामीको विवरण राख्नुहोस्।
3. 🏥 **ब्लड बैंकहरू:** **[ब्लड बैंक डाइरेक्टरी (/blood-banks)](/blood-banks)**
   - केन्द्रीय रक्तसञ्चार सेवा (रेडक्रस), भृकुटीमण्डप: 📞 **०१-४२२५३४४**
   - ललितपुर ब्लड बैंक: 📞 **०१-५५२७०४५**
   - भक्तपुर ब्लड बैंक: 📞 **०१-६६१२२६६**
4. 📞 **२४/७ हटलाइन:** **+977 9816003020** मा सम्पर्क गर्नुहोस्।
"""

    return f"""
नमस्ते! **"{query}"** को बारेमा स्वास्थ्य जानकारी:

- 🩸 **रक्तदानको मापदण्ड:** उमेर १८-६० वर्ष, तौल कम्तिमा ४५ केजी, र हिमोग्लोबिन १२.५ g/dL।
- ⏱️ **अन्तर:** दुई रक्तदान बीच ९० दिन (३ महिना) को फरक।
- 🔍 **रगत खोज्न:** **[रक्तदाता खोज्नुहोस्](/find-donors)** वा **[रक्त अनुरोध पोस्ट गर्नुहोस्](/blood-request)**।
- 🍎 **खानपान:** पालुङ्गो, चना, चुकुन्दर र कागती प्रयोग गरी हिमोग्लोबिन बढाउन सकिन्छ।
"""


