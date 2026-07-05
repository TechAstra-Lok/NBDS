from urllib.parse import urljoin, urlparse
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, session
)
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import (
    User, Donor, BloodRequest, News, Notice,
    Advertisement, Contact, SiteVisitor, SuccessStory, StaffMember, Partner, BloodBank, BloodInventory, BloodInventoryMovement, BloodReservation, BloodTransfer, LowStockAlert, Notification, AuditLog
)
from app.utils import generate_qr_code
from app.forms import (
    AdminLoginForm, DonorRegistrationForm, DonorEditForm,
    NewsForm, NoticeForm, AdvertisementForm, AdminUserForm,
    StaffMemberForm, PartnerForm
)
from app.utils import save_image, save_file, delete_file, paginate_query, sanitize_html
from sqlalchemy import desc, func, or_  # यहाँ or_ इम्पोर्ट फिक्स गरिएको छ
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash

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


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            # Check if user has User model instance or custom role attribute
            role = getattr(current_user, 'role', None)
            if role == 'superadmin' or role in roles:
                return f(*args, **kwargs)
            flash('🚫 Access Denied: You do not have the required permissions.', 'danger')
            return redirect(url_for('admin.dashboard'))
        return decorated
    return decorator


def build_blood_bank_dashboard_summary(bank_id):
    bank = BloodBank.query.get_or_404(bank_id)
    inventory_items = BloodInventory.query.filter_by(blood_bank_id=bank.id).all()
    low_stock_items = [item for item in inventory_items if item.available_units < item.minimum_stock]
    pending_transfers = BloodTransfer.query.filter_by(destination_bank_id=bank.id, status='pending').count()
    alerts = LowStockAlert.query.filter_by(blood_bank_id=bank.id).count()
    critical_items = sum(1 for item in inventory_items if item.available_units <= max(1, item.minimum_stock // 2))
    return {
        'bank_id': bank.id,
        'bank_name': bank.display_name,
        'inventory_count': len(inventory_items),
        'low_stock_count': len(low_stock_items),
        'pending_transfers': pending_transfers,
        'alert_count': alerts,
        'critical_items': critical_items,
    }


def create_inventory_notifications(inventory):
    notifications = []
    if inventory.available_units < inventory.minimum_stock:
        notification = Notification(
            title='Low stock alert',
            message=f"{inventory.blood_group} {inventory.component} is below minimum stock.",
            category='low_stock',
            channel='in_app',
        )
        db.session.add(notification)
        notifications.append(notification)

    if inventory.expiry_date:
        from datetime import datetime
        try:
            expiry = datetime.strptime(inventory.expiry_date, '%Y-%m-%d').date()
        except ValueError:
            expiry = None
        if expiry and (expiry - datetime.utcnow().date()).days <= 14:
            notification = Notification(
                title='Expiry soon',
                message=f"{inventory.blood_group} {inventory.component} expires soon.",
                category='expiry',
                channel='in_app',
            )
            db.session.add(notification)
            notifications.append(notification)
    return notifications


def log_audit_event(action, entity_id, details, actor='system'):
    audit_entry = AuditLog(action=action, entity_id=entity_id, details=details, actor=actor)
    db.session.add(audit_entry)
    return audit_entry


def build_blood_inventory_report(bank_id):
    bank = BloodBank.query.get_or_404(bank_id)
    inventory_items = BloodInventory.query.filter_by(blood_bank_id=bank.id).all()
    low_stock_count = sum(1 for item in inventory_items if item.available_units < item.minimum_stock)
    expiring_soon_count = 0
    for item in inventory_items:
        if item.expiry_date:
            from datetime import datetime
            try:
                expiry = datetime.strptime(item.expiry_date, '%Y-%m-%d').date()
            except ValueError:
                expiry = None
            if expiry and (expiry - datetime.utcnow().date()).days <= 14:
                expiring_soon_count += 1
    return {
        'bank_id': bank.id,
        'bank_name': bank.display_name,
        'inventory_count': len(inventory_items),
        'low_stock_count': low_stock_count,
        'expiring_soon_count': expiring_soon_count,
        'pending_transfers': BloodTransfer.query.filter_by(destination_bank_id=bank.id, status='pending').count(),
    }


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
    total_stories   = SuccessStory.query.count()  # ड्यासबोर्डमा सफलताका कथाहरूको गणना थपियो
    
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
        total_stories=total_stories,  # टेम्प्लेटमा डेटा पास गरियो
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
#   BLOOD BANK MANAGEMENT
# ════════════════════════════════════════════



@admin_bp.route('/blood-banks/<int:bank_id>/inventory', methods=['GET', 'POST'])
@role_required('admin', 'moderator')
def blood_bank_inventory(bank_id):
    bank = BloodBank.query.get_or_404(bank_id)
    if request.method == 'POST':
        inventory = BloodInventory(
            blood_bank_id=bank.id,
            blood_group=request.form.get('blood_group', '').strip(),
            component=request.form.get('component', 'Whole Blood').strip() or 'Whole Blood',
            units_available=int(request.form.get('units_available', 0) or 0),
            units_reserved=int(request.form.get('units_reserved', 0) or 0),
            minimum_stock=int(request.form.get('minimum_stock', 4) or 4),
            maximum_stock=int(request.form.get('maximum_stock', 20) or 20),
            expiry_date=request.form.get('expiry_date', '').strip() or None,
        )
        db.session.add(inventory)
        db.session.flush()
        inventory.qr_code = generate_qr_code('inventory', inventory.id)
        db.session.commit()
        if inventory.units_available < inventory.minimum_stock:
            db.session.add(LowStockAlert(
                blood_bank_id=bank.id,
                blood_group=inventory.blood_group,
                component=inventory.component,
                severity='warning',
                message=f"{inventory.blood_group} {inventory.component} stock is below minimum level.",
            ))
        create_inventory_notifications(inventory)
        log_audit_event('inventory_created', inventory.id, f"Inventory created for {inventory.blood_group}/{inventory.component}", actor='admin')
        db.session.commit()
        if request.form.get('movement_type') and request.form.get('movement_units'):
            movement = BloodInventoryMovement(
                inventory_id=inventory.id,
                movement_type=request.form.get('movement_type', 'received').strip(),
                units=int(request.form.get('movement_units', 0) or 0),
                note=request.form.get('movement_note', '').strip() or None,
            )
            db.session.add(movement)
            db.session.commit()
        flash('Inventory entry added.', 'success')
        return redirect(url_for('admin.blood_bank_inventory', bank_id=bank.id))

    inventory_items = BloodInventory.query.filter_by(blood_bank_id=bank.id).order_by(BloodInventory.blood_group).all()
    inventory_map = {item.id: item.movements for item in inventory_items}
    reservations = BloodReservation.query.filter_by(blood_bank_id=bank.id).order_by(BloodReservation.requested_at.desc()).all()
    transfers = BloodTransfer.query.filter((BloodTransfer.source_bank_id == bank.id) | (BloodTransfer.destination_bank_id == bank.id)).order_by(BloodTransfer.created_at.desc()).all()
    alerts = LowStockAlert.query.filter_by(blood_bank_id=bank.id).order_by(LowStockAlert.created_at.desc()).all()
    blood_banks = BloodBank.query.filter(BloodBank.id != bank.id).order_by(BloodBank.name).all()

    summary = build_blood_bank_dashboard_summary(bank.id)
    report = build_blood_inventory_report(bank.id)
    return render_template('admin/blood_bank_inventory.html', bank=bank, inventory_items=inventory_items, reservations=reservations, transfers=transfers, alerts=alerts, blood_banks=blood_banks, inventory_map=inventory_map, dashboard_summary=summary, report_summary=report)


@admin_bp.route('/blood-banks/<int:bank_id>/transfers', methods=['POST'])
@role_required('admin', 'moderator')
def blood_bank_transfers(bank_id):
    bank = BloodBank.query.get_or_404(bank_id)
    transfer = BloodTransfer(
        source_bank_id=bank.id,
        destination_bank_id=int(request.form.get('destination_bank_id') or 0),
        blood_group=request.form.get('blood_group', '').strip(),
        component=request.form.get('component', 'Whole Blood').strip() or 'Whole Blood',
        units=int(request.form.get('units', 0) or 0),
        status='pending',
        remarks=request.form.get('remarks', '').strip() or None,
    )
    db.session.add(transfer)
    db.session.commit()
    flash('Transfer request recorded.', 'success')
    return redirect(url_for('admin.blood_bank_inventory', bank_id=bank.id))


# ════════════════════════════════════════════
#   DONOR MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/donors')
@role_required('admin', 'moderator')
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
@role_required('admin', 'moderator')
def add_donor():
    form = DonorRegistrationForm()
    
    if form.validate_on_submit():
        donor = Donor(
            full_name           = form.full_name.data.strip(),
            email               = form.email.data.strip() if hasattr(form, 'email') and form.email.data else f"{form.phone1.data}@nbd.local",
            pin_hash            = generate_password_hash(form.pin.data) if hasattr(form, 'pin') and form.pin.data else generate_password_hash('0000'),
            age                 = form.age.data,
            weight              = form.weight.data,
            perm_province       = form.perm_province.data or None,
            perm_district       = form.perm_district.data.strip() if form.perm_district.data else None,
            perm_local_level    = form.perm_local_level.data.strip() if form.perm_local_level.data else None,
            curr_province       = form.curr_province.data,
            curr_district       = form.curr_district.data.strip(),
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
@role_required('admin', 'moderator')
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
@role_required('admin', 'moderator')
def delete_donor(id):
    donor = Donor.query.get_or_404(id)
    db.session.delete(donor)
    db.session.commit()
    flash(f'Donor {donor.donor_id} deleted.', 'warning')
    return redirect(url_for('admin.donors'))


@admin_bp.route('/donors/<int:id>/toggle-status', methods=['POST'])
@role_required('admin', 'moderator')
def toggle_donor_status(id):
    donor = Donor.query.get_or_404(id)
    donor.availability_status = 'unavailable' if donor.availability_status == 'available' else 'available'
    db.session.commit()
    return jsonify({'status': donor.availability_status})

@admin_bp.route('/donors/<int:donor_id>/history/<int:history_id>/delete', methods=['POST'])
@role_required('admin', 'moderator')
def delete_donor_history(donor_id, history_id):
    from app.models import DonorDonationHistory
    donor = Donor.query.get_or_404(donor_id)
    history = DonorDonationHistory.query.filter_by(id=history_id, donor_id=donor.id).first_or_404()
    db.session.delete(history)
    
    # Recalculate donor summary
    donor.donation_times = max(0, (donor.donation_times or 0) - 1)
    donor.total_donations = max(0, (donor.total_donations or 0) - 1)
    
    # Update last donation date
    last_donation = DonorDonationHistory.query.filter_by(donor_id=donor.id).filter(DonorDonationHistory.id != history_id).order_by(DonorDonationHistory.donation_date.desc()).first()
    donor.last_donation_date = last_donation.donation_date if last_donation else None
    
    donor.recalculate_and_save()
    db.session.commit()
    flash('Donation history record deleted.', 'success')
    return redirect(url_for('public.donor_profile', donor_id=donor.donor_id))


# ════════════════════════════════════════════
#   BLOOD BANKS MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/blood-banks')
@role_required('admin', 'moderator')
def blood_banks():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '')
    
    query = BloodBank.query
    if search:
        query = query.filter(BloodBank.name.ilike(f'%{search}%') | BloodBank.district.ilike(f'%{search}%'))
        
    pagination = query.order_by(BloodBank.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/blood_banks.html', pagination=pagination, search=search)

@admin_bp.route('/blood-banks/create', methods=['GET', 'POST'])
@role_required('admin')
def create_blood_bank():
    from app.forms import BloodBankForm
    form = BloodBankForm()
    
    if form.validate_on_submit():
        bank = BloodBank(
            name=form.name.data,
            display_name=form.display_name.data,
            hospital_name=form.hospital_name.data,
            branch_type=form.branch_type.data,
            service_type=form.service_type.data,
            province=form.province.data,
            district=form.district.data,
            city=form.city.data,
            contact_number=form.contact_number.data,
            alternate_contact_number=form.alternate_contact_number.data,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
            is_emergency_panel=form.is_emergency_panel.data,
            is_grouped_entry=form.is_grouped_entry.data,
            is_active=form.is_active.data,
            notes=form.notes.data,
            status='active' if form.is_active.data else 'inactive'
        )
        
        if bank.latitude and bank.longitude:
            bank.maps_url = f"https://www.google.com/maps/search/?api=1&query={bank.latitude},{bank.longitude}"
            
        db.session.add(bank)
        db.session.commit()
        flash('Blood Bank created successfully!', 'success')
        return redirect(url_for('admin.blood_banks'))
        
    return render_template('admin/blood_bank_form.html', form=form, action='Create')

@admin_bp.route('/blood-banks/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin', 'moderator')
def edit_blood_bank(id):
    from app.forms import BloodBankForm
    bank = BloodBank.query.get_or_404(id)
    form = BloodBankForm(obj=bank)
    
    if form.validate_on_submit():
        form.populate_obj(bank)
        bank.status = 'active' if form.is_active.data else 'inactive'
        if bank.latitude and bank.longitude:
            bank.maps_url = f"https://www.google.com/maps/search/?api=1&query={bank.latitude},{bank.longitude}"
            
        db.session.commit()
        flash('Blood Bank updated successfully!', 'success')
        return redirect(url_for('admin.blood_banks'))
        
    return render_template('admin/blood_bank_form.html', form=form, action='Edit', bank=bank)

@admin_bp.route('/blood-banks/<int:id>/delete', methods=['POST'])
@role_required('admin')
def delete_blood_bank(id):
    bank = BloodBank.query.get_or_404(id)
    db.session.delete(bank)
    db.session.commit()
    flash('Blood Bank deleted successfully.', 'warning')
    return redirect(url_for('admin.blood_banks'))

# ════════════════════════════════════════════
#   BLOOD REQUEST MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/requests')
@role_required('admin', 'moderator')
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
@role_required('admin', 'moderator')
def update_request_status(id, new_status):
    req = BloodRequest.query.get_or_404(id)
    if new_status in ('active', 'fulfilled', 'closed'):
        req.status = new_status
        db.session.commit()
        flash(f'Request {req.request_id} marked as {new_status}.', 'success')
    return redirect(url_for('admin.blood_requests'))


@admin_bp.route('/requests/<int:id>/delete', methods=['POST'])
@role_required('admin', 'moderator')
def delete_request(id):
    req = BloodRequest.query.get_or_404(id)
    db.session.delete(req)
    db.session.commit()
    flash(f'Request {req.request_id} deleted.', 'warning')
    return redirect(url_for('admin.blood_requests'))


# ------------------------------------------------------------------------------
# NOTIFICATION DELIVERY LOGS
# ------------------------------------------------------------------------------
@admin_bp.route('/delivery_logs')
@login_required
@role_required('admin', 'superadmin')
def delivery_logs():
    page = request.args.get('page', 1, type=int)
    from app.models import NotificationDeliveryLog
    logs = NotificationDeliveryLog.query.order_by(NotificationDeliveryLog.created_at.desc()).paginate(page=page, per_page=50)
    return render_template('admin/delivery_logs.html', logs=logs)


# ════════════════════════════════════════════
#   NEWS MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/news')
@role_required('admin', 'content_manager')
def news():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        News.query.order_by(desc(News.created_at)), page, 15
    )
    return render_template('admin/news.html', pagination=pagination)


@admin_bp.route('/news/add', methods=['GET', 'POST'])
@role_required('admin', 'content_manager')
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
@role_required('admin', 'content_manager')
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
@role_required('admin', 'content_manager')
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
@role_required('admin', 'content_manager')
def notices():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        Notice.query.order_by(Notice.priority.desc(), desc(Notice.published_date)), page, 15
    )
    return render_template('admin/notices.html', pagination=pagination)


@admin_bp.route('/notices/add', methods=['GET', 'POST'])
@role_required('admin', 'content_manager')
def add_notice():
    form = NoticeForm()
    
    if form.validate_on_submit():
        file_name, file_ext = None, None
        if form.attachment.data and form.attachment.data.filename:
            file_name, file_ext = save_file(form.attachment.data, 'notices')
        
        notice = Notice(
            # pyrefly: ignore [unexpected-keyword]
            title           = form.title.data.strip(),
            # pyrefly: ignore [unexpected-keyword]
            content         = form.content.data.strip(),
            # pyrefly: ignore [unexpected-keyword]
            expiry_date     = datetime.combine(form.expiry_date.data, datetime.min.time()) if form.expiry_date.data else None,
            # pyrefly: ignore [unexpected-keyword]
            priority        = int(form.priority.data),
            # pyrefly: ignore [unexpected-keyword]
            attachment      = file_name,
            # pyrefly: ignore [unexpected-keyword]
            attachment_type = file_ext,
            # pyrefly: ignore [unexpected-keyword]
            is_active       = form.is_active.data,
        )
        db.session.add(notice)
        db.session.commit()
        
        flash('✅ Notice published!', 'success')
        return redirect(url_for('admin.notices'))
    
    return render_template('admin/notice_form.html', form=form, action='Add')


@admin_bp.route('/notices/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin', 'content_manager')
def edit_notice(id):
    notice = Notice.query.get_or_404(id)
    form = NoticeForm(obj=notice)
    
    if form.validate_on_submit():
        if form.attachment.data and form.attachment.data.filename:
            if notice.attachment:
                delete_file(notice.attachment, 'notices')
            file_name, file_ext = save_file(form.attachment.data, 'notices')
            notice.attachment = file_name
            notice.attachment_type = file_ext
            
        notice.title = form.title.data.strip()
        notice.content = form.content.data.strip()
        notice.expiry_date = datetime.combine(form.expiry_date.data, datetime.min.time()) if form.expiry_date.data else None
        notice.priority = int(form.priority.data)
        notice.is_active = form.is_active.data
        notice.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('✅ Notice updated successfully!', 'success')
        return redirect(url_for('admin.notices'))
        
    return render_template('admin/notice_form.html', form=form, notice=notice, action='Edit')


@admin_bp.route('/notices/<int:id>/delete', methods=['POST'])
@role_required('admin', 'content_manager')
def delete_notice(id):
    notice = Notice.query.get_or_404(id)
    delete_file(notice.attachment, 'notices')
    db.session.delete(notice)
    db.session.commit()
    flash('Notice deleted.', 'warning')
    return redirect(url_for('admin.notices'))


@admin_bp.route('/notices/<int:id>/toggle', methods=['POST'])
@role_required('admin', 'content_manager')
def toggle_notice(id):
    notice = Notice.query.get_or_404(id)
    notice.is_active = not notice.is_active
    db.session.commit()
    return jsonify({'is_active': notice.is_active})


# ════════════════════════════════════════════
#   ADVERTISEMENT MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/advertisements')
@role_required('admin', 'content_manager')
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
@role_required('admin', 'content_manager')
def add_advertisement():
    form = AdvertisementForm()
    
    if form.validate_on_submit():
        if not form.image.data or not form.image.data.filename:
            flash('Banner image is required.', 'danger')
            return render_template('admin/ad_form.html', form=form, action='Add')
        
        image_file = save_image(form.image.data, 'ads', max_width=800, max_height=600)
        
        ad = Advertisement(
            # pyrefly: ignore [unexpected-keyword]
            title       = form.title.data.strip(),
            # pyrefly: ignore [unexpected-keyword]
            description = form.description.data.strip() if form.description.data else None,
            # pyrefly: ignore [unexpected-keyword]
            image       = image_file,
            # pyrefly: ignore [unexpected-keyword]
            redirect_url= form.redirect_url.data.strip() if form.redirect_url.data else None,
            # pyrefly: ignore [unexpected-keyword]
            ad_type     = form.ad_type.data,
            # pyrefly: ignore [unexpected-keyword]
            start_date  = datetime.combine(form.start_date.data, datetime.min.time()),
            # pyrefly: ignore [unexpected-keyword]
            end_date    = datetime.combine(form.end_date.data, datetime.max.time()),
            # pyrefly: ignore [unexpected-keyword]
            is_active   = form.is_active.data,
        )
        db.session.add(ad)
        db.session.commit()
        
        flash('✅ Advertisement created!', 'success')
        return redirect(url_for('admin.advertisements'))
    
    return render_template('admin/ad_form.html', form=form, action='Add')


@admin_bp.route('/advertisements/<int:id>/toggle', methods=['POST'])
@role_required('admin', 'content_manager')
def toggle_ad(id):
    ad = Advertisement.query.get_or_404(id)
    ad.is_active = not ad.is_active
    db.session.commit()
    flash(f"Advertisement {'activated' if ad.is_active else 'deactivated'}.", 'success')
    return redirect(url_for('admin.advertisements'))


@admin_bp.route('/advertisements/<int:id>/delete', methods=['POST'])
@role_required('admin', 'content_manager')
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
@role_required('admin', 'moderator')
def contacts():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        Contact.query.order_by(Contact.is_read.asc(), desc(Contact.created_at)), page, 20
    )
    return render_template('admin/contacts.html', pagination=pagination)


@admin_bp.route('/contacts/<int:id>/read', methods=['POST'])
@role_required('admin', 'moderator')
def mark_contact_read(id):
    msg = Contact.query.get_or_404(id)
    msg.is_read = True
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True})
        
    flash('Message marked as read.', 'success')
    return redirect(url_for('admin.contacts'))


# ════════════════════════════════════════════
#   SUCCESS STORIES MANAGEMENT (Admin Panel)
# ════════════════════════════════════════════
@admin_bp.route('/success-stories')
@role_required('admin', 'moderator')
def success_stories():
    """एडमिन ड्यासबोर्ड भित्र सबै सफलताका कथाहरू सूचीकृत गर्ने मुख्य व्यवस्थापन राउट"""
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        SuccessStory.query.order_by(desc(SuccessStory.created_at)), page, 15
    )
    return render_template('admin/success_stories.html', pagination=pagination)


@admin_bp.route('/success-stories/<int:id>/status/<string:new_status>', methods=['POST'])
@role_required('admin', 'moderator')
def update_story_status(id, new_status):
    """सफलताका कथाहरूको स्थिति (Pending, Approved, Rejected) परिमार्जन गर्ने"""
    story = SuccessStory.query.get_or_404(id)
    if new_status in ['pending', 'approved', 'rejected', 'hidden']:
        story.status = new_status
        db.session.commit()
        flash(f'Story status updated to {new_status}.', 'success')
    else:
        flash('Invalid status.', 'danger')
    return redirect(url_for('admin.success_stories'))

@admin_bp.route('/success-stories/<int:id>/delete', methods=['POST'])
@role_required('admin', 'moderator')
def delete_success_story(id):
    """एडमिन प्यानल र सर्भर स्टोरेज दुवैबाट कथा सुरक्षित रूपमा डिलिट गर्ने राउट"""
    story = SuccessStory.query.get_or_404(id)
    
    # यदि कथासँग कुनै अपलोड गरिएको तस्बिर छ भने त्यसलाई पनि सर्भरबाट सधैँका लागि सफा गर्ने
    if story.image_file:
        delete_file(story.image_file, 'stories')
        
    db.session.delete(story)
    db.session.commit()
    
    flash(f'⚠️ Success story by "{story.author_name}" has been permanently deleted.', 'warning')
    return redirect(url_for('admin.success_stories'))


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


# ════════════════════════════════════════════
#   STAFF MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/staff')
@role_required('admin')
def staff():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        StaffMember.query.order_by(desc(StaffMember.created_at)), page, 15
    )
    return render_template('admin/staff.html', pagination=pagination)


@admin_bp.route('/staff/add', methods=['GET', 'POST'])
@role_required('admin')
def add_staff():
    form = StaffMemberForm()
    if form.validate_on_submit():
        photo_file = None
        if form.profile_photo.data and form.profile_photo.data.filename:
            photo_file = save_image(form.profile_photo.data, 'staff')
        
        member = StaffMember(
            full_name=form.full_name.data.strip(),
            designation=form.designation.data.strip(),
            email=form.email.data.strip() if form.email.data else None,
            contact_number=form.contact_number.data.strip() if form.contact_number.data else None,
            profile_photo=photo_file,
            province=form.province.data or None,
            district=form.district.data or None,
            local_level=form.local_level.data or None,
            ward_number=form.ward_number.data or None,
            tole=form.tole.data or None,
            is_active=form.is_active.data
        )
        db.session.add(member)
        db.session.commit()
        flash('✅ Staff member added successfully!', 'success')
        return redirect(url_for('admin.staff'))
    
    return render_template('admin/staff_form.html', form=form, action='Add')


@admin_bp.route('/staff/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_staff(id):
    member = StaffMember.query.get_or_404(id)
    form = StaffMemberForm(obj=member)
    
    if form.validate_on_submit():
        if form.profile_photo.data and form.profile_photo.data.filename:
            if member.profile_photo:
                delete_file(member.profile_photo, 'staff')
            member.profile_photo = save_image(form.profile_photo.data, 'staff')
            
        member.full_name = form.full_name.data.strip()
        member.designation = form.designation.data.strip()
        member.email = form.email.data.strip() if form.email.data else None
        member.contact_number = form.contact_number.data.strip() if form.contact_number.data else None
        member.province = form.province.data or None
        member.district = form.district.data or None
        member.local_level = form.local_level.data or None
        member.ward_number = form.ward_number.data or None
        member.tole = form.tole.data or None
        member.is_active = form.is_active.data
        
        db.session.commit()
        flash('✅ Staff member updated successfully!', 'success')
        return redirect(url_for('admin.staff'))
        
    return render_template('admin/staff_form.html', form=form, member=member, action='Edit')


@admin_bp.route('/staff/<int:id>/delete', methods=['POST'])
@role_required('admin')
def delete_staff(id):
    member = StaffMember.query.get_or_404(id)
    if member.profile_photo:
        delete_file(member.profile_photo, 'staff')
    db.session.delete(member)
    db.session.commit()
    flash('Staff member deleted.', 'warning')
    return redirect(url_for('admin.staff'))


# ════════════════════════════════════════════
#   PARTNER MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/partners')
@role_required('admin')
def partners():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        Partner.query.order_by(desc(Partner.created_at)), page, 15
    )
    return render_template('admin/partners.html', pagination=pagination)


@admin_bp.route('/partners/add', methods=['GET', 'POST'])
@role_required('admin')
def add_partner():
    form = PartnerForm()
    if form.validate_on_submit():
        logo_file = None
        if form.logo_file.data and form.logo_file.data.filename:
            logo_file = save_image(form.logo_file.data, 'partners')
            
        partner = Partner(
            partner_name=form.partner_name.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            website_url=form.website_url.data.strip() if form.website_url.data else None,
            email=form.email.data.strip() if form.email.data else None,
            contact_number=form.contact_number.data.strip() if form.contact_number.data else None,
            address=form.address.data.strip() if form.address.data else None,
            logo_file=logo_file,
            is_active=form.is_active.data
        )
        db.session.add(partner)
        db.session.commit()
        flash('✅ Partner added successfully!', 'success')
        return redirect(url_for('admin.partners'))
        
    return render_template('admin/partner_form.html', form=form, action='Add')


@admin_bp.route('/partners/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_partner(id):
    partner = Partner.query.get_or_404(id)
    form = PartnerForm(obj=partner)
    
    if form.validate_on_submit():
        if form.logo_file.data and form.logo_file.data.filename:
            if partner.logo_file:
                delete_file(partner.logo_file, 'partners')
            partner.logo_file = save_image(form.logo_file.data, 'partners')
            
        partner.partner_name = form.partner_name.data.strip()
        partner.description = form.description.data.strip() if form.description.data else None
        partner.website_url = form.website_url.data.strip() if form.website_url.data else None
        partner.email = form.email.data.strip() if form.email.data else None
        partner.contact_number = form.contact_number.data.strip() if form.contact_number.data else None
        partner.address = form.address.data.strip() if form.address.data else None
        partner.is_active = form.is_active.data
        
        db.session.commit()
        flash('✅ Partner updated successfully!', 'success')
        return redirect(url_for('admin.partners'))
        
    return render_template('admin/partner_form.html', form=form, partner=partner, action='Edit')


@admin_bp.route('/partners/<int:id>/delete', methods=['POST'])
@role_required('admin')
def delete_partner(id):
    partner = Partner.query.get_or_404(id)
    if partner.logo_file:
        delete_file(partner.logo_file, 'partners')
    db.session.delete(partner)
    db.session.commit()
    flash('Partner deleted.', 'warning')
    return redirect(url_for('admin.partners'))


# ════════════════════════════════════════════
#   DATA QUALITY & ML OPS ENGINE
# ════════════════════════════════════════════
@admin_bp.route('/data-quality')
@role_required('admin')
def data_quality():
    # Calculate Data Quality Metrics
    total_donors = Donor.query.count()
    if total_donors == 0:
        return render_template('admin/data_quality.html', total_donors=0)
        
    # Profile completeness check
    missing_email = Donor.query.filter((Donor.email == None) | (Donor.email == '')).count()
    missing_phone2 = Donor.query.filter((Donor.phone2 == None) | (Donor.phone2 == '')).count()
    missing_last_donation = Donor.query.filter(Donor.last_donation_date == None).count()
    missing_social = Donor.query.filter((Donor.social_link == None) | (Donor.social_link == '')).count()
    missing_perm_address = Donor.query.filter((Donor.perm_district == None) | (Donor.perm_district == '')).count()
    
    completeness_score = int(100 - ((missing_email + missing_last_donation/2 + missing_perm_address) / (total_donors * 3) * 100))
    completeness_score = max(0, min(100, completeness_score))
    
    # Blood Group Supply vs Demand Imbalance
    # Ratios of Available Donors / Active Requests
    groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    group_imbalances = []
    
    for g in groups:
        supply = Donor.query.filter_by(blood_group=g, availability_status='available').count()
        demand = BloodRequest.query.filter_by(blood_group=g, status='active').count()
        
        # Determine risk level
        if demand > 0 and supply == 0:
            status = 'Critical Shortage'
            badge = 'danger'
        elif demand > 0 and supply / demand < 2:
            status = 'High Deficit'
            badge = 'warning'
        elif demand == 0:
            status = 'Healthy Supply'
            badge = 'success'
        else:
            status = 'Optimal'
            badge = 'success'
            
        group_imbalances.append({
            'group': g,
            'supply': supply,
            'demand': demand,
            'status': status,
            'badge': badge
        })
        
    # Regional Imbalance (Top active districts)
    districts = db.session.query(Donor.curr_district, func.count(Donor.id)).group_by(Donor.curr_district).order_by(desc(func.count(Donor.id))).limit(5).all()
    
    # Age group distribution
    age_18_30 = Donor.query.filter(Donor.age >= 18, Donor.age <= 30).count()
    age_31_45 = Donor.query.filter(Donor.age >= 31, Donor.age <= 45).count()
    age_46_65 = Donor.query.filter(Donor.age >= 46, Donor.age <= 65).count()
    
    age_dist = {
        'young': int((age_18_30 / total_donors) * 100) if total_donors > 0 else 0,
        'adult': int((age_31_45 / total_donors) * 100) if total_donors > 0 else 0,
        'senior': int((age_46_65 / total_donors) * 100) if total_donors > 0 else 0
    }
    
    # Duplicate detection (Same phone numbers or very similar names)
    # Since phone numbers are unique in DB now, we check for potential name duplicates
    all_donors = Donor.query.all()
    potential_duplicates = []
    from difflib import SequenceMatcher
    
    for i in range(len(all_donors)):
        for j in range(i + 1, min(i + 20, len(all_donors))): # Limit comparison complexity
            d1 = all_donors[i]
            d2 = all_donors[j]
            if d1.id != d2.id:
                ratio = SequenceMatcher(None, d1.full_name.lower(), d2.full_name.lower()).ratio()
                if ratio > 0.85:
                    potential_duplicates.append({
                        'donor1': d1,
                        'donor2': d2,
                        'similarity': int(ratio * 100)
                    })
                    
    return render_template('admin/data_quality.html',
        total_donors=total_donors,
        missing_email=missing_email,
        missing_phone2=missing_phone2,
        missing_last_donation=missing_last_donation,
        missing_social=missing_social,
        missing_perm_address=missing_perm_address,
        completeness_score=completeness_score,
        group_imbalances=group_imbalances,
        districts=districts,
        age_dist=age_dist,
        potential_duplicates=potential_duplicates
    )