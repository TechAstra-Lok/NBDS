from urllib.parse import urljoin, urlparse

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, current_app, session
)
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import (
    User, Donor, BloodRequest, News, Notice,
    Advertisement, Contact, SiteVisitor
)
from app.forms import (
    AdminLoginForm, DonorRegistrationForm, DonorEditForm,
    NewsForm, NoticeForm, AdvertisementForm, AdminUserForm
)
from app.utils import save_image, save_file, delete_file, paginate_query, sanitize_html
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from functools import wraps

admin_bp = Blueprint('admin', __name__)


# Enforce short admin session (5 minutes) based on last activity
@admin_bp.before_request
def enforce_admin_session_timeout():
    # Only apply to logged-in users accessing admin blueprint
    from datetime import datetime
    if not current_user.is_authenticated:
        return

    last = session.get('admin_last_active')
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
        except Exception:
            last_dt = None
        if last_dt:
            if datetime.utcnow() - last_dt > timedelta(minutes=5):
                # expire session
                logout_user()
                session.pop('admin_last_active', None)
                flash('Your admin session has expired due to inactivity. Please log in again.', 'warning')
                return redirect(url_for('admin.login'))

    # update last active timestamp for admins
    session['admin_last_active'] = datetime.utcnow().isoformat()


# ─── Auth Decorators ──────────────────────────
def superadmin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_superadmin:
            flash('Super Admin access required.', 'danger')
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated


# ════════════════════════════════════════════
#   LOGIN / LOGOUT
# ════════════════════════════════════════════
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    
    form = AdminLoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            # make admin session permanent for session lifetime tracking
            session.permanent = True
            session['admin_last_active'] = datetime.utcnow().isoformat()
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            next_page = request.args.get('next')
            if next_page and not is_safe_url(next_page):
                next_page = None
            flash(f'✅ Welcome back, {user.full_name or user.username}!', 'success')
            return redirect(next_page or url_for('admin.dashboard'))
        
        flash('❌ Invalid credentials. Please try again.', 'danger')
    
    return render_template('admin/login.html', form=form)


def is_safe_url(target):
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


@admin_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('public.index'))


# ════════════════════════════════════════════
#   DASHBOARD
# ════════════════════════════════════════════
@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    # Core stats
    total_donors    = Donor.query.count()
    avail_donors    = Donor.query.filter_by(availability_status='available').count()
    total_requests  = BloodRequest.query.count()
    active_requests = BloodRequest.query.filter_by(status='active').count()
    fulfilled       = BloodRequest.query.filter_by(status='fulfilled').count()
    total_news      = News.query.filter_by(is_published=True).count()
    total_notices   = Notice.query.filter_by(is_active=True).count()
    unread_contacts = Contact.query.filter_by(is_read=False).count()
    
    # Visitor stats
    today       = datetime.utcnow().date()
    today_visitors = SiteVisitor.query.filter_by(visit_date=today).count()
    week_ago    = today - timedelta(days=7)
    week_visitors = SiteVisitor.query.filter(SiteVisitor.visit_date >= week_ago).count()
    total_visitors = SiteVisitor.query.count()
    
    # Blood group breakdown
    bg_breakdown = db.session.query(
        Donor.blood_group,
        func.count(Donor.id).label('count')
    ).group_by(Donor.blood_group).order_by(desc('count')).all()
    
    # Recent activity
    recent_donors   = Donor.query.order_by(desc(Donor.created_at)).limit(5).all()
    recent_requests = BloodRequest.query.order_by(desc(BloodRequest.created_at)).limit(5).all()
    
    # Monthly registration trend (last 6 months)
    monthly_data = []
    for i in range(5, -1, -1):
        month_start = (datetime.utcnow().replace(day=1) - timedelta(days=i*30)).replace(day=1)
        month_end   = (month_start + timedelta(days=32)).replace(day=1)
        count = Donor.query.filter(
            Donor.created_at >= month_start,
            Donor.created_at < month_end
        ).count()
        monthly_data.append({
            'month': month_start.strftime('%b %Y'),
            'count': count
        })

    # District coverage and emergency support count
    districts_covered = db.session.query(func.count(func.distinct(Donor.curr_district))).scalar() or 0
    active_emergencies = BloodRequest.query.filter_by(status='active', is_emergency=True).count()
    
    return render_template('admin/dashboard.html',
        total_donors=total_donors,
        avail_donors=avail_donors,
        total_requests=total_requests,
        active_requests=active_requests,
        fulfilled=fulfilled,
        total_news=total_news,
        total_notices=total_notices,
        unread_contacts=unread_contacts,
        today_visitors=today_visitors,
        week_visitors=week_visitors,
        total_visitors=total_visitors,
        bg_breakdown=bg_breakdown,
        recent_donors=recent_donors,
        recent_requests=recent_requests,
        monthly_data=monthly_data,
        districts_covered=districts_covered,
        active_emergencies=active_emergencies,
    )


# ════════════════════════════════════════════
#   DONOR MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/donors')
@login_required
def donors():
    page        = request.args.get('page', 1, type=int)
    search      = request.args.get('q', '')
    blood_group = request.args.get('bg', '')
    status      = request.args.get('status', '')
    donor_type  = request.args.get('type', '')
    
    query = Donor.query
    
    if search:
        query = query.filter(or_(
            Donor.full_name.ilike(f'%{search}%'),
            Donor.donor_id.ilike(f'%{search}%'),
            Donor.phone1.ilike(f'%{search}%'),
            Donor.curr_district.ilike(f'%{search}%'),
        ))
    if blood_group:
        query = query.filter_by(blood_group=blood_group)
    if status:
        query = query.filter_by(availability_status=status)
    if donor_type:
        query = query.filter_by(donor_type=donor_type)
    
    pagination = paginate_query(
        query.order_by(desc(Donor.created_at)), page, 20
    )
    
    total = Donor.query.count()
    blood_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    
    return render_template('admin/donors.html',
        pagination=pagination,
        total=total,
        blood_groups=blood_groups,
        search=search,
        selected_bg=blood_group,
        selected_status=status,
        selected_type=donor_type,
    )


@admin_bp.route('/donors/add', methods=['GET', 'POST'])
@login_required
def add_donor():
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
        
        flash(f'✅ Donor added! ID: {donor.donor_id}', 'success')
        return redirect(url_for('admin.donors'))
    
    return render_template('admin/donor_form.html', form=form, action='Add')


@admin_bp.route('/donors/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_donor(id):
    donor = Donor.query.get_or_404(id)
    form  = DonorEditForm(obj=donor)
    form.donor_id.data = donor.id
    
    if form.validate_on_submit():
        form.populate_obj(donor)
        donor.updated_at = datetime.utcnow()
        db.session.commit()
        flash('✅ Donor updated successfully!', 'success')
        return redirect(url_for('admin.donors'))
    
    return render_template('admin/donor_form.html', form=form, donor=donor, action='Edit')


@admin_bp.route('/donors/<int:id>/delete', methods=['POST'])
@login_required
def delete_donor(id):
    donor = Donor.query.get_or_404(id)
    db.session.delete(donor)
    db.session.commit()
    flash(f'Donor {donor.donor_id} deleted.', 'warning')
    return redirect(url_for('admin.donors'))


@admin_bp.route('/donors/<int:id>/toggle-status', methods=['POST'])
@login_required
def toggle_donor_status(id):
    donor = Donor.query.get_or_404(id)
    donor.availability_status = 'unavailable' if donor.availability_status == 'available' else 'available'
    db.session.commit()
    return jsonify({'status': donor.availability_status})


# ════════════════════════════════════════════
#   BLOOD REQUEST MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/requests')
@login_required
def blood_requests():
    page        = request.args.get('page', 1, type=int)
    status      = request.args.get('status', '')
    blood_group = request.args.get('bg', '')
    
    query = BloodRequest.query
    
    if status:
        query = query.filter_by(status=status)
    if blood_group:
        query = query.filter_by(blood_group=blood_group)
    
    pagination = paginate_query(
        query.order_by(
            BloodRequest.is_emergency.desc(),
            desc(BloodRequest.created_at)
        ), page, 20
    )
    
    counts = {
        'all': BloodRequest.query.count(),
        'active': BloodRequest.query.filter_by(status='active').count(),
        'fulfilled': BloodRequest.query.filter_by(status='fulfilled').count(),
        'closed': BloodRequest.query.filter_by(status='closed').count(),
    }
    
    return render_template('admin/requests.html',
        pagination=pagination,
        counts=counts,
        selected_status=status,
        selected_bg=blood_group,
        blood_groups=['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
    )


@admin_bp.route('/requests/<int:id>/status/<string:new_status>', methods=['POST'])
@login_required
def update_request_status(id, new_status):
    req = BloodRequest.query.get_or_404(id)
    if new_status in ('active', 'fulfilled', 'closed'):
        req.status = new_status
        db.session.commit()
        flash(f'Request {req.request_id} marked as {new_status}.', 'success')
    return redirect(url_for('admin.blood_requests'))


@admin_bp.route('/requests/<int:id>/delete', methods=['POST'])
@login_required
def delete_request(id):
    req = BloodRequest.query.get_or_404(id)
    db.session.delete(req)
    db.session.commit()
    flash(f'Request {req.request_id} deleted.', 'warning')
    return redirect(url_for('admin.blood_requests'))


# ════════════════════════════════════════════
#   NEWS MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/news')
@login_required
def news():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        News.query.order_by(desc(News.created_at)), page, 15
    )
    return render_template('admin/news.html', pagination=pagination)


@admin_bp.route('/news/add', methods=['GET', 'POST'])
@login_required
def add_news():
    form = NewsForm()
    
    if form.validate_on_submit():
        image_file = None
        if form.featured_image.data and form.featured_image.data.filename:
            image_file = save_image(form.featured_image.data, 'news')
        
        post = News(
            title       = form.title.data.strip(),
            short_desc  = form.short_desc.data.strip(),
            content     = sanitize_html(form.content.data),
            category    = form.category.data,
            author      = form.author.data.strip(),
            tags        = form.tags.data.strip() if form.tags.data else None,
            featured_image = image_file,
            is_published = form.is_published.data,
        )
        db.session.add(post)
        db.session.commit()
        
        flash('✅ News post created!', 'success')
        return redirect(url_for('admin.news'))
    
    return render_template('admin/news_form.html', form=form, action='Add')


@admin_bp.route('/news/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_news(id):
    post = News.query.get_or_404(id)
    form = NewsForm(obj=post)
    
    if form.validate_on_submit():
        if form.featured_image.data and form.featured_image.data.filename:
            delete_file(post.featured_image, 'news')
            post.featured_image = save_image(form.featured_image.data, 'news')
        
        post.title      = form.title.data.strip()
        post.short_desc = form.short_desc.data.strip()
        post.content    = sanitize_html(form.content.data)
        post.category   = form.category.data
        post.author     = form.author.data.strip()
        post.tags       = form.tags.data.strip() if form.tags.data else None
        post.is_published = form.is_published.data
        post.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('✅ News post updated!', 'success')
        return redirect(url_for('admin.news'))
    
    return render_template('admin/news_form.html', form=form, post=post, action='Edit')


@admin_bp.route('/news/<int:id>/delete', methods=['POST'])
@login_required
def delete_news(id):
    post = News.query.get_or_404(id)
    delete_file(post.featured_image, 'news')
    db.session.delete(post)
    db.session.commit()
    flash('News post deleted.', 'warning')
    return redirect(url_for('admin.news'))


# ════════════════════════════════════════════
#   NOTICE MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/notices')
@login_required
def notices():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        Notice.query.order_by(Notice.priority.desc(), desc(Notice.published_date)), page, 15
    )
    return render_template('admin/notices.html', pagination=pagination)


@admin_bp.route('/notices/add', methods=['GET', 'POST'])
@login_required
def add_notice():
    form = NoticeForm()
    
    if form.validate_on_submit():
        file_name, file_ext = None, None
        if form.attachment.data and form.attachment.data.filename:
            file_name, file_ext = save_file(form.attachment.data, 'notices')
        
        notice = Notice(
            title           = form.title.data.strip(),
            content         = form.content.data.strip(),
            expiry_date     = datetime.combine(form.expiry_date.data, datetime.min.time()) if form.expiry_date.data else None,
            priority        = int(form.priority.data),
            attachment      = file_name,
            attachment_type = file_ext,
            is_active       = form.is_active.data,
        )
        db.session.add(notice)
        db.session.commit()
        
        flash('✅ Notice published!', 'success')
        return redirect(url_for('admin.notices'))
    
    return render_template('admin/notice_form.html', form=form, action='Add')


@admin_bp.route('/notices/<int:id>/delete', methods=['POST'])
@login_required
def delete_notice(id):
    notice = Notice.query.get_or_404(id)
    delete_file(notice.attachment, 'notices')
    db.session.delete(notice)
    db.session.commit()
    flash('Notice deleted.', 'warning')
    return redirect(url_for('admin.notices'))


@admin_bp.route('/notices/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_notice(id):
    notice = Notice.query.get_or_404(id)
    notice.is_active = not notice.is_active
    db.session.commit()
    return jsonify({'is_active': notice.is_active})


# ════════════════════════════════════════════
#   ADVERTISEMENT MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/advertisements')
@login_required
def advertisements():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        Advertisement.query.order_by(desc(Advertisement.created_at)), page, 15
    )
    
    # Monthly click report
    monthly_clicks = db.session.query(
        func.strftime('%Y-%m', Advertisement.created_at).label('month'),
        func.sum(Advertisement.clicks).label('total_clicks'),
        func.sum(Advertisement.impressions).label('total_impressions'),
    ).group_by('month').order_by(desc('month')).limit(6).all()
    
    return render_template('admin/advertisements.html',
        pagination=pagination,
        monthly_clicks=monthly_clicks,
    )


@admin_bp.route('/advertisements/add', methods=['GET', 'POST'])
@login_required
def add_advertisement():
    form = AdvertisementForm()
    
    if form.validate_on_submit():
        if not form.image.data or not form.image.data.filename:
            flash('Banner image is required.', 'danger')
            return render_template('admin/ad_form.html', form=form, action='Add')
        
        image_file = save_image(form.image.data, 'ads', max_width=800, max_height=600)
        
        ad = Advertisement(
            title       = form.title.data.strip(),
            description = form.description.data.strip() if form.description.data else None,
            image       = image_file,
            redirect_url= form.redirect_url.data.strip() if form.redirect_url.data else None,
            ad_type     = form.ad_type.data,
            start_date  = datetime.combine(form.start_date.data, datetime.min.time()),
            end_date    = datetime.combine(form.end_date.data, datetime.max.time()),
            is_active   = form.is_active.data,
        )
        db.session.add(ad)
        db.session.commit()
        
        flash('✅ Advertisement created!', 'success')
        return redirect(url_for('admin.advertisements'))
    
    return render_template('admin/ad_form.html', form=form, action='Add')


@admin_bp.route('/advertisements/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_ad(id):
    ad = Advertisement.query.get_or_404(id)
    ad.is_active = not ad.is_active
    db.session.commit()
    flash(f"Advertisement {'activated' if ad.is_active else 'deactivated'}.", 'success')
    return redirect(url_for('admin.advertisements'))


@admin_bp.route('/advertisements/<int:id>/delete', methods=['POST'])
@login_required
def delete_advertisement(id):
    ad = Advertisement.query.get_or_404(id)
    delete_file(ad.image, 'ads')
    db.session.delete(ad)
    db.session.commit()
    flash('Advertisement deleted.', 'warning')
    return redirect(url_for('admin.advertisements'))


# ════════════════════════════════════════════
#   CONTACTS
# ════════════════════════════════════════════
@admin_bp.route('/contacts')
@login_required
def contacts():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        Contact.query.order_by(Contact.is_read.asc(), desc(Contact.created_at)), page, 20
    )
    return render_template('admin/contacts.html', pagination=pagination)


@admin_bp.route('/contacts/<int:id>/read', methods=['POST'])
@login_required
def mark_contact_read(id):
    msg = Contact.query.get_or_404(id)
    msg.is_read = True
    db.session.commit()
    return jsonify({'ok': True})


# ════════════════════════════════════════════
#   USER MANAGEMENT (SuperAdmin only)
# ════════════════════════════════════════════
@admin_bp.route('/users')
@superadmin_required
def users():
    all_users = User.query.order_by(desc(User.created_at)).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/add', methods=['GET', 'POST'])
@superadmin_required
def add_user():
    form = AdminUserForm()
    
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists.', 'danger')
        elif User.query.filter_by(email=form.email.data).first():
            flash('Email already exists.', 'danger')
        else:
            user = User(
                username  = form.username.data.strip(),
                email     = form.email.data.strip(),
                full_name = form.full_name.data.strip(),
                role      = form.role.data,
                is_active = form.is_active.data,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('✅ Admin user created!', 'success')
            return redirect(url_for('admin.users'))
    
    return render_template('admin/user_form.html', form=form, action='Add')