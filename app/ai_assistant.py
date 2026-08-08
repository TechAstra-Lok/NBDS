# app/ai_assistant.py
# ════════════════════════════════════════════════════════════════
#   Raktadata Health & Blood AI Assistant (Doctor & Nurse Persona)
# ════════════════════════════════════════════════════════════════

import os
import re

SYSTEM_PROMPT = """
You are "Raktadata AI Assistant", an expert Medical Doctor and Health Guidance Assistant specialized strictly in:
1. Blood donation guidelines, donor eligibility, and intervals.
2. Blood group compatibility (ABO & Rh system).
3. Pre-donation and post-donation care, hydration, and nutrition.
4. Hemoglobin level improvement, iron-rich diet, and healthy lifestyle habits.
5. General health tips, wellness advice, and blood donor safety.

Rules:
- Be warm, empathetic, professional, and clear.
- Keep responses well-structured with bullet points where appropriate.
- If a query is NOT related to health, medical advice, blood donation, nutrition, or blood groups, politely decline: "I am specifically trained as a Health & Blood Donation Assistant. Please feel free to ask me any question about blood groups, donation eligibility, health tips, or donor nutrition!"
- Always emphasize safety and donor well-being.
"""

MEDICAL_DISCLAIMER = "\n\n*⚠️ Medical Disclaimer: This AI assistant provides general health guidance and blood donation information. For acute medical emergencies or diagnosis, please consult a certified healthcare professional immediately.*"

# Knowledge base fallback answers for key medical / blood queries when no API key is configured
KNOWLEDGE_BASE = {
    'compatibility': """
🩸 **Blood Group Compatibility Guide:**

- **O negative (O-):** Universal donor for red blood cells. Can donate to all blood types!
- **AB positive (AB+):** Universal recipient for red blood cells. Can receive from all blood types!
- **O positive (O+):** Can donate to O+, A+, B+, AB+.
- **A positive (A+):** Can donate to A+, AB+. Can receive from A+, A-, O+, O-.
- **B positive (B+):** Can donate to B+, AB+. Can receive from B+, B-, O+, O-.
- **A negative (A-):** Can donate to A+, A-, AB+, AB-.
- **B negative (B-):** Can donate to B+, B-, AB+, AB-.
- **AB negative (AB-):** Can donate to AB+, AB-.

*Need urgent blood in Nepal? Use our [Find Donors](/find-donors) page or submit a [Blood Request](/blood-request)!*
""",
    'eligibility': """
📋 **Basic Blood Donor Eligibility Criteria:**

1. **Age:** 18 – 60 years old (18–65 in some medical centers).
2. **Weight:** Minimum 45 kg (100 lbs).
3. **Donation Interval:** At least 90 days (3 months) between whole blood donations for males & females.
4. **Hemoglobin:** Minimum 12.5 g/dL.
5. **Blood Pressure & Pulse:** Systolic 100-140 mmHg, Diastolic 60-90 mmHg, Pulse 60-100 bpm.
6. **Health Status:** Free from acute infections, fever, active cold/flu, or major surgery in the last 6 months.

*Tip: Make sure you get 7-8 hours of sleep and eat a light meal before donating!*
""",
    'before_donation': """
🍎 **Pre-Donation Preparation & Health Tips:**

1. **Hydrate Well:** Drink at least 500ml (2-3 glasses) of water or fruit juice 1-2 hours before donating.
2. **Eat Healthy:** Have a healthy, non-fatty meal 2-3 hours before donation. Avoid high-fat foods like fried snacks as they can affect blood testing.
3. **Rest:** Ensure at least 7-8 hours of sound sleep the night before.
4. **Avoid Alcohol & Smoking:** Avoid alcohol for 24 hours and refrain from smoking for at least 2 hours before donation.
5. **ID & History:** Bring a valid photo ID and know your basic medical history.
""",
    'after_donation': """
💪 **Post-Donation Care & Fast Recovery Guidance:**

1. **Rest & Snacks:** Sit in the refreshment area for 10-15 minutes after donation and consume juice/biscuits provided.
2. **Extra Fluids:** Drink extra fluids (water, juice, coconut water) over the next 24-48 hours.
3. **Avoid Heavy Lifting:** Avoid strenuous physical exercise or heavy lifting with your donation arm for the rest of the day.
4. **Keep Bandage On:** Keep the bandage on your arm for 4-5 hours.
5. **Feeling Dizzy?** If you feel lightheaded, lie down immediately with your legs elevated until the feeling passes.
""",
    'hemoglobin': """
🥦 **How to Naturaly Boost Hemoglobin & Iron Levels:**

1. **Iron-Rich Plant Foods:** Spinach, fenugreek (methi), beetroot, lentils, beans, chickpeas, sesame seeds, and jaggery (gud).
2. **Iron-Rich Animal Foods:** Lean red meat, liver, poultry, and fish.
3. **Vitamin C Pairings:** Vitamin C increases iron absorption! Combine iron-rich foods with lemons, oranges, tomatoes, or amla.
4. **Avoid Inhibitors:** Avoid drinking tea, coffee, or milk immediately with meals as calcium and tannins hinder iron absorption.
""",
    'default': """
🏥 **Welcome to Raktadata Health & Blood AI Guidance!**

I am here to help you with:
- **Blood Donor Eligibility & Intervals** (minimum age, weight, donation gap)
- **Blood Group Compatibility** (O-, AB+, A+, B+, etc.)
- **Pre & Post Donation Health Care** (hydration, rest, recovery)
- **Hemoglobin & Iron Diet Tips** (natural ways to boost blood levels)
- **General Health & Wellness Guidance**

*How can I assist your health and blood donation journey today?*
"""
}


def generate_ai_response(user_query: str) -> str:
    """
    Generates a specialized health response using Gemini API, OpenAI, or Smart Knowledge Fallback.
    """
    query_clean = user_query.strip()
    if not query_clean:
        return "Please ask a question about health, blood groups, or blood donation eligibility."
    
    # 1. Try Google Gemini API
    gemini_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {query_clean}"
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip() + MEDICAL_DISCLAIMER
        except Exception as e:
            pass

    # 2. Try OpenAI API
    openai_key = os.environ.get('OPENAI_API_KEY')
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
                max_tokens=500,
                temperature=0.7,
            )
            if completion.choices and completion.choices[0].message.content:
                return completion.choices[0].message.content.strip() + MEDICAL_DISCLAIMER
        except Exception:
            pass

    # 3. Rule-Based Smart Knowledge Engine Fallback (guarantees responses 24/7)
    q_lower = query_clean.lower()
    
    if any(k in q_lower for k in ['compatib', 'group', 'type', 'receive', 'donate to', 'o+', 'o-', 'a+', 'b+', 'ab+']):
        reply = KNOWLEDGE_BASE['compatibility']
    elif any(k in q_lower for k in ['eligib', 'who can', 'requirement', 'weight', 'age', 'gap', 'interval', 'how often']):
        reply = KNOWLEDGE_BASE['eligibility']
    elif any(k in q_lower for k in ['before', 'prep', 'eat before', 'drink before', 'prior']):
        reply = KNOWLEDGE_BASE['before_donation']
    elif any(k in q_lower for k in ['after', 'post', 'recover', 'care', 'dizzy', 'faint', 'rest']):
        reply = KNOWLEDGE_BASE['after_donation']
    elif any(k in q_lower for k in ['hemoglobin', 'hb', 'iron', 'blood count', 'beetroot', 'spinach', 'anemia']):
        reply = KNOWLEDGE_BASE['hemoglobin']
    elif any(k in q_lower for k in ['hi', 'hello', 'namaste', 'hey', 'start', 'help']):
        reply = KNOWLEDGE_BASE['default']
    else:
        # General smart health response
        reply = f"Thank you for reaching out to Raktadata Health Guidance! Regarding **\"{query_clean}\"**:\n\nFor blood donation safety, maintaining adequate hydration (minimum 2-3 liters water/day), iron-rich nutrition (greens, legumes), and 90 days gap between blood donations is key. If you are experiencing any abnormal symptoms, we strongly recommend consulting a physician.\n\nFeel free to ask about **blood group compatibility**, **donor eligibility**, or **pre/post donation tips**!"

    return reply.strip() + MEDICAL_DISCLAIMER
