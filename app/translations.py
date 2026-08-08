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
        'hero_badge': 'Save Lives in Nepal',
        'hero_heading_1': 'Donate Blood,',
        'hero_heading_2': 'Save Lives!',
        'hero_desc': 'Join Nepal\'s largest blood donor network. Your single donation can save up to 3 lives.',
        'hero_donate_blood': 'Donate Blood · Save Lives',
        'search_donors': 'Search Donors',
        'donate_now': 'Donate Now',
        'request_blood_btn': 'Request Blood',
        'become_donor_btn': 'Become a Donor',
        'find_donors_btn': 'Find Donors',
        'quick_find_bg': 'Quick Find by Blood Group:',

        # ── Emergency Blood Requests (Index) ──
        'emergency_blood_requests': 'Emergency Blood Requests',
        'active_requests_needing': 'Active requests needing immediate attention',
        'view_all': 'View All',
        'post_request': 'Post Request',
        'urgent': 'URGENT',
        'units_needed_label': 'unit(s) needed',
        'no_active_requests': 'No Active Blood Requests',
        'no_active_requests_desc': 'Great news! No urgent requests at the moment.',

        # ── Search Donors Section (Index) ──
        'find_blood_donors': 'Find Blood Donors',
        'search_area_desc': 'Search for available donors in your area',
        'blood_group_label': 'Blood Group',
        'district_placeholder': 'District (e.g. Kathmandu)',
        'city_placeholder': 'City / Town',
        'search_donors_btn': 'Search Donors',

        # ── Blood Group Stats ──
        'donors_by_bg': 'Donors by Blood Group',
        'total': 'total',

        # ── Latest News (Index) ──
        'latest_news': 'Latest News & Events',
        'stay_updated': 'Stay updated with blood donation activities',
        'read_more': 'Read More',

        # ── Success Stories (Index) ──
        'success_stories': 'Success Stories',
        'real_lives_saved': 'Real lives saved through blood donation',
        'all_stories': 'All Stories',
        'read_story': 'Read Story',

        # ── Sidebar ──
        'latest_notices': 'Latest Notices',
        'days_left': 'd left',
        'donate_blood_today': 'Donate Blood Today!',
        'donate_blood_cta': 'You could be the reason someone survives. Register as a donor now.',
        'register_as_donor': 'Register as Donor',
        'sponsored': 'Sponsored',

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

        # ── Blood Request Board ──
        'blood_request_board': 'Blood Request Board',
        'showing_all_requests': 'Showing all blood requests. Latest requests appear first.',
        'post_blood_request': 'Post Blood Request',
        'manage_your_request': 'Manage Your Request',
        'active': 'Active',
        'closed': 'Closed',
        'all': 'All',

        # ── About / Footer ──
        'about_description': 'We connect blood donors with patients in need across Nepal.',
        'quick_links': 'Quick Links',
        'follow_us': 'Follow Us',
        'copyright': '© 2024 Nepali Blood Donors System. All rights reserved.',
        'faq': 'FAQ',
        'donor_guidelines': 'Donor Guidelines',
        'blood_banks': 'Blood Banks',

        # ── Footer Bottom ──
        'privacy_policy': 'Privacy Policy',
        'terms_of_use': 'Terms of Use',
        'admin_portal': 'Admin Portal',
        'contact_developer': 'Contact Developer',
        'all_rights_reserved': 'All rights reserved.',
        'founded_by': 'Founded By',
        'in_nepal': 'in Nepal.',

        # ── News Page ──
        'news_and_notices': 'News & Notices',
        'latest_updates': 'Latest blood donation updates and announcements',
        'no_news': 'No news articles published yet.',

        # ── Contact Page ──
        'contact_us': 'Contact Us',
        'get_in_touch': 'Get in touch with us',
        'send_message': 'Send Message',
        'your_message': 'Your Message',
        'contact_info': 'Contact Information',
        'address': 'Address',

        # ── About Page ──
        'our_mission': 'Our Mission',
        'our_vision': 'Our Vision',
        'who_we_are': 'Who We Are',

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
        'age_requirement': 'Age Requirement Range',
        'weight_metric': 'Weight Metric',
        'phone_copied': 'Phone number copied!',
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
        'hero_badge': 'नेपालमा जीवन बचाउनुहोस्',
        'hero_heading_1': 'रगत दान गर्नुहोस्,',
        'hero_heading_2': 'जीवन बचाउनुहोस्!',
        'hero_desc': 'नेपालको सबैभन्दा ठूलो रक्तदाता नेटवर्कमा सामेल हुनुहोस्। तपाईंको एक पटकको रक्तदानले ३ जनासम्मको जीवन बचाउन सक्छ।',
        'hero_donate_blood': 'रक्तदान गर्नुहोस् · जीवन बचाउनुहोस्',
        'search_donors': 'रक्तदाता खोज्नुहोस्',
        'donate_now': 'अहिले दान गर्नुहोस्',
        'request_blood_btn': 'रक्त अनुरोध गर्नुहोस्',
        'become_donor_btn': 'रक्तदाता बन्नुहोस्',
        'find_donors_btn': 'रक्तदाता खोज्नुहोस्',
        'quick_find_bg': 'रक्त समूह अनुसार द्रुत खोजी:',

        # ── Emergency Blood Requests (Index) ──
        'emergency_blood_requests': 'आकस्मिक रक्त अनुरोधहरू',
        'active_requests_needing': 'तत्काल ध्यान चाहिने सक्रिय अनुरोधहरू',
        'view_all': 'सबै हेर्नुहोस्',
        'post_request': 'अनुरोध पोस्ट गर्नुहोस्',
        'urgent': 'अत्यावश्यक',
        'units_needed_label': 'युनिट चाहिन्छ',
        'no_active_requests': 'कुनै सक्रिय रक्त अनुरोध छैन',
        'no_active_requests_desc': 'राम्रो खबर! हाल कुनै आकस्मिक अनुरोध छैन।',

        # ── Search Donors Section (Index) ──
        'find_blood_donors': 'रक्तदाता खोज्नुहोस्',
        'search_area_desc': 'तपाईंको क्षेत्रमा उपलब्ध रक्तदाता खोज्नुहोस्',
        'blood_group_label': 'रक्त समूह',
        'district_placeholder': 'जिल्ला (जस्तै काठमाडौं)',
        'city_placeholder': 'शहर / नगर',
        'search_donors_btn': 'रक्तदाता खोज्नुहोस्',

        # ── Blood Group Stats ──
        'donors_by_bg': 'रक्त समूह अनुसार रक्तदाताहरू',
        'total': 'कुल',

        # ── Latest News (Index) ──
        'latest_news': 'ताजा समाचार र कार्यक्रमहरू',
        'stay_updated': 'रक्तदान गतिविधिहरूको बारेमा अपडेट रहनुहोस्',
        'read_more': 'थप पढ्नुहोस्',

        # ── Success Stories (Index) ──
        'success_stories': 'सफलताका कथाहरू',
        'real_lives_saved': 'रक्तदानबाट बचाइएका वास्तविक जीवनहरू',
        'all_stories': 'सबै कथाहरू',
        'read_story': 'कथा पढ्नुहोस्',

        # ── Sidebar ──
        'latest_notices': 'ताजा सूचनाहरू',
        'days_left': 'दिन बाँकी',
        'donate_blood_today': 'आज रक्तदान गर्नुहोस्!',
        'donate_blood_cta': 'तपाईं नै कसैको जीवन बचाउने कारण हुन सक्नुहुन्छ। अहिले दर्ता गर्नुहोस्।',
        'register_as_donor': 'रक्तदाताको रूपमा दर्ता गर्नुहोस्',
        'sponsored': 'प्रायोजित',

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

        # ── Blood Request Board ──
        'blood_request_board': 'रक्त अनुरोध बोर्ड',
        'showing_all_requests': 'सबै रक्त अनुरोधहरू देखाइँदैछ। नवीनतम अनुरोधहरू पहिले देखिन्छ।',
        'post_blood_request': 'रक्त अनुरोध पोस्ट गर्नुहोस्',
        'manage_your_request': 'तपाईंको अनुरोध व्यवस्थापन',
        'active': 'सक्रिय',
        'closed': 'बन्द',
        'all': 'सबै',

        # ── About / Footer ──
        'about_description': 'हामी नेपालभरका रक्तदाताहरूलाई बिरामीहरूसँग जोड्दछौं।',
        'quick_links': 'द्रुत लिंकहरू',
        'follow_us': 'हामीलाई फलो गर्नुहोस्',
        'copyright': '© २०२४ नेपाली रक्तदान प्रणाली। सर्वाधिकार सुरक्षित।',
        'faq': 'बारम्बार सोधिने प्रश्नहरू',
        'donor_guidelines': 'रक्तदाता मार्गदर्शन',
        'blood_banks': 'ब्लड बैंकहरू',

        # ── Footer Bottom ──
        'privacy_policy': 'गोपनीयता नीति',
        'terms_of_use': 'सेवा सर्तहरू',
        'admin_portal': 'एडमिन पोर्टल',
        'contact_developer': 'विकासकर्तालाई सम्पर्क गर्नुहोस्',
        'all_rights_reserved': 'सर्वाधिकार सुरक्षित।',
        'founded_by': 'स्थापना गर्नुभएको',
        'in_nepal': 'नेपालमा।',

        # ── News Page ──
        'news_and_notices': 'समाचार र सूचनाहरू',
        'latest_updates': 'ताजा रक्तदान अपडेट र घोषणाहरू',
        'no_news': 'अहिलेसम्म कुनै समाचार प्रकाशित भएको छैन।',

        # ── Contact Page ──
        'contact_us': 'हामीलाई सम्पर्क गर्नुहोस्',
        'get_in_touch': 'हामीसँग सम्पर्कमा रहनुहोस्',
        'send_message': 'सन्देश पठाउनुहोस्',
        'your_message': 'तपाईंको सन्देश',
        'contact_info': 'सम्पर्क जानकारी',
        'address': 'ठेगाना',

        # ── About Page ──
        'our_mission': 'हाम्रो लक्ष्य',
        'our_vision': 'हाम्रो दृष्टिकोण',
        'who_we_are': 'हामी को हौं',

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
        'phone_copied': 'फोन नम्बर कपी भयो!',
    }
}


def get_translation(lang='en'):
    """Return the translation dictionary for the given language."""
    return TRANSLATIONS.get(lang, TRANSLATIONS['en'])

