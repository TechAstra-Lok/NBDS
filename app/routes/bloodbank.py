"""
Blood Bank Authentication Blueprint
Handles login, logout, password change, and first-login flows for blood bank accounts.
Isolated from the admin authentication system.
"""
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session
)
from app import db
from app.models import BloodBankAccount, BloodBankLoginHistory, BloodBankPasswordHistory
from app.services.auth_service import AuthService
import json
from datetime import datetime, timedelta, timezone
from functools import wraps

bloodbank_bp = Blueprint('bloodbank', __name__, template_folder='../templates/bloodbank')

# ── Configuration ──────────────────────────────────
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30


def bloodbank_login_required(f):
    """Decorator that ensures the user is a logged-in BloodBankAccount (not an admin User)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('bloodbank_account_id'):
            flash('Please log in to access your blood bank dashboard.', 'warning')
            return redirect(url_for('bloodbank.login'))
        account = BloodBankAccount.query.get(session['bloodbank_account_id'])
        if not account:
            session.pop('bloodbank_account_id', None)
            flash('Session expired. Please log in again.', 'warning')
            return redirect(url_for('bloodbank.login'))
            
        # --- Multi-Tenant Support ---
        # Resolve tenant DB if available, otherwise fall back to primary DB
        if account.blood_bank and account.blood_bank.tenant_id:
            try:
                from app.services.tenant_service import TenantResolutionService
                TenantResolutionService.resolve_tenant(account.blood_bank.tenant_id)
            except Exception:
                pass

        return f(*args, **kwargs)
    return decorated


# ── Login ──────────────────────────────────────────
@bloodbank_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Already logged in?
    if session.get('bloodbank_account_id'):
        return redirect(url_for('bloodbank.dashboard'))

    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '').strip()

        from sqlalchemy import func, or_
        from app.models import BloodBank
        
        # Look up by login_id (case-insensitive) or by associated blood bank email/phone
        account = BloodBankAccount.query.filter(
            func.lower(BloodBankAccount.login_id) == login_id.lower()
        ).first()

        if not account:
            bank = BloodBank.query.filter(
                or_(
                    func.lower(BloodBank.email) == login_id.lower(),
                    BloodBank.phone == login_id,
                    BloodBank.contact_number == login_id,
                    BloodBank.alternate_contact_number == login_id
                )
            ).first()
            if bank and bank.account:
                account = bank.account

        # Record login attempt
        def record_login(acct, status):
            entry = BloodBankLoginHistory(
                account_id=acct.id,
                login_time=datetime.now(timezone.utc),
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')[:255],
                status=status
            )
            db.session.add(entry)

        if not account:
            flash('Invalid login ID or password.', 'danger')
            return render_template('bloodbank/login.html')

        # Check lock status
        if account.is_locked:
            if account.locked_until and datetime.now(timezone.utc) > account.locked_until:
                # Auto-unlock after lockout period
                account.is_locked = False
                account.failed_login_attempts = 0
                account.locked_until = None
                db.session.commit()
            else:
                record_login(account, 'locked')
                db.session.commit()
                flash('Account is locked due to too many failed login attempts. Please contact the administrator.', 'danger')
                return render_template('bloodbank/login.html')

        # Check suspended status
        if account.account_status == 'suspended':
            flash('This account has been suspended. Please contact the administrator.', 'danger')
            return render_template('bloodbank/login.html')

        # Verify password
        if not account.check_password(password):
            account.failed_login_attempts = (account.failed_login_attempts or 0) + 1
            if account.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                account.is_locked = True
                account.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                record_login(account, 'locked')
                db.session.commit()
                flash(f'Account locked after {MAX_FAILED_ATTEMPTS} failed attempts. Try again in {LOCKOUT_DURATION_MINUTES} minutes.', 'danger')
            else:
                remaining = MAX_FAILED_ATTEMPTS - account.failed_login_attempts
                record_login(account, 'failed')
                db.session.commit()
                flash(f'Invalid login ID or password. {remaining} attempt(s) remaining.', 'danger')
            return render_template('bloodbank/login.html')

        # Success — reset counters
        account.failed_login_attempts = 0
        account.last_login_at = datetime.now(timezone.utc)
        if account.account_status == 'pending':
            account.account_status = 'active'
        record_login(account, 'success')
        db.session.commit()

        # Store in session (NOT Flask-Login — that's for admin users)
        session['bloodbank_account_id'] = account.id
        session['bloodbank_login_id'] = account.login_id
        session['bloodbank_bank_name'] = account.blood_bank.resolved_display_name

        # Force password change on first login
        if account.password_change_required:
            flash('You must change your password before proceeding.', 'warning')
            return redirect(url_for('bloodbank.change_password'))

        flash(f'Welcome, {account.blood_bank.resolved_display_name}!', 'success')
        return redirect(url_for('bloodbank.dashboard'))

    return render_template('bloodbank/login.html')


# ── Logout ─────────────────────────────────────────
@bloodbank_bp.route('/logout')
def logout():
    session.pop('bloodbank_account_id', None)
    session.pop('bloodbank_login_id', None)
    session.pop('bloodbank_bank_name', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('bloodbank.login'))


# ── Password Change ────────────────────────────────
@bloodbank_bp.route('/change-password', methods=['GET', 'POST'])
@bloodbank_login_required
def change_password():
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required

    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Only verify current password if this is NOT a forced change
        if not account.password_change_required:
            if not account.check_password(current_password):
                flash('Current password is incorrect.', 'danger')
                return render_template('bloodbank/change_password.html', forced=False)

        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return render_template('bloodbank/change_password.html', forced=account.password_change_required)

        # Validate policy
        is_valid, message = AuthService.validate_password_policy(new_password, account=account)
        if not is_valid:
            flash(message, 'danger')
            return render_template('bloodbank/change_password.html', forced=account.password_change_required)

        # Apply
        account.set_password(new_password)
        account.temp_password = None
        account.password_change_required = False
        
        account.password_changed_at = datetime.now(timezone.utc)

        history = BloodBankPasswordHistory(
            account_id=account.id,
            password_hash=account.password_hash,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(history)
        db.session.commit()

        flash('Password changed successfully!', 'success')
        return redirect(url_for('bloodbank.dashboard'))

    return render_template('bloodbank/change_password.html', forced=account.password_change_required)

# ── Reservations ─────────────────────────────────────
@bloodbank_bp.route('/reservations')
@bloodbank_login_required
def reservations():
    from app.models import BloodReservation
    from app.utils import paginate_query
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    
    query = BloodReservation.query.filter_by(blood_bank_id=account.blood_bank_id)
    if status_filter:
        query = query.filter_by(status=status_filter)
        
    pagination = paginate_query(query.order_by(BloodReservation.requested_at.desc()), page, 15)
    return render_template('bloodbank/reservations.html', pagination=pagination, status_filter=status_filter)


@bloodbank_bp.route('/reservations/add', methods=['POST'])
@bloodbank_login_required
def add_reservation():
    from app.models import BloodReservation
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    
    hospital_name = request.form.get('hospital_name', '').strip()
    patient_name = request.form.get('patient_name', '').strip()
    blood_group = request.form.get('blood_group', '').strip()
    component = request.form.get('component', 'Whole Blood').strip()
    units = request.form.get('units', 1, type=int)
    priority = request.form.get('priority', 'normal').strip()
    
    if not all([hospital_name, patient_name, blood_group]):
        flash('Hospital name, patient name, and blood group are required.', 'danger')
        return redirect(url_for('bloodbank.reservations'))
        
    import uuid
    new_reservation = BloodReservation(
        blood_bank_id=account.blood_bank_id,
        hospital_name=hospital_name,
        patient_name=patient_name,
        blood_group=blood_group,
        component=component,
        units=units,
        priority=priority,
        status='pending',
        qr_code=str(uuid.uuid4())[:8].upper()
    )
    db.session.add(new_reservation)
    db.session.commit()
    
    flash(f'Reservation for {hospital_name} created successfully.', 'success')
    return redirect(url_for('bloodbank.reservations'))


@bloodbank_bp.route('/reservations/<int:id>/status', methods=['POST'])
@bloodbank_login_required
def update_reservation_status(id):
    from app.models import BloodReservation, BloodInventory, BloodInventoryMovement, AuditLog
    from app.services.inventory_service import InventoryService
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    
    reservation = BloodReservation.query.filter_by(id=id, blood_bank_id=account.blood_bank_id).first_or_404()
    new_status = request.form.get('status', '').strip().lower()
    
    allowed_statuses = ['approved', 'rejected', 'more_info', 'cancelled', 'fulfilled', 'under_review']
    if new_status not in allowed_statuses:
        flash('Invalid reservation status requested.', 'danger')
        return redirect(url_for('bloodbank.reservations'))
        
    if reservation.status == new_status:
        flash('Reservation is already in that status.', 'info')
        return redirect(url_for('bloodbank.reservations'))
        
    # Transactional inventory locking
    inventory = BloodInventory.query.filter_by(
        blood_bank_id=account.blood_bank_id, 
        blood_group=reservation.blood_group, 
        component=reservation.component
    ).with_for_update().first()
    
    old_status = reservation.status

    if new_status == 'approved' and old_status in ['pending', 'under_review', 'more_info']:
        if not inventory or inventory.available_units < reservation.units:
            avail = inventory.available_units if inventory else 0
            flash(f'Stock Conflict: Insufficient stock of {reservation.blood_group} ({reservation.component}). Available: {avail}, Requested: {reservation.units}. Cannot approve.', 'danger')
            return redirect(url_for('bloodbank.reservations'))
        
        # Atomically reserve inventory units
        inventory.units_reserved += reservation.units
        inventory.last_updated = datetime.now(timezone.utc)
        
        # Log inventory movement
        movement = BloodInventoryMovement(
            inventory_id=inventory.id,
            movement_type='reservation_lock',
            units=reservation.units,
            note=f"Locked for Reservation #{reservation.id} ({reservation.patient_name})",
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(movement)
        
    elif new_status in ['cancelled', 'rejected'] and old_status == 'approved':
        if inventory:
            # Free up the reserved units
            inventory.units_reserved = max(0, inventory.units_reserved - reservation.units)
            inventory.last_updated = datetime.now(timezone.utc)
            
            movement = BloodInventoryMovement(
                inventory_id=inventory.id,
                movement_type='reservation_release',
                units=reservation.units,
                note=f"Released from Reservation #{reservation.id} (Status changed to {new_status})",
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(movement)
            
    elif new_status == 'fulfilled' and old_status == 'approved':
        if inventory:
            # Physically deduct from stock and release reservation lock
            inventory.units_reserved = max(0, inventory.units_reserved - reservation.units)
            inventory.units_available = max(0, inventory.units_available - reservation.units)
            inventory.last_updated = datetime.now(timezone.utc)
            
            movement = BloodInventoryMovement(
                inventory_id=inventory.id,
                movement_type='issue_fulfilled',
                units=reservation.units,
                note=f"Issued & Dispensed for Reservation #{reservation.id} ({reservation.hospital_name})",
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(movement)
            
    reservation.status = new_status
    reservation.updated_at = datetime.now(timezone.utc)

    # Create immutable audit log
    audit = AuditLog(
        action=f"reservation_{new_status}",
        entity_id=reservation.id,
        details=f"Reservation #{reservation.id} changed from '{old_status}' to '{new_status}' by {account.login_id}",
        actor=account.login_id
    )
    db.session.add(audit)
    db.session.commit()
    
    # Sync public cache if inventory changed
    if inventory:
        try:
            InventoryService.sync_public_cache(account.blood_bank_id)
        except Exception:
            pass
        
    status_labels = {
        'approved': 'Approved and units locked',
        'fulfilled': 'Marked as Issued & Fulfilled',
        'rejected': 'Rejected',
        'more_info': 'Marked as More Information Required',
        'cancelled': 'Cancelled'
    }
    flash(f'Reservation #{reservation.id} successfully {status_labels.get(new_status, new_status)}.', 'success')
    return redirect(url_for('bloodbank.reservations'))


# ── Staff Management (Strict Blood Bank Isolation) ─────────────
@bloodbank_bp.route('/staff')
@bloodbank_login_required
def staff():
    from app.models import StaffMember
    from app.utils import paginate_query
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()
    
    query = StaffMember.query.filter_by(blood_bank_id=account.blood_bank_id)
    if search:
        query = query.filter(
            (StaffMember.full_name.ilike(f"%{search}%")) |
            (StaffMember.designation.ilike(f"%{search}%")) |
            (StaffMember.contact_number.ilike(f"%{search}%"))
        )
    if status:
        query = query.filter_by(availability_status=status)
        
    pagination = paginate_query(
        query.order_by(StaffMember.created_at.desc()), page, 15
    )
    
    total_staff = StaffMember.query.filter_by(blood_bank_id=account.blood_bank_id).count()
    active_staff = StaffMember.query.filter_by(blood_bank_id=account.blood_bank_id, is_active=True, employment_status='active').count()
    on_duty_staff = StaffMember.query.filter_by(blood_bank_id=account.blood_bank_id, availability_status='on_duty').count()
    emergency_staff = StaffMember.query.filter_by(blood_bank_id=account.blood_bank_id, availability_status='emergency_standby').count()

    return render_template(
        'bloodbank/staff.html',
        pagination=pagination,
        account=account,
        bank=account.blood_bank,
        total_staff=total_staff,
        active_staff=active_staff,
        on_duty_staff=on_duty_staff,
        emergency_staff=emergency_staff,
        search=search,
        selected_status=status
    )


@bloodbank_bp.route('/staff/add', methods=['GET', 'POST'])
@bloodbank_login_required
def add_staff():
    from app.models import StaffMember, AuditLog
    from app.forms import StaffMemberForm
    from app.utils import save_image
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    
    form = StaffMemberForm()
    if form.validate_on_submit():
        photo_file = None
        if form.profile_photo.data and form.profile_photo.data.filename:
            photo_file = save_image(form.profile_photo.data, 'staff')
        
        member = StaffMember(
            blood_bank_id=account.blood_bank_id,
            full_name=(form.full_name.data or "").strip(),
            designation=(form.designation.data or "").strip(),
            qualification=form.qualification.data.strip() if form.qualification.data else None,
            registration_number=form.registration_number.data.strip() if form.registration_number.data else None,
            email=form.email.data.strip() if form.email.data else None,
            contact_number=form.contact_number.data.strip() if form.contact_number.data else None,
            secondary_contact=form.secondary_contact.data.strip() if form.secondary_contact.data else None,
            emergency_contact=form.emergency_contact.data.strip() if form.emergency_contact.data else None,
            profile_photo=photo_file,
            availability_status=form.availability_status.data or 'available',
            employment_status=form.employment_status.data or 'active',
            profile_visibility=form.profile_visibility.data or 'public',
            province=form.province.data or None,
            district=form.district.data or None,
            local_level=form.local_level.data or None,
            ward_number=form.ward_number.data or None,
            tole=form.tole.data or None,
            is_active=form.is_active.data,
            created_by=account.login_id
        )
        db.session.add(member)
        
        log = AuditLog(
            action='BLOOD_BANK_STAFF_CREATED',
            entity_id=account.blood_bank_id,
            details=f"Created staff member '{member.full_name}' ({member.designation}) for Blood Bank {account.blood_bank.name}.",
            actor=account.login_id
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Staff member "{member.full_name}" added successfully!', 'success')
        return redirect(url_for('bloodbank.staff'))
    
    return render_template('bloodbank/staff_form.html', form=form, account=account, bank=account.blood_bank, action='Add')


@bloodbank_bp.route('/staff/<int:id>/edit', methods=['GET', 'POST'])
@bloodbank_login_required
def edit_staff(id):
    from app.models import StaffMember, AuditLog
    from app.forms import StaffMemberForm
    from app.utils import save_image, delete_file
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required

    member = StaffMember.query.filter_by(id=id, blood_bank_id=account.blood_bank_id).first_or_404()
    form = StaffMemberForm(obj=member)
    
    if form.validate_on_submit():
        if form.profile_photo.data and form.profile_photo.data.filename:
            if member.profile_photo:
                delete_file(member.profile_photo, 'staff')
            member.profile_photo = save_image(form.profile_photo.data, 'staff')
            
        member.full_name = (form.full_name.data or "").strip()
        member.designation = (form.designation.data or "").strip()
        member.qualification = form.qualification.data.strip() if form.qualification.data else None
        member.registration_number = form.registration_number.data.strip() if form.registration_number.data else None
        member.email = form.email.data.strip() if form.email.data else None
        member.contact_number = form.contact_number.data.strip() if form.contact_number.data else None
        member.secondary_contact = form.secondary_contact.data.strip() if form.secondary_contact.data else None
        member.emergency_contact = form.emergency_contact.data.strip() if form.emergency_contact.data else None
        member.availability_status = form.availability_status.data or member.availability_status
        member.employment_status = form.employment_status.data or member.employment_status
        member.profile_visibility = form.profile_visibility.data or member.profile_visibility
        member.province = form.province.data or None
        member.district = form.district.data or None
        member.local_level = form.local_level.data or None
        member.ward_number = form.ward_number.data or None
        member.tole = form.tole.data or None
        member.is_active = form.is_active.data
        member.updated_by = account.login_id
        
        log = AuditLog(
            action='BLOOD_BANK_STAFF_UPDATED',
            entity_id=account.blood_bank_id,
            details=f"Updated staff member '{member.full_name}' (ID: {member.id}).",
            actor=account.login_id
        )
        db.session.add(log)
        db.session.commit()
        flash(f'Staff member "{member.full_name}" updated successfully!', 'success')
        return redirect(url_for('bloodbank.staff'))
        
    return render_template('bloodbank/staff_form.html', form=form, member=member, account=account, bank=account.blood_bank, action='Edit')


@bloodbank_bp.route('/staff/<int:id>/delete', methods=['POST'])
@bloodbank_login_required
def delete_staff(id):
    from app.models import StaffMember, AuditLog
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required

    member = StaffMember.query.filter_by(id=id, blood_bank_id=account.blood_bank_id).first_or_404()
    
    # Soft archive instead of destroying historical shift records
    member.is_active = False
    member.employment_status = 'archived'
    member.availability_status = 'inactive'
    member.updated_by = account.login_id
    
    log = AuditLog(
        action='BLOOD_BANK_STAFF_DEACTIVATED',
        entity_id=account.blood_bank_id,
        details=f"Deactivated and archived staff member '{member.full_name}' (ID: {member.id}).",
        actor=account.login_id
    )
    db.session.add(log)
    db.session.commit()
    
    flash(f'Staff member "{member.full_name}" has been deactivated and archived.', 'info')
    return redirect(url_for('bloodbank.staff'))


# ── Three-Shift Management (Previous / Current / Next) ────────
@bloodbank_bp.route('/shifts')
@bloodbank_login_required
def shifts():
    from app.models import BloodBankShift, StaffMember
    from app.services.shift_service import ShiftService
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    bank_id = account.blood_bank_id

    # 3-Shift Board calculation
    three_shifts = ShiftService.get_three_shifts(bank_id)
    
    # All active shifts configured for this bank
    all_shifts = BloodBankShift.query.filter_by(blood_bank_id=bank_id).order_by(BloodBankShift.start_time).all()
    
    # All active staff available for assignment
    available_staff = StaffMember.query.filter_by(
        blood_bank_id=bank_id,
        is_active=True,
        employment_status='active'
    ).order_by(StaffMember.full_name).all()

    return render_template(
        'bloodbank/shifts.html',
        account=account,
        bank=account.blood_bank,
        three_shifts=three_shifts,
        all_shifts=all_shifts,
        available_staff=available_staff
    )


@bloodbank_bp.route('/shifts/add', methods=['GET', 'POST'])
@bloodbank_login_required
def add_shift():
    from app.models import BloodBankShift, AuditLog
    from app.forms import BloodBankShiftForm
    from datetime import datetime
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    
    form = BloodBankShiftForm()
    if form.validate_on_submit():
        st_parts = (form.start_time.data or "").strip().split(':')
        et_parts = (form.end_time.data or "").strip().split(':')
        start_t = datetime.strptime((form.start_time.data or "").strip(), '%H:%M').time()
        end_t = datetime.strptime((form.end_time.data or "").strip(), '%H:%M').time()
        
        shift = BloodBankShift(
            blood_bank_id=account.blood_bank_id,
            shift_name=(form.shift_name.data or "").strip(),
            shift_type=form.shift_type.data,
            start_time=start_t,
            end_time=end_t,
            notes=form.notes.data.strip() if form.notes.data else None,
            is_active=form.is_active.data,
            created_by=account.login_id
        )
        db.session.add(shift)
        
        log = AuditLog(
            action='BLOOD_BANK_SHIFT_CREATED',
            entity_id=account.blood_bank_id,
            details=f"Created shift '{shift.shift_name}' ({form.start_time.data} - {form.end_time.data}) for Blood Bank {account.blood_bank.name}.",
            actor=account.login_id
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Shift "{shift.shift_name}" created successfully!', 'success')
        return redirect(url_for('bloodbank.shifts'))
        
    return render_template('bloodbank/shift_form.html', form=form, account=account, bank=account.blood_bank, action='Add')


@bloodbank_bp.route('/shifts/<int:id>/edit', methods=['GET', 'POST'])
@bloodbank_login_required
def edit_shift(id):
    from app.models import BloodBankShift, AuditLog
    from app.forms import BloodBankShiftForm
    from datetime import datetime
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    
    shift = BloodBankShift.query.filter_by(id=id, blood_bank_id=account.blood_bank_id).first_or_404()
    form = BloodBankShiftForm(obj=shift)
    
    if request.method == 'GET':
        form.start_time.data = shift.start_time.strftime('%H:%M') if shift.start_time else ''
        form.end_time.data = shift.end_time.strftime('%H:%M') if shift.end_time else ''

    if form.validate_on_submit():
        start_t = datetime.strptime((form.start_time.data or "").strip(), '%H:%M').time()
        end_t = datetime.strptime((form.end_time.data or "").strip(), '%H:%M').time()
        
        shift.shift_name = (form.shift_name.data or "").strip()
        shift.shift_type = form.shift_type.data
        shift.start_time = start_t
        shift.end_time = end_t
        shift.notes = form.notes.data.strip() if form.notes.data else None
        shift.is_active = form.is_active.data
        shift.updated_by = account.login_id
        
        log = AuditLog(
            action='BLOOD_BANK_SHIFT_UPDATED',
            entity_id=account.blood_bank_id,
            details=f"Updated shift '{shift.shift_name}' (ID: {shift.id}).",
            actor=account.login_id
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Shift "{shift.shift_name}" updated successfully!', 'success')
        return redirect(url_for('bloodbank.shifts'))
        
    return render_template('bloodbank/shift_form.html', form=form, shift=shift, account=account, bank=account.blood_bank, action='Edit')


@bloodbank_bp.route('/shifts/assign', methods=['POST'])
@bloodbank_login_required
def assign_staff_shift():
    from app.services.shift_service import ShiftService
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    
    shift_id = request.form.get('shift_id', type=int)
    staff_id = request.form.get('staff_id', type=int)
    role_in_shift = request.form.get('role_in_shift', '').strip()
    
    if not shift_id or not staff_id:
        flash('Please select both a Shift and a Staff member.', 'danger')
        return redirect(url_for('bloodbank.shifts'))
        
    ok, msg = ShiftService.assign_staff(
        blood_bank_id=account.blood_bank_id,
        shift_id=shift_id,
        staff_id=staff_id,
        role_in_shift=role_in_shift,
        actor=account.login_id
    )
    
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('bloodbank.shifts'))


@bloodbank_bp.route('/shifts/assignment/<int:id>/remove', methods=['POST'])
@bloodbank_login_required
def remove_staff_shift(id):
    from app.services.shift_service import ShiftService
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    
    ok, msg = ShiftService.remove_assignment(
        blood_bank_id=account.blood_bank_id,
        assignment_id=id,
        actor=account.login_id
    )
    flash(msg, 'info' if ok else 'danger')
    return redirect(url_for('bloodbank.shifts'))


# ── Dashboard ─────────────────────────────────────
@bloodbank_bp.route('/dashboard')
@bloodbank_login_required
def dashboard():
    from app.models import BloodInventory, StaffMember, BloodReservation, BloodTransfer
    from app.services.shift_service import ShiftService
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    # Force password change if still required
    if account.password_change_required:
        return redirect(url_for('bloodbank.change_password'))
        
    bank_id = account.blood_bank_id
    inventory_items = BloodInventory.query.filter_by(blood_bank_id=bank_id).all()
    
    # Staff stats strictly isolated for this blood bank
    staff_count = StaffMember.query.filter_by(blood_bank_id=bank_id).count()
    active_staff_count = StaffMember.query.filter_by(blood_bank_id=bank_id, is_active=True, employment_status='active').count()
    on_duty_count = StaffMember.query.filter_by(blood_bank_id=bank_id, availability_status='on_duty').count()
    emergency_count = StaffMember.query.filter_by(blood_bank_id=bank_id, availability_status='emergency_standby').count()
    
    reservations_count = BloodReservation.query.filter_by(blood_bank_id=bank_id, status='pending').count()
    transfers_count = BloodTransfer.query.filter_by(source_bank_id=bank_id, status='pending').count()
    
    # Real-time 3-shift roster
    three_shifts = ShiftService.get_three_shifts(bank_id)

    # Real-time alerts and nearby requests
    from app.models import BloodBankNotification
    recent_notifications = BloodBankNotification.query.filter_by(
        blood_bank_id=bank_id,
        is_archived=False
    ).order_by(BloodBankNotification.created_at.desc()).limit(5).all()

    nearby_alerts = BloodBankNotification.query.filter_by(
        blood_bank_id=bank_id,
        notification_type='NEARBY_REQUEST',
        is_archived=False
    ).order_by(BloodBankNotification.created_at.desc()).limit(5).all()

    return render_template(
        'bloodbank/dashboard.html', 
        account=account, 
        bank=account.blood_bank, 
        inventory_items=inventory_items,
        staff_count=staff_count,
        active_staff_count=active_staff_count,
        on_duty_count=on_duty_count,
        emergency_count=emergency_count,
        reservations_count=reservations_count,
        transfers_count=transfers_count,
        three_shifts=three_shifts,
        recent_notifications=recent_notifications,
        nearby_alerts=nearby_alerts
    )


# ── Inventory Management ──────────────────────────
@bloodbank_bp.route('/inventory')
@bloodbank_login_required
def inventory():
    from app.models import BloodInventory
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    items = BloodInventory.query.filter_by(blood_bank_id=account.blood_bank_id).order_by(BloodInventory.blood_group).all()
    return render_template('bloodbank/inventory.html', account=account, bank=account.blood_bank, items=items)


@bloodbank_bp.route('/inventory/add', methods=['GET', 'POST'])
@bloodbank_login_required
def add_inventory():
    from app.models import BloodInventory, BloodInventoryMovement
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required

    if request.method == 'POST':
        blood_group = request.form.get('blood_group', '').strip()
        component = request.form.get('component', 'Whole Blood').strip()
        units = int(request.form.get('units_available', 0))
        minimum_stock = int(request.form.get('minimum_stock', 4))
        maximum_stock = int(request.form.get('maximum_stock', 20))

        if not blood_group:
            flash('Blood group is required.', 'danger')
            return render_template('bloodbank/inventory_form.html', account=account, bank=account.blood_bank, mode='add')

        # Check for duplicate
        existing = BloodInventory.query.filter_by(
            blood_bank_id=account.blood_bank_id,
            blood_group=blood_group,
            component=component
        ).first()
        if existing:
            flash(f'Inventory for {blood_group} ({component}) already exists. Edit the existing record instead.', 'warning')
            return redirect(url_for('bloodbank.inventory'))

        item = BloodInventory(
            blood_bank_id=account.blood_bank_id,
            blood_group=blood_group,
            component=component,
            units_available=units,
            minimum_stock=minimum_stock,
            maximum_stock=maximum_stock,
            last_updated=datetime.now(timezone.utc)
        )
        db.session.add(item)
        db.session.flush()

        # Log the initial stock as a movement
        if units > 0:
            movement = BloodInventoryMovement(
                inventory_id=item.id,
                movement_type='addition',
                units=units,
                note='Initial stock setup',
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(movement)

        db.session.commit()
        
        # Sync public cache
        from app.services.inventory_service import InventoryService
        InventoryService.sync_public_cache(account.blood_bank_id)

        flash(f'Inventory for {blood_group} ({component}) created with {units} units.', 'success')
        return redirect(url_for('bloodbank.inventory'))

    return render_template('bloodbank/inventory_form.html', account=account, bank=account.blood_bank, mode='add')


@bloodbank_bp.route('/inventory/<int:id>/edit', methods=['GET', 'POST'])
@bloodbank_login_required
def edit_inventory(id):
    from app.models import BloodInventory, BloodInventoryMovement
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    item = BloodInventory.query.filter_by(id=id, blood_bank_id=account.blood_bank_id).first_or_404()

    if request.method == 'POST':
        new_units = int(request.form.get('units_available', item.units_available))
        minimum_stock = int(request.form.get('minimum_stock', item.minimum_stock))
        maximum_stock = int(request.form.get('maximum_stock', item.maximum_stock))
        note = request.form.get('note', '').strip()

        diff = new_units - item.units_available
        if diff != 0:
            movement = BloodInventoryMovement(
                inventory_id=item.id,
                movement_type='addition' if diff > 0 else 'removal',
                units=abs(diff),
                note=note or ('Stock adjusted' if diff != 0 else ''),
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(movement)

        item.units_available = new_units
        item.minimum_stock = minimum_stock
        item.maximum_stock = maximum_stock
        item.last_updated = datetime.now(timezone.utc)
        db.session.commit()

        # Sync public cache
        from app.services.inventory_service import InventoryService
        InventoryService.sync_public_cache(account.blood_bank_id)

        flash(f'Inventory for {item.blood_group} ({item.component}) updated.', 'success')
        return redirect(url_for('bloodbank.inventory'))

    movements = BloodInventoryMovement.query.filter_by(inventory_id=item.id).order_by(BloodInventoryMovement.created_at.desc()).limit(20).all()
    return render_template('bloodbank/inventory_form.html', account=account, bank=account.blood_bank, mode='edit', item=item, movements=movements)


@bloodbank_bp.route('/inventory/<int:id>/delete', methods=['POST'])
@bloodbank_login_required
def delete_inventory(id):
    from app.models import BloodInventory
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None  # guaranteed by @bloodbank_login_required
    item = BloodInventory.query.filter_by(id=id, blood_bank_id=account.blood_bank_id).first_or_404()

    if item.units_reserved > 0:
        flash(f'Cannot delete {item.blood_group} ({item.component}) — it has {item.units_reserved} reserved units. Cancel reservations first.', 'danger')
        return redirect(url_for('bloodbank.inventory'))

    label = f'{item.blood_group} ({item.component})'
    db.session.delete(item)
    db.session.commit()
    
    # Sync public cache
    from app.services.inventory_service import InventoryService
    InventoryService.sync_public_cache(account.blood_bank_id)

    flash(f'Inventory record for {label} deleted.', 'success')
    return redirect(url_for('bloodbank.inventory'))


# ── Notification Center & Real-Time Alerts ───────────
@bloodbank_bp.route('/notifications')
@bloodbank_login_required
def notifications():
    from app.models import BloodBankNotification
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None
    bank = account.blood_bank

    tab = request.args.get('tab', 'unread').strip()
    page = request.args.get('page', 1, type=int)

    query = BloodBankNotification.query.filter_by(blood_bank_id=account.blood_bank_id)

    if tab == 'unread':
        query = query.filter_by(is_read=False, is_archived=False)
    elif tab == 'archived':
        query = query.filter_by(is_archived=True)
    else:
        query = query.filter_by(is_archived=False)

    pagination = query.order_by(BloodBankNotification.created_at.desc()).paginate(page=page, per_page=15, error_out=False)
    unread_count = BloodBankNotification.query.filter_by(blood_bank_id=account.blood_bank_id, is_read=False, is_archived=False).count()

    return render_template(
        'bloodbank/notifications.html',
        account=account,
        bank=bank,
        pagination=pagination,
        tab=tab,
        unread_count=unread_count
    )


@bloodbank_bp.route('/notifications/<int:id>/read', methods=['POST'])
@bloodbank_login_required
def mark_notification_read(id):
    from app.models import BloodBankNotification
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None
    notif = BloodBankNotification.query.filter_by(id=id, blood_bank_id=account.blood_bank_id).first_or_404()
    notif.is_read = True
    notif.read_at = datetime.now(timezone.utc)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return {'status': 'ok', 'id': notif.id}
    return redirect(request.referrer or url_for('bloodbank.notifications'))


@bloodbank_bp.route('/notifications/read-all', methods=['POST'])
@bloodbank_login_required
def mark_all_notifications_read():
    from app.models import BloodBankNotification
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None
    now_utc = datetime.now(timezone.utc)
    BloodBankNotification.query.filter_by(
        blood_bank_id=account.blood_bank_id,
        is_read=False
    ).update({'is_read': True, 'read_at': now_utc})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('bloodbank.notifications'))


@bloodbank_bp.route('/notifications/<int:id>/archive', methods=['POST'])
@bloodbank_login_required
def archive_notification(id):
    from app.models import BloodBankNotification
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None
    notif = BloodBankNotification.query.filter_by(id=id, blood_bank_id=account.blood_bank_id).first_or_404()
    notif.is_archived = True
    db.session.commit()
    flash('Notification archived.', 'info')
    return redirect(url_for('bloodbank.notifications'))


@bloodbank_bp.route('/api/notifications/poll')
@bloodbank_login_required
def poll_notifications():
    """Fallback polling endpoint for real-time alerts when Socket.IO is disconnected."""
    from app.models import BloodBankNotification
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None
    since_id = request.args.get('since_id', 0, type=int)

    query = BloodBankNotification.query.filter(
        BloodBankNotification.blood_bank_id == account.blood_bank_id,
        BloodBankNotification.is_read == False,
        BloodBankNotification.is_archived == False
    )
    if since_id > 0:
        query = query.filter(BloodBankNotification.id > since_id)

    new_notifs = query.order_by(BloodBankNotification.created_at.desc()).limit(10).all()
    unread_total = BloodBankNotification.query.filter_by(
        blood_bank_id=account.blood_bank_id,
        is_read=False,
        is_archived=False
    ).count()

    items = []
    for n in new_notifs:
        meta = {}
        if n.meta_json:
            try:
                meta = json.loads(n.meta_json)
            except Exception:
                pass
        items.append({
            'id': n.id,
            'type': n.notification_type,
            'title': n.title,
            'message': n.message,
            'priority': n.priority,
            'reservation_id': n.reservation_id,
            'blood_request_id': n.blood_request_id,
            'meta': meta,
            'created_at': n.created_at.isoformat() if n.created_at else ''
        })

    return {
        'status': 'ok',
        'unread_count': unread_total,
        'notifications': items
    }


# ── Alert Settings ──────────────────────────────────
@bloodbank_bp.route('/settings/alerts', methods=['GET', 'POST'])
@bloodbank_login_required
def alert_settings():
    from app.models import BloodBankAlertSettings
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    assert account is not None
    bank = account.blood_bank

    settings = BloodBankAlertSettings.query.filter_by(blood_bank_id=account.blood_bank_id).first()
    if not settings:
        settings = BloodBankAlertSettings(blood_bank_id=account.blood_bank_id)
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        settings.reservation_alerts_enabled = bool(request.form.get('reservation_alerts_enabled'))
        settings.nearby_request_alerts_enabled = bool(request.form.get('nearby_request_alerts_enabled'))
        settings.emergency_only = bool(request.form.get('emergency_only'))
        settings.alert_radius_km = max(int(request.form.get('alert_radius_km', 25) or 25), 1)
        selected_groups = request.form.getlist('blood_groups')
        settings.alert_blood_groups = ','.join(selected_groups)
        settings.sound_enabled = bool(request.form.get('sound_enabled'))
        settings.push_enabled = bool(request.form.get('push_enabled'))
        settings.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Alert notification preferences saved successfully.', 'success')
        return redirect(url_for('bloodbank.alert_settings'))

    all_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    current_groups = [g.strip() for g in settings.alert_blood_groups.split(',') if g.strip()] if settings.alert_blood_groups else []

    return render_template(
        'bloodbank/alert_settings.html',
        account=account,
        bank=bank,
        settings=settings,
        all_groups=all_groups,
        current_groups=current_groups
    )


