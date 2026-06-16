from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, abort, current_app, render_template_string, Response
)
from app import db
from app.models import Donor, BloodRequest, News, Notice, Advertisement, Contact, SiteVisitor
from app.forms import BloodRequestForm, DonorRegistrationForm, ContactForm, RequestManagementForm
from difflib import SequenceMatcher
from app.utils import paginate_query, get_blood_group_stats, sanitize_html
from sqlalchemy import desc, or_, func
from urllib.parse import urlparse
from datetime import datetime, timedelta, date

public_bp = Blueprint('public', __name__)

@public_bp.route('/sitemap.xml', methods=['GET'])
def sitemap():
    # Build a simple sitemap including index, news items, and notices
    pages = []
    pages.append((url_for('public.index', _external=True), datetime.utcnow().date().isoformat()))
    pages.append((url_for('public.news_list', _external=True), datetime.utcnow().date().isoformat()))
    # include first few paginated news pages
    try:
        news_count = News.query.filter_by(is_published=True).count()
        per_page = current_app.config.get('NEWS_PER_PAGE', 10)
        total_pages = max(1, (news_count // per_page) + (1 if news_count % per_page else 0))
        # limit sitemap pagination to first 5 pages to avoid huge sitemaps
        for p in range(1, min(total_pages, 5) + 1):
            pages.append((url_for('public.news_list', page=p, _external=True), datetime.utcnow().date().isoformat()))
    except Exception:
        pass
    pages.append((url_for('public.blood_request_board', _external=True), datetime.utcnow().date().isoformat()))
    pages.append((url_for('public.contact', _external=True), datetime.utcnow().date().isoformat()))

    # News articles
    for n in News.query.filter_by(is_published=True).order_by(desc(News.created_at)).all():
        pages.append((url_for('public.news_detail', slug=n.slug, _external=True), n.created_at.date().isoformat()))

    # include a few important static pages
    pages.append((url_for('public.about', _external=True), datetime.utcnow().date().isoformat()))
    pages.append((url_for('public.contact', _external=True), datetime.utcnow().date().isoformat()))

    # Notices
    for no in Notice.query.filter_by(is_active=True).order_by(desc(Notice.published_date)).all():
        pages.append((url_for('public.index', _external=True) + '#notice-' + str(no.id), no.published_date.date().isoformat()))

    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in pages:
        xml_parts.append('<url>')
        xml_parts.append(f'<loc>{loc}</loc>')
        xml_parts.append(f'<lastmod>{lastmod}</lastmod>')
        xml_parts.append('</url>')
    xml_parts.append('</urlset>')
    body = '\n'.join(xml_parts)
    return Response(body, mimetype='application/xml')

ALL_DISTRICTS = [
    'Bhojpur', 'Dhankuta', 'Ilam', 'Jhapa', 'Khotang', 'Morang', 'Okhaldhunga',
    'Panchthar', 'Sankhuwasabha', 'Solukhumbu', 'Sunsari', 'Taplejung', 'Terhathum',
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


# ════════════════════════════════════════════
#   HOMEPAGE
# ════════════════════════════════════════════
@public_bp.route('/')
def index():
    # Active blood requests
    active_requests = BloodRequest.query.filter_by(status='active').order_by(
        BloodRequest.is_emergency.desc(),
        desc(BloodRequest.created_at)
    ).limit(6).all()
    
    # Stats
    total_donors    = Donor.query.count()
    avail_donors    = Donor.query.filter_by(availability_status='available').count()
    total_requests  = BloodRequest.query.count()
    fulfilled       = BloodRequest.query.filter_by(status='fulfilled').count()
    
    # Blood group stats
    bg_stats = get_blood_group_stats()
    
    # Latest news
    latest_news = News.query.filter_by(is_published=True).order_by(
        desc(News.created_at)
    ).limit(3).all()
    
    # Latest notices (homepage)
    latest_notices = Notice.query.filter(
        Notice.is_active == True,
        or_(Notice.expiry_date == None, Notice.expiry_date >= datetime.utcnow())
    ).order_by(Notice.priority.desc(), desc(Notice.published_date)).limit(5).all()
    
    # Success stories
    stories = News.query.filter_by(
        category='story', is_published=True
    ).order_by(desc(News.created_at)).limit(3).all()
    
    # Homepage banner ads
    banner_ads = Advertisement.query.filter(
        Advertisement.is_active == True,
        Advertisement.ad_type == 'banner',
        or_(Advertisement.end_date == None, Advertisement.end_date >= datetime.utcnow())
    ).all()
    
    # Track impressions
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
def blood_request_form():
    form = BloodRequestForm()
    
    if form.validate_on_submit():
        # Typosquatting / duplicate prevention: disallow similar requests for same patient within 10 minutes
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
            request_message = form.request_message.data.strip(),
            case_details    = form.case_details.data.strip(),
            blood_group     = form.blood_group.data,
            units_needed    = form.units_needed.data,
            hospital        = form.hospital.data.strip(),
            hospital_address= form.hospital_address.data.strip() if form.hospital_address.data else None,
            contact_person  = form.contact_person.data.strip(),
            contact_number  = form.contact_number.data.strip(),
            alt_number      = form.alt_number.data.strip() if form.alt_number.data else None,
            is_emergency    = form.is_emergency.data,
        )
        db.session.add(req)
        db.session.commit()
        
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
    
    # Count by status
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


@public_bp.route('/blood-requests/manage', methods=['GET', 'POST'])
def manage_blood_request():
    form = RequestManagementForm()
    request_record = None

    if form.validate_on_submit():
        request_record = BloodRequest.query.filter_by(
            request_id=form.request_id.data.strip(),
            contact_number=form.contact_number.data.strip()
        ).first()

        if not request_record:
            flash('No matching blood request found. Please verify Request ID and contact number.', 'danger')

    return render_template('blood_request_manage.html', form=form, request_record=request_record)


@public_bp.route('/blood-requests/<int:id>/update-status', methods=['POST'])
def public_update_request_status(id):
    request_record = BloodRequest.query.get_or_404(id)
    request_id = request.form.get('request_id', '').strip()
    contact_number = request.form.get('contact_number', '').strip()
    new_status = request.form.get('new_status', '').strip()

    if not request_id or not contact_number or request_record.request_id != request_id or request_record.contact_number != contact_number:
        flash('Authorization failed. Please confirm your request details.', 'danger')
        return redirect(url_for('public.manage_blood_request'))

    if new_status not in ('fulfilled', 'closed'):
        flash('Invalid status selected.', 'danger')
        return redirect(url_for('public.manage_blood_request'))

    if request_record.status == new_status:
        flash(f'Request is already marked {new_status}.', 'info')
        return redirect(url_for('public.manage_blood_request'))

    request_record.status = new_status
    db.session.commit()
    flash(f'Your request has been marked {new_status}.', 'success')
    return redirect(url_for('public.manage_blood_request'))


# ════════════════════════════════════════════
#   FIND DONORS
# ════════════════════════════════════════════
@public_bp.route('/find-donors')
def find_donors():
    page        = request.args.get('page', 1, type=int)
    blood_group = request.args.get('blood_group', '')
    district    = request.args.get('district', '')
    city        = request.args.get('city', '')
    donor_type  = request.args.get('donor_type', '')
    
    query = Donor.query
    
    if blood_group:
        query = query.filter_by(blood_group=blood_group)
    if district:
        query = query.filter(Donor.curr_district.ilike(f'%{district}%'))
    if city:
        query = query.filter(Donor.curr_city.ilike(f'%{city}%'))
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
    
    # Use a full district autocomplete list and keep user-entered district filtering
    districts = ALL_DISTRICTS
    
    return render_template('find_donors.html',
        pagination=pagination,
        blood_groups=blood_groups,
        districts=districts,
        selected_bg=blood_group,
        selected_district=district,
        selected_city=city,
        selected_type=donor_type,
        total_donors=total_donors,
        avail_donors=avail_donors,
    )


# ════════════════════════════════════════════
#   DONOR REGISTRATION
# ════════════════════════════════════════════
@public_bp.route('/become-donor', methods=['GET', 'POST'])
def become_donor():
    form = DonorRegistrationForm()
    
    if form.validate_on_submit():
        donor = Donor(
            full_name           = form.full_name.data.strip(),
            age                 = form.age.data,
            weight              = form.weight.data,
            perm_province       = form.perm_province.data or None,
            perm_district       = form.perm_district.data.strip() if form.perm_district.data else None,
            perm_city           = form.perm_city.data.strip() if form.perm_city.data else None,
            perm_local_level    = form.perm_local_level.data.strip() if form.perm_local_level.data else None,
            curr_province       = form.curr_province.data,
            curr_district       = form.curr_district.data.strip(),
            curr_city           = form.curr_city.data.strip(),
            curr_local_level    = form.curr_local_level.data.strip() if form.curr_local_level.data else None,
            phone1              = form.phone1.data.strip(),
            phone2              = form.phone2.data.strip() if form.phone2.data else None,
            blood_group         = form.blood_group.data,
            last_donation_date  = form.last_donation_date.data,
            donation_times      = form.donation_times.data or 0,
            donor_type          = form.donor_type.data,
            social_link         = form.social_link.data.strip() if form.social_link.data else None,
        )
        db.session.add(donor)
        db.session.commit()
        
        flash(f'🎉 Registration successful! Your Donor ID: {donor.donor_id}. Thank you for joining!', 'success')
        return redirect(url_for('public.donor_profile', donor_id=donor.donor_id))
    
    return render_template('become_donor.html', form=form, districts=ALL_DISTRICTS)


@public_bp.route('/donor/<string:donor_id>')
def donor_profile(donor_id):
    donor = Donor.query.filter_by(donor_id=donor_id).first_or_404()
    return render_template('donor_profile.html', donor=donor)


# Public profile editing is disabled to prevent unauthorized data modification.
# Admin users may update donors through the secure admin panel only.

# ════════════════════════════════════════════
#   NEWS
# ════════════════════════════════════════════
@public_bp.route('/news')
def news_list():
    page        = request.args.get('page', 1, type=int)
    category    = request.args.get('category', '')
    
    query = News.query.filter_by(is_published=True)
    if category:
        query = query.filter_by(category=category)
    
    pagination = paginate_query(
        query.order_by(desc(News.created_at)),
        page, current_app.config['NEWS_PER_PAGE']
    )
    
    categories = ['news', 'event', 'program', 'story']
    
    return render_template('news.html',
        pagination=pagination,
        categories=categories,
        selected_category=category,
    )


@public_bp.route('/news/<string:slug>')
def news_detail(slug):
    post = News.query.filter_by(slug=slug, is_published=True).first_or_404()
    post.views += 1
    db.session.commit()
    
    related = News.query.filter(
        News.category == post.category,
        News.id != post.id,
        News.is_published == True
    ).order_by(desc(News.created_at)).limit(3).all()
    
    return render_template('news_detail.html', post=post, related=related)


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
            name    = form.name.data.strip(),
            email   = form.email.data.strip(),
            phone   = form.phone.data.strip() if form.phone.data else None,
            subject = form.subject.data.strip(),
            message = form.message.data.strip(),
        )
        db.session.add(msg)
        db.session.commit()
        
        flash('✅ Your message has been sent! We will respond within 24 hours.', 'success')
        return redirect(url_for('public.contact'))
    
    return render_template('contact.html', form=form)


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