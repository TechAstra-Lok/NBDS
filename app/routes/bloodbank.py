"""
Blood Bank Authentication Blueprint
Handles login, logout, password change, and first-login flows for blood bank accounts.
Isolated from the admin authentication system.
"""
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session
)
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import BloodBankAccount, BloodBankLoginHistory, BloodBankPasswordHistory
from app.services.auth_service import AuthService
from datetime import datetime, timedelta
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
        # If accessing the dashboard/authenticated routes, resolve the tenant DB
        if not account.blood_bank or not account.blood_bank.tenant_id:
            flash("Your blood bank has not been fully provisioned yet.", "danger")
            return redirect(url_for('bloodbank.login'))
            
        try:
            from app.services.tenant_service import TenantResolutionService
            TenantResolutionService.resolve_tenant(account.blood_bank.tenant_id)
        except Exception as e:
            flash(f"Tenant error: {str(e)}", "danger")
            return redirect(url_for('bloodbank.login'))
            
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

        account = BloodBankAccount.query.filter_by(login_id=login_id).first()

        # Record login attempt
        def record_login(acct, status):
            entry = BloodBankLoginHistory(
                # pyrefly: ignore [unexpected-keyword]
                account_id=acct.id,
                # pyrefly: ignore [unexpected-keyword]
                login_time=datetime.utcnow(),
                # pyrefly: ignore [unexpected-keyword]
                ip_address=request.remote_addr,
                # pyrefly: ignore [unexpected-keyword]
                user_agent=request.headers.get('User-Agent', '')[:255],
                # pyrefly: ignore [unexpected-keyword]
                status=status
            )
            db.session.add(entry)

        if not account:
            flash('Invalid login ID or password.', 'danger')
            return render_template('bloodbank/login.html')

        # Check lock status
        if account.is_locked:
            if account.locked_until and datetime.utcnow() > account.locked_until:
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
                account.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
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
        account.last_login_at = datetime.utcnow()
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
        account.password_changed_at = datetime.utcnow()

        history = BloodBankPasswordHistory(
            # pyrefly: ignore [unexpected-keyword]
            account_id=account.id,
            # pyrefly: ignore [unexpected-keyword]
            password_hash=account.password_hash,
            # pyrefly: ignore [unexpected-keyword]
            created_at=datetime.utcnow()
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
    from app.models import BloodReservation, BloodInventory
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    
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
    from app.models import BloodReservation, BloodInventory
    from app.services.inventory_service import InventoryService
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    
    reservation = BloodReservation.query.filter_by(id=id, blood_bank_id=account.blood_bank_id).first_or_404()
    new_status = request.form.get('status')
    
    if new_status not in ['approved', 'cancelled', 'fulfilled']:
        flash('Invalid status.', 'danger')
        return redirect(url_for('bloodbank.reservations'))
        
    if reservation.status == new_status:
        flash('Reservation is already in that status.', 'info')
        return redirect(url_for('bloodbank.reservations'))
        
    # Logic for inventory update if approved or cancelled after approval
    inventory = BloodInventory.query.filter_by(blood_bank_id=account.blood_bank_id, blood_group=reservation.blood_group, component=reservation.component).first()
    
    if new_status == 'approved' and reservation.status == 'pending':
        if not inventory or inventory.units_available < reservation.units:
            flash(f'Not enough available units of {reservation.blood_group} {reservation.component} to approve.', 'danger')
            return redirect(url_for('bloodbank.reservations'))
        
        # Reserve the units
        inventory.units_available -= reservation.units
        inventory.units_reserved += reservation.units
        
    elif new_status == 'cancelled' and reservation.status == 'approved':
        if inventory:
            # Free up the reserved units
            inventory.units_reserved = max(0, inventory.units_reserved - reservation.units)
            inventory.units_available += reservation.units
            
    elif new_status == 'fulfilled' and reservation.status == 'approved':
        if inventory:
            # Consume the reserved units
            inventory.units_reserved = max(0, inventory.units_reserved - reservation.units)
            # Log the movement? The user can do that manually, or we can just decrement. Since we're keeping it simple for now, we just drop the reserved units.
            
    reservation.status = new_status
    db.session.commit()
    
    # Sync public cache if inventory changed
    if new_status in ['approved', 'cancelled', 'fulfilled'] and inventory:
        InventoryService.sync_public_cache(account.blood_bank_id)
        
    flash(f'Reservation #{reservation.id} status updated to {new_status}.', 'success')
    return redirect(url_for('bloodbank.reservations'))


# ── Staff Management ─────────────────────────────────────
@bloodbank_bp.route('/staff')
@bloodbank_login_required
def staff():
    from app.models import StaffMember
    from app.utils import paginate_query
    page = request.args.get('page', 1, type=int)
    pagination = paginate_query(
        StaffMember.query.order_by(StaffMember.created_at.desc()), page, 15
    )
    return render_template('bloodbank/staff.html', pagination=pagination)


@bloodbank_bp.route('/staff/add', methods=['GET', 'POST'])
@bloodbank_login_required
def add_staff():
    from app.models import StaffMember
    from app.forms import StaffMemberForm
    from app.utils import save_image
    
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
        flash('Staff member added successfully!', 'success')
        return redirect(url_for('bloodbank.staff'))
    
    return render_template('bloodbank/staff_form.html', form=form, action='Add')


@bloodbank_bp.route('/staff/<int:id>/edit', methods=['GET', 'POST'])
@bloodbank_login_required
def edit_staff(id):
    from app.models import StaffMember
    from app.forms import StaffMemberForm
    from app.utils import save_image, delete_file

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
        flash('Staff member updated successfully!', 'success')
        return redirect(url_for('bloodbank.staff'))
        
    return render_template('bloodbank/staff_form.html', form=form, member=member, action='Edit')


@bloodbank_bp.route('/staff/<int:id>/delete', methods=['POST'])
@bloodbank_login_required
def delete_staff(id):
    from app.models import StaffMember
    from app.utils import delete_file

    member = StaffMember.query.get_or_404(id)
    
    if member.profile_photo:
        delete_file(member.profile_photo, 'staff')
        
    db.session.delete(member)
    db.session.commit()
    
    flash(f'Staff member "{member.full_name}" has been removed.', 'success')
    return redirect(url_for('bloodbank.staff'))


# ── Dashboard ─────────────────────────────────────
@bloodbank_bp.route('/dashboard')
@bloodbank_login_required
def dashboard():
    from app.models import BloodInventory, StaffMember, BloodReservation, BloodTransfer
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    # Force password change if still required
    if account.password_change_required:
        return redirect(url_for('bloodbank.change_password'))
        
    inventory_items = BloodInventory.query.filter_by(blood_bank_id=account.blood_bank_id).all()
    # Dashboard detailed stats
    staff_count = StaffMember.query.count()
    reservations_count = BloodReservation.query.filter_by(blood_bank_id=account.blood_bank_id, status='pending').count()
    transfers_count = BloodTransfer.query.filter_by(source_bank_id=account.blood_bank_id, status='pending').count()
    
    return render_template('bloodbank/dashboard.html', 
                           account=account, 
                           bank=account.blood_bank, 
                           inventory_items=inventory_items,
                           staff_count=staff_count,
                           reservations_count=reservations_count,
                           transfers_count=transfers_count)


# ── Inventory Management ──────────────────────────
@bloodbank_bp.route('/inventory')
@bloodbank_login_required
def inventory():
    from app.models import BloodInventory
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])
    items = BloodInventory.query.filter_by(blood_bank_id=account.blood_bank_id).order_by(BloodInventory.blood_group).all()
    return render_template('bloodbank/inventory.html', account=account, bank=account.blood_bank, items=items)


@bloodbank_bp.route('/inventory/add', methods=['GET', 'POST'])
@bloodbank_login_required
def add_inventory():
    from app.models import BloodInventory, BloodInventoryMovement
    account = BloodBankAccount.query.get(session['bloodbank_account_id'])

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
            last_updated=datetime.utcnow()
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
                created_at=datetime.utcnow()
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
                created_at=datetime.utcnow()
            )
            db.session.add(movement)

        item.units_available = new_units
        item.minimum_stock = minimum_stock
        item.maximum_stock = maximum_stock
        item.last_updated = datetime.utcnow()
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

