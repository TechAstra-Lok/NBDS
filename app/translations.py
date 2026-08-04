# app/translations.py
# ═══════════════════════════════════════════════
#   Bilingual Translation Dictionary (EN ↔ NE)
# ═══════════════════════════════════════════════

TRANSLATIONS = {
    'en': {
        # ── Navigation ──
        'home': 'Home',
        'blood_requests': 'Blood Requests',
        'find_donors': 'Find Donors',
        'become_donor': 'Become a Donor',
        'news_notices': 'News & Notices',
        'about_us': 'About Us',
        'contact': 'Contact',
        'request_blood': 'Request Blood',
        'search': 'Search',
        'login': 'Login',
        'logout': 'Logout',
        'register': 'Register',
        'profile': 'Profile',
        'dashboard': 'Dashboard',

        # ── Stats ──
        'total_donors': 'Total Donors',
        'available_now': 'Available Now',
        'available': 'Available',
        'total_requests': 'Requests',
        'fulfilled': 'Fulfilled',
        'lives_saved': 'Lives Saved',
        'our_community': 'Our Community',

        # ── Hero Section ──
        'hero_title': 'Save a Life, Donate Blood',
        'hero_subtitle': 'Connect with blood donors in Nepal',
        'search_donors': 'Search Donors',
        'donate_now': 'Donate Now',

        # ── Donor Card ──
        'available_to_donate': 'Available to donate',
        'recently_donated': 'Recently Donated',
        'eligible_after': 'Eligible after',
        'currently_unavailable': 'Currently Unavailable',
        'eligible_to_donate_now': 'Eligible to donate now',
        'last_donated': 'Last donated',
        'never': 'Never',
        'donated_times': 'Donated {count} time(s)',
        'primary_contact': 'Primary Registered Contact',
        'secondary_contact': 'Secondary Contact',
        'not_provided': 'Not provided',
        'copy': 'Copy',
        'social_profile': 'Social Profile',
        'call': 'Call',

        # ── Donor Details ──
        'age': 'Age',
        'weight': 'Weight',
        'blood_group': 'Blood Group',
        'donor_type': 'Donor Type',
        'location': 'Location',
        'last_donation_date': 'Last Donation Date',
        'never_donated_fresh': 'Never Donated / Fresh',
        'social_media_profile': 'Social Media Profile',
        'view_profile': 'View Handle Profile',
        'none_linked': 'None linked',
        'current_residence': 'Current Residence Address',
        'permanent_address': 'Permanent Address',
        'province': 'Province',
        'district': 'District',
        'local_level': 'Local Level',
        'ward': 'Ward',
        'tole': 'Tole',

        # ── Forms ──
        'full_name': 'Full Name',
        'phone_number': 'Phone Number',
        'email': 'Email',
        'select_blood_group': 'Select Blood Group',
        'submit': 'Submit',
        'cancel': 'Cancel',
        'save': 'Save',
        'update': 'Update',
        'delete': 'Delete',
        'confirm': 'Confirm',
        'upload': 'Upload',
        'browse': 'Browse',

        # ── Blood Request ──
        'patient_name': 'Patient Name',
        'hospital': 'Hospital',
        'required_date': 'Required Date',
        'units_needed': 'Units Needed',
        'urgency': 'Urgency',
        'emergency': 'Emergency',
        'normal': 'Normal',
        'contact_number': 'Contact Number',
        'additional_notes': 'Additional Notes',
        'active_requests': 'Active Requests',

        # ── About / Footer ──
        'about_description': 'We connect blood donors with patients in need across Nepal.',
        'quick_links': 'Quick Links',
        'follow_us': 'Follow Us',
        'copyright': '© 2024 Nepali Blood Donors System. All rights reserved.',
        'faq': 'FAQ',
        'donor_guidelines': 'Donor Guidelines',
        'success_stories': 'Success Stories',
        'blood_banks': 'Blood Banks',

        # ── Messages ──
        'no_donors_found': 'No donors found matching your criteria.',
        'registration_success': 'Registration successful!',
        'login_success': 'Login successful!',
        'logout_success': 'Logged out successfully.',
        'request_submitted': 'Blood request submitted successfully.',
        'profile_updated': 'Profile updated successfully.',

        # ── Filters ──
        'filter_by': 'Filter By',
        'all_blood_groups': 'All Blood Groups',
        'all_districts': 'All Districts',
        'all_types': 'All Types',
        'regular': 'Regular',
        'volunteer': 'Volunteer',
        'platelet': 'Platelet',
        'rare': 'Rare',

        # ── Misc ──
        'years_old': 'Years Old',
        'kg': 'kg',
        'browse_directory': 'Browse Directory',
        'register_as_donor': 'Register as Donor',
        'age_requirement': 'Age Requirement Range',
        'weight_metric': 'Weight Metric',
    },
    'ne': {
        # ── Navigation ──
        'home': 'गृहपृष्ठ',
        'blood_requests': 'रक्त अनुरोधहरू',
        'find_donors': 'रक्तदाता खोज्नुहोस्',
        'become_donor': 'रक्तदाता बन्नुहोस्',
        'news_notices': 'समाचार र सूचनाहरू',
        'about_us': 'हाम्रो बारेमा',
        'contact': 'सम्पर्क',
        'request_blood': 'रक्त अनुरोध गर्नुहोस्',
        'search': 'खोज्नुहोस्',
        'login': 'लगइन',
        'logout': 'लगआउट',
        'register': 'दर्ता',
        'profile': 'प्रोफाइल',
        'dashboard': 'ड्यासबोर्ड',

        # ── Stats ──
        'total_donors': 'कुल रक्तदाताहरू',
        'available_now': 'उपलब्ध',
        'available': 'उपलब्ध',
        'total_requests': 'अनुरोधहरू',
        'fulfilled': 'पूरा भएका',
        'lives_saved': 'बचाइएका जीवनहरू',
        'our_community': 'हाम्रो समुदाय',

        # ── Hero Section ──
        'hero_title': 'जीवन बचाउनुहोस्, रक्तदान गर्नुहोस्',
        'hero_subtitle': 'नेपालका रक्तदाताहरूसँग जोडिनुहोस्',
        'search_donors': 'रक्तदाता खोज्नुहोस्',
        'donate_now': 'अहिले दान गर्नुहोस्',

        # ── Donor Card ──
        'available_to_donate': 'रक्तदान गर्न उपलब्ध',
        'recently_donated': 'भर्खरै रक्तदान गरिएको',
        'eligible_after': 'पछि योग्य हुने मिति',
        'currently_unavailable': 'हाल अनुपलब्ध',
        'eligible_to_donate_now': 'अहिले रक्तदान गर्न योग्य',
        'last_donated': 'अन्तिम रक्तदान',
        'never': 'कहिल्यै गरेको छैन',
        'donated_times': '{count} पटक रक्तदान गरिसकेको',
        'primary_contact': 'प्राथमिक सम्पर्क नम्बर',
        'secondary_contact': 'वैकल्पिक सम्पर्क नम्बर',
        'not_provided': 'उपलब्ध छैन',
        'copy': 'कपी',
        'social_profile': 'सामाजिक प्रोफाइल',
        'call': 'कल गर्नुहोस्',

        # ── Donor Details ──
        'age': 'उमेर',
        'weight': 'तौल',
        'blood_group': 'रक्त समूह',
        'donor_type': 'रक्तदाता प्रकार',
        'location': 'स्थान',
        'last_donation_date': 'अन्तिम रक्तदान मिति',
        'never_donated_fresh': 'कहिल्यै रक्तदान गरेको छैन',
        'social_media_profile': 'सामाजिक सञ्जाल प्रोफाइल',
        'view_profile': 'प्रोफाइल हेर्नुहोस्',
        'none_linked': 'कुनै लिंक छैन',
        'current_residence': 'हालको बसोबास ठेगाना',
        'permanent_address': 'स्थायी ठेगाना',
        'province': 'प्रदेश',
        'district': 'जिल्ला',
        'local_level': 'स्थानीय तह',
        'ward': 'वडा',
        'tole': 'टोल',

        # ── Forms ──
        'full_name': 'पूरा नाम',
        'phone_number': 'फोन नम्बर',
        'email': 'इमेल',
        'select_blood_group': 'रक्त समूह छान्नुहोस्',
        'submit': 'पेश गर्नुहोस्',
        'cancel': 'रद्द गर्नुहोस्',
        'save': 'सुरक्षित गर्नुहोस्',
        'update': 'अपडेट गर्नुहोस्',
        'delete': 'मेटाउनुहोस्',
        'confirm': 'पुष्टि गर्नुहोस्',
        'upload': 'अपलोड',
        'browse': 'ब्राउज',

        # ── Blood Request ──
        'patient_name': 'बिरामीको नाम',
        'hospital': 'अस्पताल',
        'required_date': 'आवश्यक मिति',
        'units_needed': 'आवश्यक युनिट',
        'urgency': 'आकस्मिकता',
        'emergency': 'आकस्मिक',
        'normal': 'सामान्य',
        'contact_number': 'सम्पर्क नम्बर',
        'additional_notes': 'थप टिप्पणी',
        'active_requests': 'सक्रिय अनुरोधहरू',

        # ── About / Footer ──
        'about_description': 'हामी नेपालभरका रक्तदाताहरूलाई बिरामीहरूसँग जोड्दछौं।',
        'quick_links': 'द्रुत लिंकहरू',
        'follow_us': 'हामीलाई फलो गर्नुहोस्',
        'copyright': '© २०२४ नेपाली रक्तदान प्रणाली। सर्वाधिकार सुरक्षित।',
        'faq': 'बारम्बार सोधिने प्रश्नहरू',
        'donor_guidelines': 'रक्तदाता मार्गदर्शन',
        'success_stories': 'सफलताका कथाहरू',
        'blood_banks': 'ब्लड बैंकहरू',

        # ── Messages ──
        'no_donors_found': 'तपाईंको खोजसँग मिल्ने कुनै रक्तदाता भेटिएन।',
        'registration_success': 'दर्ता सफल भयो!',
        'login_success': 'लगइन सफल भयो!',
        'logout_success': 'सफलतापूर्वक लगआउट भयो।',
        'request_submitted': 'रक्त अनुरोध सफलतापूर्वक पेश गरियो।',
        'profile_updated': 'प्रोफाइल सफलतापूर्वक अपडेट गरियो।',

        # ── Filters ──
        'filter_by': 'फिल्टर गर्नुहोस्',
        'all_blood_groups': 'सबै रक्त समूह',
        'all_districts': 'सबै जिल्ला',
        'all_types': 'सबै प्रकार',
        'regular': 'नियमित',
        'volunteer': 'स्वयंसेवक',
        'platelet': 'प्लेटलेट',
        'rare': 'दुर्लभ',

        # ── Misc ──
        'years_old': 'वर्ष',
        'kg': 'केजी',
        'browse_directory': 'डाइरेक्टरी हेर्नुहोस्',
        'register_as_donor': 'रक्तदाताको रूपमा दर्ता गर्नुहोस्',
        'age_requirement': 'उमेर आवश्यकता',
        'weight_metric': 'तौल मापदण्ड',
    }
}


def get_translation(lang='en'):
    """Return the translation dictionary for the given language."""
    return TRANSLATIONS.get(lang, TRANSLATIONS['en'])
