import csv
import io
from urllib.parse import urljoin, urlparse
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, session, Response
)
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import (
    User, Donor, BloodRequest, News, Notice,
    Advertisement, Contact, SiteVisitor, SuccessStory, StaffMember, Partner, BloodBank, BloodInventory, BloodInventoryMovement, BloodReservation, BloodTransfer, LowStockAlert, Notification, AuditLog, Volunteer, NotificationDeliveryLog
)
from app.utils import generate_qr_code
from app.services.auth_service import AuthService
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


from app.rbac import permission_required


def _resolve_bank_tenant(bank):
    """
    If the blood bank has been provisioned with a tenant database,
    resolve its tenant context so that queries against tenant-scoped
    models (BloodInventory, etc.) hit the correct DB file.
    Safe to call on un-provisioned banks (no-op).
    """
    if bank.tenant_id and bank.db_name and bank.tenant_status == 'Active':
        try:
            from app.services.tenant_service import TenantResolutionService
            TenantResolutionService.resolve_tenant(bank.tenant_id)
        except Exception:
            pass  # fall back to main DB


def build_blood_bank_dashboard_summary(bank_id):
    bank = BloodBank.query.get_or_404(bank_id)
    _resolve_bank_tenant(bank)
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
    _resolve_bank_tenant(bank)
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
    recently_donated_donors = Donor.query.filter_by(availability_status='recently_donated').count()
    unavailable_donors = Donor.query.filter_by(availability_status='unavailable').count()
    
    total_requests  = BloodRequest.query.count()
    active_requests = BloodRequest.query.filter_by(status='active').count()
    fulfilled       = BloodRequest.query.filter_by(status='fulfilled').count()
    
    total_news      = News.query.filter_by(is_published=True).count()
    total_notices   = Notice.query.filter_by(is_active=True).count()
    unread_contacts = Contact.query.filter_by(is_read=False).count()
    total_stories   = SuccessStory.query.count()
    pending_success_stories = SuccessStory.query.filter_by(status='pending').count()
    
    total_partners  = Partner.query.count()
    total_staff     = StaffMember.query.count()
    total_advertisements = Advertisement.query.count()
    
    volunteer_doctors = Volunteer.query.filter_by(designation='Doctor').count()
    volunteer_nurses  = Volunteer.query.filter_by(designation='Nurse').count()
    volunteer_has     = Volunteer.query.filter_by(designation='HA').count()
    
    total_blood_banks = BloodBank.query.count()
    pending_events    = News.query.filter(News.category.in_(['event', 'program'])).filter(News.scheduled_date > datetime.utcnow()).count()
    
    notifications_sent = NotificationDeliveryLog.query.filter_by(status='sent').count()
    notifications_failed = NotificationDeliveryLog.query.filter_by(status='failed').count()

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
        recently_donated_donors=recently_donated_donors,
        unavailable_donors=unavailable_donors,
        total_requests=total_requests,
        active_requests=active_requests,
        fulfilled=fulfilled,
        total_news=total_news,
        total_notices=total_notices,
        unread_contacts=unread_contacts,
        total_stories=total_stories,
        pending_success_stories=pending_success_stories,
        total_partners=total_partners,
        total_staff=total_staff,
        total_advertisements=total_advertisements,
        volunteer_doctors=volunteer_doctors,
        volunteer_nurses=volunteer_nurses,
        volunteer_has=volunteer_has,
        total_blood_banks=total_blood_banks,
        pending_events=pending_events,
        notifications_sent=notifications_sent,
        notifications_failed=notifications_failed,
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
@permission_required('manage_blood_banks')
def blood_bank_inventory(bank_id):
    bank = BloodBank.query.get_or_404(bank_id)
    _resolve_bank_tenant(bank)
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
@permission_required('manage_blood_banks')
def blood_bank_transfers(bank_id):
    bank = BloodBank.query.get_or_404(bank_id)
    _resolve_bank_tenant(bank)
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
@permission_required('manage_donors')
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


@admin_bp.route('/donors/export-csv')
@permission_required('manage_donors')
def export_donors_csv():
    """Export all or filtered donors as a downloadable CSV file."""
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
        
    donors_list = query.order_by(desc(Donor.created_at)).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        'Donor ID', 'Full Name', 'Email', 'Primary Phone', 'Secondary Phone',
        'Blood Group', 'Age', 'Gender', 'Weight (kg)', 'Donor Type',
        'Availability Status', 'Last Donation Date', 'Current Province',
        'Current District', 'Current Local Level', 'Current Ward', 'Current Tole',
        'Permanent Province', 'Permanent District', 'Permanent Local Level',
        'Registered Date'
    ])
    
    for d in donors_list:
        writer.writerow([
            d.donor_id or '',
            d.full_name or '',
            d.email or '',
            d.phone1 or '',
            d.phone2 or '',
            d.blood_group or '',
            d.age or '',
            d.gender or '',
            d.weight or '',
            d.donor_type or 'regular',
            d.availability_status or 'available',
            d.last_donation_date.strftime('%Y-%m-%d') if d.last_donation_date else '',
            d.curr_province or '',
            d.curr_district or '',
            d.curr_local_level or '',
            d.curr_ward or '',
            d.curr_tole or '',
            d.perm_province or '',
            d.perm_district or '',
            d.perm_local_level or '',
            d.created_at.strftime('%Y-%m-%d %H:%M:%S') if d.created_at else ''
        ])
        
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=nepal_blood_donors_export.csv'}
    )


@admin_bp.route('/donors/sample-csv')
@permission_required('manage_donors')
def sample_donors_csv():
    """Generate and return a sample CSV template for bulk donor upload."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Full Name', 'Current Age', 'Current Weight', 'Permanent Address',
        'Current Address', 'Phone number 1', 'Phone number 2', 'Blood Group',
        'Previous Blood Donation Date (if any)', 'Previous Blood Donation Location',
        'Type of Donor', 'Social Medial Profile Link(e.g Facebook, Instagram)'
    ])
    writer.writerow([
        'Ram Bahadur Shrestha', '28', '65', 'Kavre',
        'Kathmandu', '9841234567', '9801234567', 'O+',
        '2025-10-15', 'Bir Hospital',
        'regular', 'https://facebook.com/ram'
    ])
    writer.writerow([
        'Sita Kumari Thapa', '24', '55', 'Kaski',
        'Pokhara', '9841987654', '', 'A+',
        '', '',
        'emergency', 'https://instagram.com/sita'
    ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=sample_blood_donors_import.csv'}
    )


@admin_bp.route('/donors/import-csv', methods=['POST'])
@permission_required('manage_donors')
def import_donors_csv():
    """Bulk import blood donors from a CSV file."""
    if 'csv_file' not in request.files:
        flash('No file part uploaded.', 'danger')
        return redirect(url_for('admin.donors'))
        
    file = request.files['csv_file']
    if not file or file.filename == '':
        flash('No CSV file selected for upload.', 'danger')
        return redirect(url_for('admin.donors'))
        
    if not file.filename.lower().endswith('.csv'):
        flash('Invalid file format. Please upload a .csv file.', 'danger')
        return redirect(url_for('admin.donors'))
        
    try:
        stream = io.StringIO(file.stream.read().decode('utf-8-sig', errors='replace'))
        csv_reader = csv.DictReader(stream)
        
        imported_count = 0
        skipped_count = 0
        
        default_pin_hash = generate_password_hash('1234')
        
        for idx, row in enumerate(csv_reader, start=2):
            row_data = {k.strip().lower(): (v.strip() if v else '') for k, v in row.items() if k}
            
            full_name = row_data.get('full name') or row_data.get('full_name') or row_data.get('name') or row_data.get('donor_name')
            phone1 = row_data.get('phone number 1') or row_data.get('phone1') or row_data.get('phone') or row_data.get('mobile') or row_data.get('contact')
            blood_group = row_data.get('blood group') or row_data.get('blood_group') or row_data.get('bloodgroup') or row_data.get('bg')
            
            if not full_name or not phone1 or not blood_group:
                skipped_count += 1
                continue
                
            bg_clean = blood_group.upper().replace(' ', '')
            if bg_clean not in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
                skipped_count += 1
                continue
                
            email = row_data.get('email') or f"donor_{phone1}@nepaliblooddonors.org"
            if Donor.query.filter((Donor.phone1 == phone1) | (Donor.email == email)).first():
                skipped_count += 1
                continue
                
            try:
                age_val = row_data.get('current age') or row_data.get('age')
                age = int(age_val) if age_val else 25
            except ValueError:
                age = 25
                
            try:
                weight_val = row_data.get('current weight') or row_data.get('weight')
                weight = float(weight_val) if weight_val else 60.0
            except ValueError:
                weight = 60.0
                
            last_donation_date = None
            ld_str = row_data.get('previous blood donation date (if any)') or row_data.get('last_donation_date') or row_data.get('last_donation')
            if ld_str:
                for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d'):
                    try:
                        last_donation_date = datetime.strptime(ld_str, fmt).date()
                        break
                    except ValueError:
                        pass
                        
            curr_addr = row_data.get('current address') or ''
            perm_addr = row_data.get('permanent address') or ''
            
            curr_province = row_data.get('curr_province') or row_data.get('province') or 'Bagmati'
            curr_district = row_data.get('curr_district') or row_data.get('district') or (curr_addr if curr_addr else 'Kathmandu')
            curr_local_level = row_data.get('curr_local_level') or row_data.get('local_level') or row_data.get('city') or (curr_addr if curr_addr else 'Kathmandu')
            curr_ward = row_data.get('curr_ward') or row_data.get('ward') or ''
            curr_tole = row_data.get('curr_tole') or row_data.get('tole') or ''
            
            perm_province = row_data.get('perm_province') or curr_province
            perm_district = row_data.get('perm_district') or (perm_addr if perm_addr else curr_district)
            perm_local_level = row_data.get('perm_local_level') or (perm_addr if perm_addr else curr_local_level)

            donor_type = row_data.get('type of donor') or row_data.get('donor_type') or 'regular'
            gender = row_data.get('gender') or 'male'
            social_link = row_data.get('social medial profile link(e.g facebook, instagram)') or row_data.get('social_link') or ''
            
            donor = Donor(
                full_name=full_name,
                email=email,
                phone1=phone1,
                phone2=row_data.get('phone number 2') or row_data.get('phone2') or '',
                pin_hash=default_pin_hash,
                age=age,
                weight=weight,
                blood_group=bg_clean,
                gender=gender,
                donor_type=donor_type,
                curr_province=curr_province,
                curr_district=curr_district,
                curr_local_level=curr_local_level,
                curr_ward=curr_ward,
                curr_tole=curr_tole,
                perm_province=perm_province,
                perm_district=perm_district,
                perm_local_level=perm_local_level,
                last_donation_date=last_donation_date,
                social_link=social_link,
                is_active=True,
                is_public=True
            )
            donor.recalculate_and_save()
            db.session.add(donor)
            imported_count += 1
            
        db.session.commit()
        
        audit_log = AuditLog(
            action='BULK_IMPORT_DONORS',
            details=f'Imported {imported_count} donors from CSV file ({skipped_count} skipped).',
            actor=current_user.username if hasattr(current_user, 'username') else 'admin'
        )
        db.session.add(audit_log)
        db.session.commit()
        
        msg = f"✅ Successfully imported {imported_count} donors."
        if skipped_count > 0:
            msg += f" {skipped_count} rows were skipped (duplicates or invalid data)."
        flash(msg, 'success' if imported_count > 0 else 'warning')
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error processing CSV file: {str(e)}", 'danger')
        
    return redirect(url_for('admin.donors'))


@admin_bp.route('/donors/add', methods=['GET', 'POST'])
@permission_required('manage_donors')
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
@permission_required('manage_donors')
def edit_donor(id):
    donor = Donor.query.get_or_404(id)
    
    if request.method == 'GET':
        form = DonorEditForm(obj=donor)
    else:
        form = DonorEditForm()
    form.record_id.data = donor.id
    
    if request.method == 'POST':
        if form.validate_on_submit():
            original_email = donor.email
            form.populate_obj(donor)
            # Preserve email if template doesn't have the field
            if not form.email.data:
                donor.email = original_email
            donor.updated_at = datetime.utcnow()
            db.session.commit()
            flash('✅ Donor updated successfully!', 'success')
            return redirect(url_for('admin.donors'))
        else:
            for field_name, errors in form.errors.items():
                for error in errors:
                    flash(f'⚠️ {field_name}: {error}', 'danger')
    
    return render_template('admin/donor_form.html', form=form, donor=donor, action='Edit')


@admin_bp.route('/donors/<int:id>/delete', methods=['POST'])
@permission_required('manage_donors')
def delete_donor(id):
    donor = Donor.query.get_or_404(id)
    db.session.delete(donor)
    db.session.commit()
    flash(f'Donor {donor.donor_id} deleted.', 'warning')
    return redirect(url_for('admin.donors'))


@admin_bp.route('/donors/<int:id>/toggle-status', methods=['POST'])
@permission_required('manage_donors')
def toggle_donor_status(id):
    donor = Donor.query.get_or_404(id)
    donor.availability_status = 'unavailable' if donor.availability_status == 'available' else 'available'
    db.session.commit()
    return jsonify({'status': donor.availability_status})

@admin_bp.route('/donors/<int:donor_id>/history/<int:history_id>/delete', methods=['POST'])
@permission_required('manage_donors')
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
@permission_required('manage_blood_banks')
def blood_banks():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '')
    
    query = BloodBank.query
    if search:
        query = query.filter(BloodBank.name.ilike(f'%{search}%') | BloodBank.district.ilike(f'%{search}%'))
        
    pagination = query.order_by(BloodBank.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/blood_banks.html', pagination=pagination, search=search)

@admin_bp.route('/blood-banks/create', methods=['GET', 'POST'])
@permission_required('manage_blood_banks')
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
            maps_url=form.maps_url.data,
            is_emergency_panel=form.is_emergency_panel.data,
            is_grouped_entry=form.is_grouped_entry.data,
            is_active=form.is_active.data,
            notes=form.notes.data,
            status='active' if form.is_active.data else 'inactive'
        )
        
        db.session.add(bank)
        db.session.commit()
        flash('Blood Bank created successfully!', 'success')
        return redirect(url_for('admin.blood_banks'))
        
    return render_template('admin/blood_bank_form.html', form=form, action='Create')

@admin_bp.route('/blood-banks/<int:id>/edit', methods=['GET', 'POST'])
@permission_required('manage_blood_banks')
def edit_blood_bank(id):
    from app.forms import BloodBankForm
    bank = BloodBank.query.get_or_404(id)
    form = BloodBankForm(obj=bank)
    
    if form.validate_on_submit():
        form.populate_obj(bank)
        bank.status = 'active' if form.is_active.data else 'inactive'
            
        db.session.commit()
        flash('Blood Bank updated successfully!', 'success')
        return redirect(url_for('admin.blood_banks'))
        
    return render_template('admin/blood_bank_form.html', form=form, action='Edit', bank=bank)

@admin_bp.route('/blood-banks/<int:id>/delete', methods=['POST'])
@permission_required('manage_blood_banks')
def delete_blood_bank(id):
    bank = BloodBank.query.get_or_404(id)
    
    # Delete related account (cascades to password_history and login_history)
    if bank.account:
        db.session.delete(bank.account)
    
    # Delete public cache entry
    from app.models import PublicBloodBankCache
    PublicBloodBankCache.query.filter_by(blood_bank_id=id).delete()
    
    db.session.delete(bank)
    db.session.commit()
    flash('Blood Bank and all related data deleted successfully.', 'warning')
    return redirect(url_for('admin.blood_banks'))

@admin_bp.route('/blood-banks/<int:id>/generate-account', methods=['POST'])
@permission_required('manage_users')
def generate_blood_bank_account(id):
    bank = BloodBank.query.get_or_404(id)
    
    if hasattr(bank, 'account') and bank.account:
        flash('Account already exists for this blood bank.', 'warning')
        return redirect(url_for('admin.blood_banks'))
        
    try:
        province_code = bank.province[:3].upper() if bank.province else 'UNK'
        district_code = bank.district[:3].upper() if bank.district else 'UNK'
        
        account, raw_password = AuthService.create_blood_bank_account(bank.id, province_code, district_code)
        
        # Provision the tenant database immediately
        from app.services.tenant_service import TenantProvisioningService
        TenantProvisioningService.provision_tenant(bank.id)
        
        log_audit_event('CREATE_BLOOD_BANK_ACCOUNT', bank.id, f'Created account for {bank.name}', actor=current_user.username)
        
        # Enqueue Email Notification
        if bank.email:
            from app.models import Notification, NotificationQueue
            import json
            notif = Notification(
                title='Blood Bank Account Created',
                message=f'Your portal login ID is: {account.login_id}\nYour temporary password is: {raw_password}\nPlease change it upon first login.',
                category='system',
                channel='email'
            )
            db.session.add(notif)
            db.session.flush() # get notif.id
            queue_item = NotificationQueue(
                notification_id=notif.id,
                channel='email',
                payload=json.dumps({'to': bank.email, 'subject': 'Your Nepal Blood Donors Account'})
            )
            db.session.add(queue_item)
            db.session.commit()
            flash(f'Account created and notification queued for {bank.email}', 'success')
        
        # Redirect to a dedicated credentials display page
        return render_template('admin/blood_bank_credentials.html',
                               bank=bank, account=account, raw_password=raw_password)
    except Exception as e:
        db.session.rollback()
        flash(f'Error generating account: {str(e)}', 'danger')
        
    return redirect(url_for('admin.blood_banks'))

@admin_bp.route('/blood-banks/<int:id>/account')
@login_required
@superadmin_required
def view_blood_bank_account(id):
    bank = BloodBank.query.get_or_404(id)
    if not bank.account:
        flash('No account exists for this blood bank.', 'warning')
        return redirect(url_for('admin.blood_banks'))
    return render_template('admin/blood_bank_account_detail.html', bank=bank, account=bank.account)

@admin_bp.route('/blood-banks/<int:id>/account/toggle-lock', methods=['POST'])
@login_required
@superadmin_required
def toggle_blood_bank_account_lock(id):
    bank = BloodBank.query.get_or_404(id)
    if not bank.account:
        flash('No account exists for this blood bank.', 'warning')
        return redirect(url_for('admin.blood_banks'))
    
    action = request.form.get('action', 'lock')
    if action == 'unlock':
        bank.account.is_locked = False
        bank.account.failed_login_attempts = 0
        bank.account.locked_until = None
        flash(f'Account for {bank.resolved_display_name} has been unlocked.', 'success')
        log_audit_event('UNLOCK_BLOOD_BANK_ACCOUNT', bank.id, f'Unlocked account {bank.account.login_id}', actor=current_user.username)
    else:
        bank.account.is_locked = True
        flash(f'Account for {bank.resolved_display_name} has been locked.', 'warning')
        log_audit_event('LOCK_BLOOD_BANK_ACCOUNT', bank.id, f'Locked account {bank.account.login_id}', actor=current_user.username)
    
    db.session.commit()
    return redirect(url_for('admin.view_blood_bank_account', id=bank.id))

@admin_bp.route('/blood-banks/<int:id>/account/reset-password', methods=['POST'])
@login_required
@superadmin_required
def reset_blood_bank_password(id):
    bank = BloodBank.query.get_or_404(id)
    if not bank.account:
        flash('No account exists for this blood bank.', 'warning')
        return redirect(url_for('admin.blood_banks'))
    
    from app.models import BloodBankPasswordHistory
    raw_password = AuthService.generate_secure_password()
    bank.account.set_password(raw_password)
    bank.account.temp_password = raw_password
    bank.account.password_change_required = True
    
    history = BloodBankPasswordHistory(
        # pyrefly: ignore [unexpected-keyword]
        account_id=bank.account.id,
        # pyrefly: ignore [unexpected-keyword]
        password_hash=bank.account.password_hash,
        # pyrefly: ignore [unexpected-keyword]
        created_at=datetime.utcnow()
    )
    db.session.add(history)
    db.session.commit()
    
    log_audit_event('RESET_BLOOD_BANK_PASSWORD', bank.id, f'Password reset for {bank.account.login_id}', actor=current_user.username)
    
    # Enqueue Email Notification
    if bank.email:
        from app.models import Notification, NotificationQueue
        import json
        notif = Notification(
            title='Blood Bank Password Reset',
            message=f'Your portal password has been reset.\nYour new temporary password is: {raw_password}\nPlease change it upon login.',
            category='system',
            channel='email'
        )
        db.session.add(notif)
        db.session.flush() # get notif.id
        queue_item = NotificationQueue(
            notification_id=notif.id,
            channel='email',
            payload=json.dumps({'to': bank.email, 'subject': 'Nepal Blood Donors - Password Reset'})
        )
        db.session.add(queue_item)
        flash(f'Password reset and notification queued for {bank.email}', 'success')
        
    db.session.commit()
    
    # Show the new credentials page
    return render_template('admin/blood_bank_credentials.html',
                           bank=bank, account=bank.account, raw_password=raw_password)


# ════════════════════════════════════════════
#   BLOOD REQUEST MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/requests')
@permission_required('manage_requests')
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
@permission_required('manage_requests')
def update_request_status(id, new_status):
    req = BloodRequest.query.get_or_404(id)
    if new_status in ('active', 'fulfilled', 'closed'):
        req.status = new_status
        db.session.commit()
        flash(f'Request {req.request_id} marked as {new_status}.', 'success')
    return redirect(url_for('admin.blood_requests'))


@admin_bp.route('/requests/<int:id>/verify-paper/<string:action>', methods=['POST'])
@permission_required('manage_users')
def verify_hospital_paper(id, action):
    req = BloodRequest.query.get_or_404(id)
    if action == 'verify':
        req.hospital_paper_verified = True
        flash(f'Hospital paper for request {req.request_id} approved.', 'success')
    elif action == 'reject':
        req.hospital_paper_verified = False
        flash(f'Hospital paper for request {req.request_id} rejected.', 'warning')
    db.session.commit()
    return redirect(url_for('admin.blood_requests'))


@admin_bp.route('/requests/<int:id>/delete', methods=['POST'])
@permission_required('manage_requests')
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
@permission_required('manage_users')
def delivery_logs():
    page = request.args.get('page', 1, type=int)
    from app.models import NotificationDeliveryLog
    logs = NotificationDeliveryLog.query.order_by(NotificationDeliveryLog.created_at.desc()).paginate(page=page, per_page=50)
    return render_template('admin/delivery_logs.html', logs=logs)


# ════════════════════════════════════════════
#   NEWS MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/news')
@permission_required('manage_news')
def news():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        News.query.order_by(desc(News.created_at)), page, 15
    )
    return render_template('admin/news.html', pagination=pagination)


@admin_bp.route('/news/add', methods=['GET', 'POST'])
@permission_required('manage_news')
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
@permission_required('manage_news')
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
@permission_required('manage_news')
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
@permission_required('manage_notices')
def notices():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        Notice.query.order_by(Notice.priority.desc(), desc(Notice.published_date)), page, 15
    )
    return render_template('admin/notices.html', pagination=pagination)


@admin_bp.route('/notices/add', methods=['GET', 'POST'])
@permission_required('manage_notices')
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
@permission_required('manage_notices')
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
@permission_required('manage_notices')
def delete_notice(id):
    notice = Notice.query.get_or_404(id)
    delete_file(notice.attachment, 'notices')
    db.session.delete(notice)
    db.session.commit()
    flash('Notice deleted.', 'warning')
    return redirect(url_for('admin.notices'))


@admin_bp.route('/notices/<int:id>/toggle', methods=['POST'])
@permission_required('manage_notices')
def toggle_notice(id):
    notice = Notice.query.get_or_404(id)
    notice.is_active = not notice.is_active
    db.session.commit()
    return jsonify({'is_active': notice.is_active})


# ════════════════════════════════════════════
#   ADVERTISEMENT MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/advertisements')
@permission_required('manage_users')
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
@permission_required('manage_users')
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
@permission_required('manage_users')
def toggle_ad(id):
    ad = Advertisement.query.get_or_404(id)
    ad.is_active = not ad.is_active
    db.session.commit()
    flash(f"Advertisement {'activated' if ad.is_active else 'deactivated'}.", 'success')
    return redirect(url_for('admin.advertisements'))


@admin_bp.route('/advertisements/<int:id>/delete', methods=['POST'])
@permission_required('manage_users')
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
@permission_required('moderate_content')
def contacts():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        Contact.query.order_by(Contact.is_read.asc(), desc(Contact.created_at)), page, 20
    )
    return render_template('admin/contacts.html', pagination=pagination)


@admin_bp.route('/contacts/<int:id>/read', methods=['POST'])
@permission_required('moderate_content')
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
@permission_required('manage_users')
def success_stories():
    """एडमिन ड्यासबोर्ड भित्र सबै सफलताका कथाहरू सूचीकृत गर्ने मुख्य व्यवस्थापन राउट"""
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        SuccessStory.query.order_by(desc(SuccessStory.created_at)), page, 15
    )
    return render_template('admin/success_stories.html', pagination=pagination)


@admin_bp.route('/success-stories/<int:id>/status/<string:new_status>', methods=['POST'])
@permission_required('manage_success_stories')
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
@permission_required('manage_success_stories')
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
#   STAFF MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/staff')
@permission_required('manage_staff')
def staff():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        StaffMember.query.order_by(desc(StaffMember.created_at)), page, 15
    )
    return render_template('admin/staff.html', pagination=pagination)


@admin_bp.route('/staff/add', methods=['GET', 'POST'])
@permission_required('manage_staff')
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
@permission_required('manage_staff')
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
@permission_required('manage_staff')
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
@permission_required('manage_partners')
def partners():
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        Partner.query.order_by(desc(Partner.created_at)), page, 15
    )
    return render_template('admin/partners.html', pagination=pagination)


@admin_bp.route('/partners/add', methods=['GET', 'POST'])
@permission_required('manage_partners')
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
@permission_required('manage_partners')
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
@permission_required('manage_partners')
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
@permission_required('manage_users')
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
@admin_bp.route('/notifications-dashboard')
@login_required
def notifications_dashboard():
    from app.models import NotificationQueue, NotificationDeliveryLog
    from sqlalchemy import func
    
    # Aggregates for Chart.js
    channel_stats = db.session.query(
        NotificationDeliveryLog.channel,
        func.count(NotificationDeliveryLog.id).label('total'),
        func.sum(db.case((NotificationDeliveryLog.status == 'sent', 1), else_=0)).label('success'),
        func.sum(db.case((NotificationDeliveryLog.status == 'failed', 1), else_=0)).label('failed')
    ).group_by(NotificationDeliveryLog.channel).all()
    
    queue_stats = db.session.query(
        NotificationQueue.status, func.count(NotificationQueue.id)
    ).group_by(NotificationQueue.status).all()
    
    recent_logs = NotificationDeliveryLog.query.order_by(NotificationDeliveryLog.created_at.desc()).limit(50).all()
    
    return render_template(
        'admin/notifications_dashboard.html',
        channel_stats=channel_stats,
        queue_stats=queue_stats,
        recent_logs=recent_logs
    )

# ════════════════════════════════════════════
#   ADMIN USERS MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/users')
@permission_required('manage_users')
def users():
    page = request.args.get('page', 1, type=int)
    pagination = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/users.html', pagination=pagination)

@admin_bp.route('/users/add', methods=['GET', 'POST'])
@permission_required('manage_users')
def add_user():
    from app.forms import AdminUserForm
    form = AdminUserForm()
    
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            role=form.role.data,
            is_active=form.is_active.data
        )
        password = form.password.data if form.password.data else 'admin123'
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Admin user created successfully.', 'success')
        return redirect(url_for('admin.users'))
        
    return render_template('admin/user_form.html', form=form, action='Add')

@admin_bp.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@permission_required('manage_users')
def edit_user(id):
    from app.forms import AdminUserForm
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash("You cannot edit your own role here. Use profile settings.", "warning")
        return redirect(url_for('admin.users'))
        
    form = AdminUserForm(obj=user)
    
    if form.validate_on_submit():
        form.populate_obj(user)
        if form.password.data:
            user.set_password(form.password.data)
        db.session.commit()
        flash('Admin user updated successfully!', 'success')
        return redirect(url_for('admin.users'))
        
    return render_template('admin/user_form.html', form=form, action='Edit', user=user)

@admin_bp.route('/users/<int:id>/delete', methods=['POST'])
@permission_required('manage_users')
def delete_user(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash("You cannot delete yourself.", "danger")
        return redirect(url_for('admin.users'))
        
    db.session.delete(user)
    db.session.commit()
    flash('Admin user deleted successfully.', 'warning')
    return redirect(url_for('admin.users'))

# ════════════════════════════════════════════
#   VOLUNTEER APPROVALS MANAGEMENT
# ════════════════════════════════════════════
@admin_bp.route('/volunteers')
@permission_required('manage_volunteer_approvals')
def volunteers():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    
    query = Volunteer.query
    if search:
        query = query.filter(
            or_(
                Volunteer.full_name.like(f'%{search}%'),
                Volunteer.email.like(f'%{search}%'),
                Volunteer.phone1.like(f'%{search}%')
            )
        )
    
    pagination = paginate_query(
        query.order_by(desc(Volunteer.created_at)), page, 15
    )
    return render_template('admin/volunteers.html', pagination=pagination, search=search)

@admin_bp.route('/volunteers/<int:id>/approve', methods=['POST'])
@permission_required('manage_volunteer_approvals')
def approve_volunteer(id):
    volunteer = Volunteer.query.get_or_404(id)
    volunteer.is_approved = True
    db.session.commit()
    flash(f'Volunteer {volunteer.full_name} has been approved!', 'success')
    return redirect(url_for('admin.volunteers'))

@admin_bp.route('/volunteers/<int:id>/toggle-active', methods=['POST'])
@permission_required('manage_volunteer_approvals')
def toggle_volunteer_active(id):
    volunteer = Volunteer.query.get_or_404(id)
    volunteer.is_active = not volunteer.is_active
    db.session.commit()
    status = 'activated' if volunteer.is_active else 'deactivated'
    flash(f'Volunteer {volunteer.full_name} has been {status}!', 'info')
    return redirect(url_for('admin.volunteers'))

@admin_bp.route('/volunteers/<int:id>/delete', methods=['POST'])
@permission_required('manage_volunteer_approvals')
def delete_volunteer(id):
    volunteer = Volunteer.query.get_or_404(id)
    db.session.delete(volunteer)
    db.session.commit()
    flash(f'Volunteer {volunteer.full_name} deleted successfully.', 'warning')
    return redirect(url_for('admin.volunteers'))


@admin_bp.context_processor
def inject_admin_globals():
    from app.rbac import has_permission as check_permission
    if current_user.is_authenticated:
        from app.models import Donor, BloodRequest, Contact, Volunteer
        try:
            donor_count = Donor.query.count()
            active_req_count = BloodRequest.query.filter_by(status='active').count()
            unread_count = Contact.query.filter_by(is_read=False).count()
            pending_volunteers = Volunteer.query.filter_by(is_approved=False).count()
            return dict(
                donor_count=donor_count,
                active_req_count=active_req_count,
                unread_count=unread_count,
                pending_volunteers_count=pending_volunteers,
                has_permission=lambda perm: check_permission(current_user, perm)
            )
        except Exception:
            pass
    return dict(
        has_permission=lambda perm: False
    )



