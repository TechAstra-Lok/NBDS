from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import uuid


# ─────────────────────────────────────────────
# USER MODEL (ADMINS)
# ─────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id              = db.Column(db.Integer, primary_key=True)
    username        = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email           = db.Column(db.String(120), unique=True, nullable=False)
    full_name       = db.Column(db.String(150))
    password_hash   = db.Column(db.String(255), nullable=False)
    role            = db.Column(db.String(20), default='admin')  # superadmin | admin | moderator | content_manager
    is_active       = db.Column(db.Boolean, default=True)
    last_login      = db.Column(db.DateTime)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, username: str, email: str, full_name: str = '',
                 role: str = 'admin', is_active: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.username  = username
        self.email     = email
        self.full_name = full_name
        self.role      = role
        self.is_active = is_active
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_superadmin(self):
        return self.role == 'superadmin'
        
    def get_id(self):
        return f"user_{self.id}"
    
    def has_permission(self, permission):
        from app.rbac import has_permission as check_permission
        return check_permission(self, permission)

    def __repr__(self):
        return f'<User {self.username} [{self.role}]>'


# ─────────────────────────────────────────────
# BLOOD BANK MODEL
# ─────────────────────────────────────────────
class BloodBank(db.Model):
    __tablename__ = 'blood_banks'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False, index=True)
    display_name = db.Column(db.String(200))
    hospital_name = db.Column(db.String(200))
    parent_organization = db.Column(db.String(200))
    branch_type = db.Column(db.String(60), default='Hospital Blood Bank')
    service_type = db.Column(db.String(60), default='Hospital Blood Bank')
    province = db.Column(db.String(60), index=True)
    district = db.Column(db.String(80), index=True)
    city = db.Column(db.String(120))
    local_level = db.Column(db.String(120))
    ward = db.Column(db.String(20))
    tole = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    contact_number = db.Column(db.String(20))
    alternate_contact_number = db.Column(db.String(20))
    email = db.Column(db.String(120))
    website = db.Column(db.String(250))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    google_maps = db.Column(db.String(500))
    maps_url = db.Column(db.String(500))
    emergency_available = db.Column(db.Boolean, default=False)
    is_emergency_panel = db.Column(db.Boolean, default=False, index=True)
    is_grouped_entry = db.Column(db.Boolean, default=False, index=True)
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, index=True)
    status = db.Column(db.String(20), default='active', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Tenant Registry Fields
    tenant_id = db.Column(db.String(50), unique=True, index=True)
    db_name = db.Column(db.String(100), unique=True)
    schema_version = db.Column(db.String(50))
    tenant_status = db.Column(db.String(20), default='Provisioning') # Provisioning, Active, Suspended, Deprovisioned

    # Note: Tenant models (BloodInventory, etc.) are in separate databases, so we cannot use cross-db relationships.
    # We remove the relationships to BloodInventory, BloodReservation, BloodTransfer, LowStockAlert here.

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.uuid:
            self.uuid = str(uuid.uuid4())
        if not self.display_name and self.name:
            self.display_name = self.name


    @property
    def resolved_display_name(self):
        return self.display_name or self.name or self.hospital_name or 'Blood Bank'

    @property
    def is_operational(self):
        return bool(self.is_active and self.status == 'active')

    @property
    def google_maps_url(self):
        if self.maps_url:
            return self.maps_url
        if self.google_maps:
            return self.google_maps
        if self.latitude is not None and self.longitude is not None:
            return f'https://www.google.com/maps?q={self.latitude},{self.longitude}'
        return None

    def to_dict(self):
        return {
            'id': self.id,
            'uuid': self.uuid,
            'name': self.resolved_display_name,
            'province': self.province,
            'district': self.district,
            'city': self.city,
            'contact_number': self.contact_number or self.phone,
            'alternate_contact_number': self.alternate_contact_number,
            'email': self.email,
            'website': self.website,
            'service_type': self.service_type,
            'branch_type': self.branch_type,
            'emergency_available': self.emergency_available or self.is_emergency_panel,
            'is_emergency_panel': self.is_emergency_panel,
            'is_grouped_entry': self.is_grouped_entry,
            'status': self.status,
            'is_active': self.is_active,
            'maps_url': self.google_maps_url,
        }

    def __repr__(self):
        return f'<BloodBank {self.resolved_display_name}>'


# ─────────────────────────────────────────────
# BLOOD BANK ACCOUNTS & AUTH
# ─────────────────────────────────────────────
class BloodBankAccount(UserMixin, db.Model):
    __tablename__ = 'blood_bank_accounts'

    id = db.Column(db.Integer, primary_key=True)
    blood_bank_id = db.Column(db.Integer, db.ForeignKey('blood_banks.id'), nullable=False, index=True)
    login_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    temp_password = db.Column(db.String(100), nullable=True)
    
    password_change_required = db.Column(db.Boolean, default=True)
    account_status = db.Column(db.String(20), default='pending') # pending, active, suspended
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)
    password_changed_at = db.Column(db.DateTime)
    
    is_locked = db.Column(db.Boolean, default=False)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)

    blood_bank = db.relationship('BloodBank', backref=db.backref('account', uselist=False))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)


class BloodBankPasswordHistory(db.Model):
    __tablename__ = 'blood_bank_password_history'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('blood_bank_accounts.id'), nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    account = db.relationship('BloodBankAccount', backref=db.backref('password_history', lazy=True, cascade='all, delete-orphan'))


class BloodBankLoginHistory(db.Model):
    __tablename__ = 'blood_bank_login_history'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('blood_bank_accounts.id'), nullable=False, index=True)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    status = db.Column(db.String(20)) # success, failed, locked
    
    account = db.relationship('BloodBankAccount', backref=db.backref('login_history', lazy=True, cascade='all, delete-orphan'))


class PublicBloodBankCache(db.Model):
    __tablename__ = 'public_blood_bank_cache'
    
    id = db.Column(db.Integer, primary_key=True)
    blood_bank_id = db.Column(db.Integer, db.ForeignKey('blood_banks.id'), nullable=False, unique=True, index=True)
    
    # Pre-calculated aggregates of available units
    a_pos = db.Column(db.Integer, default=0)
    a_neg = db.Column(db.Integer, default=0)
    b_pos = db.Column(db.Integer, default=0)
    b_neg = db.Column(db.Integer, default=0)
    ab_pos = db.Column(db.Integer, default=0)
    ab_neg = db.Column(db.Integer, default=0)
    o_pos = db.Column(db.Integer, default=0)
    o_neg = db.Column(db.Integer, default=0)
    
    last_synced_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    blood_bank = db.relationship('BloodBank', backref=db.backref('inventory_cache', uselist=False))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class BloodInventory(db.Model):
    __tablename__ = 'blood_inventory'
    # __bind_key__ = 'tenant'

    id = db.Column(db.Integer, primary_key=True)
    blood_bank_id = db.Column(db.Integer, nullable=False, index=True) # Logical FK to Main DB BloodBank
    blood_group = db.Column(db.String(5), nullable=False, index=True)
    component = db.Column(db.String(50), nullable=False, default='Whole Blood')
    units_available = db.Column(db.Integer, default=0)
    units_reserved = db.Column(db.Integer, default=0)
    minimum_stock = db.Column(db.Integer, default=4)
    maximum_stock = db.Column(db.Integer, default=20)
    
    # Deprecated in Phase 3 (Moved to BloodBag)
    expiry_date = db.Column(db.String(20))
    qr_code = db.Column(db.String(80), unique=True, nullable=True, index=True)
    
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    movements = db.relationship('BloodInventoryMovement', backref='inventory', lazy=True, cascade='all, delete-orphan')

    @property
    def available_units(self):
        return max(self.units_available - self.units_reserved, 0)

    def to_dict(self):
        return {
            'id': self.id,
            'blood_group': self.blood_group,
            'component': self.component,
            'units_available': self.units_available,
            'units_reserved': self.units_reserved,
            'available_units': self.available_units,
            'minimum_stock': self.minimum_stock,
            'maximum_stock': self.maximum_stock,
            'expiry_date': self.expiry_date,
            'qr_code': self.qr_code,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class BloodInventoryMovement(db.Model):
    __tablename__ = 'blood_inventory_movements'
    # __bind_key__ = 'tenant'

    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('blood_inventory.id'), nullable=False, index=True)
    movement_type = db.Column(db.String(30), nullable=False, index=True)
    units = db.Column(db.Integer, default=0)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'movement_type': self.movement_type,
            'units': self.units,
            'note': self.note,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class BloodBag(db.Model):
    __tablename__ = 'blood_bags'
    # __bind_key__ = 'tenant'

    id = db.Column(db.Integer, primary_key=True)
    bag_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    blood_bank_id = db.Column(db.Integer, nullable=False, index=True) # Logical FK to Main DB BloodBank
    donor_id = db.Column(db.Integer, nullable=True, index=True) # Logical FK to Main DB Donor
    blood_group = db.Column(db.String(5), nullable=False, index=True)
    component = db.Column(db.String(50), nullable=False, default='Whole Blood')
    volume_ml = db.Column(db.Integer, nullable=True)
    collection_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True, index=True)
    status = db.Column(db.String(20), default='testing', index=True) # testing, available, reserved, transferred, discarded, used
    qr_code = db.Column(db.String(100), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Note: Donor is in Main DB, BloodBag is in Tenant DB. Cross-DB joins are not supported by SQLAlchemy.
    # We remove the donor db.relationship.
    lab_tests = db.relationship('LabTestResult', backref='blood_bag', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('BloodInventoryTransaction', backref='blood_bag', lazy=True, cascade='all, delete-orphan')


class LabTestResult(db.Model):
    __tablename__ = 'lab_test_results'
    # __bind_key__ = 'tenant'

    id = db.Column(db.Integer, primary_key=True)
    bag_id = db.Column(db.Integer, db.ForeignKey('blood_bags.id'), nullable=False, index=True)
    test_name = db.Column(db.String(100), nullable=False) # HIV, Hep B, Hep C, Syphilis, Malaria
    result = db.Column(db.String(20), default='pending') # positive, negative, pending
    tested_at = db.Column(db.DateTime, nullable=True)
    tested_by = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BloodInventoryTransaction(db.Model):
    __tablename__ = 'blood_inventory_transactions'
    # __bind_key__ = 'tenant'

    id = db.Column(db.Integer, primary_key=True)
    bag_id = db.Column(db.Integer, db.ForeignKey('blood_bags.id'), nullable=True, index=True)
    blood_bank_id = db.Column(db.Integer, nullable=False, index=True) # Logical FK to Main DB BloodBank
    transaction_type = db.Column(db.String(30), nullable=False, index=True) # collection, transfer_in, transfer_out, discard, issue
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class BloodReservation(db.Model):
    __tablename__ = 'blood_reservations'
    # __bind_key__ = 'tenant'

    id = db.Column(db.Integer, primary_key=True)
    blood_bank_id = db.Column(db.Integer, nullable=False, index=True) # Logical FK to Main DB BloodBank
    hospital_name = db.Column(db.String(200), nullable=False)
    patient_name = db.Column(db.String(150), nullable=False)
    blood_group = db.Column(db.String(5), nullable=False, index=True)
    component = db.Column(db.String(50), nullable=False, default='Whole Blood')
    units = db.Column(db.Integer, default=1)
    priority = db.Column(db.String(20), default='normal')
    status = db.Column(db.String(20), default='pending', index=True)
    hospital_paper_file = db.Column(db.String(255), nullable=True)
    qr_code = db.Column(db.String(80), unique=True, nullable=True, index=True)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'hospital_name': self.hospital_name,
            'patient_name': self.patient_name,
            'blood_group': self.blood_group,
            'component': self.component,
            'units': self.units,
            'priority': self.priority,
            'status': self.status,
            'qr_code': self.qr_code,
            'requested_at': self.requested_at.isoformat() if self.requested_at else None,
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class BloodTransfer(db.Model):
    __tablename__ = 'blood_transfers'
    # __bind_key__ = 'tenant'

    id = db.Column(db.Integer, primary_key=True)
    source_bank_id = db.Column(db.Integer, nullable=False, index=True)
    destination_bank_id = db.Column(db.Integer, nullable=False, index=True)
    blood_group = db.Column(db.String(5), nullable=False, index=True)
    component = db.Column(db.String(50), nullable=False, default='Whole Blood')
    units = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default='pending', index=True)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'source_bank_id': self.source_bank_id,
            'destination_bank_id': self.destination_bank_id,
            'blood_group': self.blood_group,
            'component': self.component,
            'units': self.units,
            'status': self.status,
            'remarks': self.remarks,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class LowStockAlert(db.Model):
    __tablename__ = 'low_stock_alerts'
    # __bind_key__ = 'tenant'

    id = db.Column(db.Integer, primary_key=True)
    blood_bank_id = db.Column(db.Integer, nullable=False, index=True)
    blood_group = db.Column(db.String(5), nullable=False, index=True)
    component = db.Column(db.String(50), nullable=False, default='Whole Blood')
    severity = db.Column(db.String(20), default='warning', index=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'blood_group': self.blood_group,
            'component': self.component,
            'severity': self.severity,
            'message': self.message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id'), nullable=True, index=True)
    blood_request_id = db.Column(db.Integer, nullable=True, index=True) # Logical FK to Tenant DB BloodRequest
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), default='general', index=True)
    channel = db.Column(db.String(20), default='in_app', index=True)
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    delivery_logs = db.relationship('NotificationDeliveryLog', backref='notification', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'donor_id': self.donor_id,
            'blood_request_id': self.blood_request_id,
            'title': self.title,
            'message': self.message,
            'category': self.category,
            'channel': self.channel,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class NotificationDeliveryLog(db.Model):
    __tablename__ = 'notification_delivery_logs'

    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer, db.ForeignKey('notifications.id'), nullable=False, index=True)
    channel = db.Column(db.String(20), nullable=False, index=True) # email, sms, in_app
    status = db.Column(db.String(20), default='pending', index=True) # pending, sent, failed
    error_message = db.Column(db.Text, nullable=True)
    attempt_count = db.Column(db.Integer, default=0)
    last_attempt_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Enterprise fields
    provider_name = db.Column(db.String(50), nullable=True)
    provider_response_id = db.Column(db.String(100), nullable=True)
    opened_at = db.Column(db.DateTime, nullable=True)
    clicked_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'notification_id': self.notification_id,
            'channel': self.channel,
            'status': self.status,
            'error_message': self.error_message,
            'attempt_count': self.attempt_count,
            'last_attempt_at': self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'provider_name': self.provider_name,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class DonorNotificationPreference(db.Model):
    __tablename__ = 'donor_notification_preferences'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id'), nullable=False, unique=True)
    email_alerts = db.Column(db.Boolean, default=True)
    sms_alerts = db.Column(db.Boolean, default=True)
    in_app_alerts = db.Column(db.Boolean, default=True)
    
    # Enterprise fields
    web_push_alerts = db.Column(db.Boolean, default=True)
    mobile_push_alerts = db.Column(db.Boolean, default=True)
    quiet_hours_start = db.Column(db.Time, nullable=True)
    quiet_hours_end = db.Column(db.Time, nullable=True)
    dnd_mode = db.Column(db.Boolean, default=False)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'donor_id': self.donor_id,
            'email_alerts': self.email_alerts,
            'sms_alerts': self.sms_alerts,
            'in_app_alerts': self.in_app_alerts,
            'web_push_alerts': self.web_push_alerts,
            'mobile_push_alerts': self.mobile_push_alerts,
            'dnd_mode': self.dnd_mode,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(80), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)
    details = db.Column(db.Text)
    actor = db.Column(db.String(100), default='system')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'action': self.action,
            'entity_id': self.entity_id,
            'details': self.details,
            'actor': self.actor,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# ─────────────────────────────────────────────
# DONOR MODEL
# ─────────────────────────────────────────────
BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

class Donor(UserMixin, db.Model):
    __tablename__ = 'donors'
    __table_args__ = (
        db.Index('idx_donor_search', 'curr_district', 'blood_group', 'availability_status'),
    )
    
    id                      = db.Column(db.Integer, primary_key=True)
    donor_id                = db.Column(db.String(20), unique=True, nullable=False, index=True)
    full_name               = db.Column(db.String(150), nullable=False, index=True)
    email                   = db.Column(db.String(120), unique=True, nullable=True)
    phone1                  = db.Column(db.String(15), unique=True, nullable=False, index=True)
    phone2                  = db.Column(db.String(15))
    pin_hash                = db.Column(db.String(255), nullable=False)
    
    age                     = db.Column(db.Integer, nullable=False)
    weight                  = db.Column(db.Float)
    
    # Permanent Address
    perm_province           = db.Column(db.String(60))
    perm_district           = db.Column(db.String(80))
    perm_local_level        = db.Column(db.String(100))
    perm_ward               = db.Column(db.String(10))
    perm_tole               = db.Column(db.String(100))
    
    # Current Address
    curr_province           = db.Column(db.String(60), nullable=False)
    curr_district           = db.Column(db.String(80), nullable=False, index=True)
    curr_local_level        = db.Column(db.String(100), nullable=False)
    curr_ward               = db.Column(db.String(10))
    curr_tole               = db.Column(db.String(100))
    
    # Blood Info
    blood_group             = db.Column(db.String(5), nullable=False, index=True)
    last_donation_date      = db.Column(db.Date)
    donation_times          = db.Column(db.Integer, default=0)
    
    # Donor Meta
    donor_type              = db.Column(db.String(30), nullable=False)  # regular|emergency|platelet|rare|volunteer|other
    social_link             = db.Column(db.String(300))
    availability_status     = db.Column(db.String(30), default='available', index=True) # available | recently_donated | unavailable
    available_after         = db.Column(db.Date)
    
    # Optional Profile Metadata
    gender                  = db.Column(db.String(20))  # male|female|other|prefer_not_to_say
    emergency_contact       = db.Column(db.String(15))  # emergency contact phone
    donor_notes             = db.Column(db.Text)  # admin or self notes
    is_public               = db.Column(db.Boolean, default=True)  # profile visibility toggle
    
    # Donation Summary Fields (kept for fast filtering, updated by engine)
    total_donations         = db.Column(db.Integer, default=0)
    available_after_date    = db.Column(db.Date)  # computed: 90th day from last donation
    last_status_recalculated_at = db.Column(db.DateTime)
    
    # Auth & System
    is_email_verified       = db.Column(db.Boolean, default=False)
    is_phone_verified       = db.Column(db.Boolean, default=False)
    is_active               = db.Column(db.Boolean, default=True)
    created_at              = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at              = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    donation_history        = db.relationship('DonorDonationHistory', backref='donor', lazy=True, cascade='all, delete-orphan')
    notifications           = db.relationship('Notification', backref='donor', lazy=True, cascade='all, delete-orphan')
    preference              = db.relationship('DonorNotificationPreference', backref='donor', uselist=False, lazy=True, cascade='all, delete-orphan')

    
    # ── Configurable Availability Thresholds ──
    RECENT_DAYS     = 30   # 0-29 days => Recently Donated
    UNAVAILABLE_DAYS = 90  # 30-89 days => Unavailable; 90+ => Available
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.donor_id:
            self.donor_id = self._generate_donor_id()
    
    @staticmethod
    def _generate_donor_id():
        uid = uuid.uuid4().hex[:6].upper()
        return f"NBD-{uid}"
        
    def set_pin(self, pin):
        self.pin_hash = generate_password_hash(str(pin))
        
    def check_pin(self, pin):
        return check_password_hash(self.pin_hash, str(pin))
        
    def get_id(self):
        return f"donor_{self.id}"
    
    @property
    def next_eligible_date(self):
        if not self.last_donation_date:
            return None
        return self.last_donation_date + timedelta(days=self.UNAVAILABLE_DAYS)
    
    def calculate_availability(self):
        """
        Compute donor availability based on last_donation_date.
        Returns (status_string, available_after_date_or_None).
        
        Logic:
          < 90 days  => 'recently_donated'
          >= 90 days => 'available'
          No date    => 'available'
        """
        if not self.last_donation_date:
            return ('available', None)
        
        today = datetime.utcnow().date()
        days_since = (today - self.last_donation_date).days
        eligible_date = self.last_donation_date + timedelta(days=self.UNAVAILABLE_DAYS)
        
        if days_since < self.UNAVAILABLE_DAYS:
            return ('recently_donated', eligible_date)
        else:
            return ('available', None)
    
    def to_dict(self):
        import nepali_datetime
        
        def format_bs(dt):
            if not dt: return None
            try:
                if isinstance(dt, datetime): dt = dt.date()
                bs = nepali_datetime.date.from_datetime_date(dt)
                return bs.strftime('%Y-%m-%d')
            except:
                return dt.strftime('%Y-%m-%d')

        return {
            'id': self.id,
            'donor_id': self.donor_id,
            'full_name': self.full_name,
            'blood_group': self.blood_group,
            'age': self.age,
            'weight': self.weight,
            'curr_district': self.curr_district,
            'curr_local_level': self.curr_local_level,
            'availability_status': self.availability_status,
            'available_after_date': format_bs(self.available_after_date),
            'last_donation_date': format_bs(self.last_donation_date),
            'availability_display': self.availability_display,
            'created_at': self.created_at.strftime('%Y-%m-%dT%H:%M:%S') if self.created_at else None,
        }

    def recalculate_and_save(self):
        """Recalculate availability and update summary fields in-place."""
        status, after_date = self.calculate_availability()
        self.availability_status = status
        self.available_after_date = after_date
        # Also sync the legacy field
        self.available_after = after_date
        self.last_status_recalculated_at = datetime.utcnow()
    
    @property
    def availability_display(self):
        """Human-readable availability status text."""
        import nepali_datetime
        
        def format_bs(dt):
            if not dt: return ""
            try:
                if isinstance(dt, datetime): dt = dt.date()
                bs = nepali_datetime.date.from_datetime_date(dt)
                return bs.strftime('%Y-%m-%d')
            except:
                return dt.strftime('%Y-%m-%d')

        if self.availability_status == 'available':
            return 'Available to donate'
        elif self.availability_status == 'recently_donated':
            if self.available_after_date:
                return f'Recently Donated (Eligible after {format_bs(self.available_after_date)})'
            return 'Recently Donated'
        elif self.availability_status == 'unavailable':
            if self.available_after_date:
                return f'Eligible after {format_bs(self.available_after_date)}'
            return 'Currently Unavailable'
        return 'Unknown'
    
    @property
    def availability_badge_class(self):
        """Bootstrap badge class for status display."""
        return {
            'available': 'bg-success',
            'recently_donated': 'bg-warning text-dark',
            'unavailable': 'bg-danger',
        }.get(self.availability_status, 'bg-secondary')
    
    def __repr__(self):
        return f'<Donor {self.donor_id}: {self.full_name} [{self.blood_group}] status={self.availability_status}>'


# ─────────────────────────────────────────────
# DONOR DONATION HISTORY MODEL
# ─────────────────────────────────────────────
class DonorDonationHistory(db.Model):
    __tablename__ = 'donor_donation_history'
    __table_args__ = (
        db.Index('idx_donation_history_donor', 'donor_id', 'donation_date'),
    )
    
    id              = db.Column(db.Integer, primary_key=True)
    donor_id        = db.Column(db.Integer, db.ForeignKey('donors.id'), nullable=False, index=True)
    donation_date   = db.Column(db.Date, nullable=False)
    donation_type   = db.Column(db.String(30), default='whole_blood')  # whole_blood|platelet|plasma|sdp|other
    location        = db.Column(db.String(200))  # hospital/blood bank name
    units           = db.Column(db.Float, default=1.0)
    notes           = db.Column(db.Text)
    created_by      = db.Column(db.String(50), default='donor')  # 'donor' or 'admin_<id>'
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    DONATION_TYPE_LABELS = {
        'whole_blood': 'Whole Blood',
        'platelet': 'Platelet (SDP)',
        'plasma': 'Plasma',
        'sdp': 'Single Donor Platelet',
        'other': 'Other',
    }
    
    @property
    def donation_type_label(self):
        return self.DONATION_TYPE_LABELS.get(self.donation_type, self.donation_type or 'Whole Blood')
    
    def to_dict(self):
        return {
            'id': self.id,
            'donor_id': self.donor_id,
            'donation_date': self.donation_date.isoformat() if self.donation_date else None,
            'donation_type': self.donation_type,
            'donation_type_label': self.donation_type_label,
            'location': self.location,
            'units': self.units,
            'notes': self.notes,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    def __repr__(self):
        return f'<DonorDonationHistory donor={self.donor_id} date={self.donation_date} type={self.donation_type}>'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# ─────────────────────────────────────────────
# VOLUNTEER MODEL (DOCTORS & NURSES)
# ─────────────────────────────────────────────
class Volunteer(UserMixin, db.Model):
    __tablename__ = 'volunteers'
    
    id                      = db.Column(db.Integer, primary_key=True)
    full_name               = db.Column(db.String(150), nullable=False, index=True)
    designation             = db.Column(db.String(50), nullable=False) # doctor | nurse | HA
    working_field           = db.Column(db.String(100)) # artho, neuro, gyno, GM, etc.
    email                   = db.Column(db.String(120), unique=True, nullable=False)
    phone1                  = db.Column(db.String(15), unique=True, nullable=False, index=True)
    phone2                  = db.Column(db.String(15))
    pin_hash                = db.Column(db.String(255), nullable=False)
    
    # Addresses
    perm_address            = db.Column(db.String(200))
    curr_address            = db.Column(db.String(200))
    curr_district           = db.Column(db.String(80), index=True) # Useful for filtering
    
    availability_time       = db.Column(db.String(150))
    
    # Status
    is_approved             = db.Column(db.Boolean, default=False, index=True)
    is_active               = db.Column(db.Boolean, default=True)
    created_at              = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_pin(self, pin):
        self.pin_hash = generate_password_hash(str(pin))
        
    def check_pin(self, pin):
        return check_password_hash(self.pin_hash, str(pin))
        
    def get_id(self):
        return f"volunteer_{self.id}"
        
    def __repr__(self):
        return f'<Volunteer {self.full_name} [{self.designation}]>'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# ─────────────────────────────────────────────
# STAFF MODEL
# ─────────────────────────────────────────────
class StaffMember(db.Model):
    __tablename__ = 'staff_members'
    # __bind_key__ = 'tenant'
    
    id              = db.Column(db.Integer, primary_key=True)
    full_name       = db.Column(db.String(150), nullable=False)
    designation     = db.Column(db.String(100), nullable=False)
    email           = db.Column(db.String(120))
    contact_number  = db.Column(db.String(20))
    profile_photo   = db.Column(db.String(255))
    
    # Address
    province        = db.Column(db.String(60))
    district        = db.Column(db.String(80))
    local_level     = db.Column(db.String(100))
    ward_number     = db.Column(db.String(10))
    tole            = db.Column(db.String(100))
    
    is_active       = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def image_url(self):
        if self.profile_photo:
            return f"/static/uploads/staff/{self.profile_photo}"
        return "/static/images/default-avatar.jpg"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# ─────────────────────────────────────────────
# PARTNER MODEL
# ─────────────────────────────────────────────
class Partner(db.Model):
    __tablename__ = 'partners'
    
    id              = db.Column(db.Integer, primary_key=True)
    partner_name    = db.Column(db.String(200), nullable=False)
    description     = db.Column(db.Text)
    website_url     = db.Column(db.String(300))
    email           = db.Column(db.String(120))
    contact_number  = db.Column(db.String(20))
    address         = db.Column(db.String(255))
    logo_file       = db.Column(db.String(255))
    
    is_active       = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def image_url(self):
        if self.logo_file:
            return f"/static/uploads/partners/{self.logo_file}"
        return "/static/images/default-partner.png"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# ─────────────────────────────────────────────
# BLOOD REQUEST MODEL
# ─────────────────────────────────────────────
class BloodRequest(db.Model):
    __tablename__ = 'blood_requests'
    
    id              = db.Column(db.Integer, primary_key=True)
    request_id      = db.Column(db.String(20), unique=True, nullable=False, index=True)
    patient_name    = db.Column(db.String(150), nullable=False)
    request_message = db.Column(db.Text, nullable=True)
    case_details    = db.Column(db.String(255), nullable=False)
    blood_group     = db.Column(db.String(5), nullable=False, index=True)
    required_component = db.Column(db.String(100), default='Whole Blood', nullable=True)
    units_needed    = db.Column(db.Integer, default=1)
    
    # Location
    hospital        = db.Column(db.String(200), nullable=False)
    hospital_paper_file = db.Column(db.String(255), nullable=True)
    hospital_paper_verified = db.Column(db.Boolean, default=None, nullable=True)
    province        = db.Column(db.String(60))
    district        = db.Column(db.String(80), index=True)
    local_level     = db.Column(db.String(100))
    ward_no         = db.Column(db.String(10))
    
    contact_person  = db.Column(db.String(150), nullable=False)
    contact_number  = db.Column(db.String(15), nullable=False)
    alt_number      = db.Column(db.String(15))
    
    status          = db.Column(db.String(30), default='active', index=True)  # active|fulfilled|cancelled|managed_from_other_source
    is_emergency    = db.Column(db.Boolean, default=False)
    
    # Ownership
    creator_id      = db.Column(db.Integer, nullable=True) # Logical FK to Main DB Donor (Optional, if logged in)
    
    # Tracking
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fulfilled_date  = db.Column(db.DateTime)
    
    pin             = db.Column(db.String(4), nullable=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.request_id:
            ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            self.request_id = f"REQ-{ts}"
    
    @property
    def status_badge(self):
        badges = {
            'active': 'danger',
            'fulfilled': 'success',
            'cancelled': 'dark',
            'managed_from_other_source': 'info'
        }
        return badges.get(self.status, 'secondary')

    @property
    def component_display(self):
        try:
            return getattr(self, 'required_component', None) or 'Whole Blood'
        except Exception:
            return 'Whole Blood'

    @property
    def hospital_paper_url(self):
        try:
            if not getattr(self, 'hospital_paper_file', None):
                return None
            fn = str(self.hospital_paper_file).replace('\\', '/').strip('/')
            if fn.startswith('http://') or fn.startswith('https://'):
                return fn
            if fn.startswith('static/'):
                return f"/{fn}"
            if fn.startswith('uploads/'):
                return f"/static/{fn}"
            return f"/static/uploads/request_papers/{fn}"
        except Exception:
            return None

    @property
    def formatted_share_text(self):
        comp = self.component_display
        msg = f' ("{self.request_message.strip()}")' if getattr(self, 'request_message', None) else ''
        loc = f"{self.hospital}"
        if self.district:
            loc += f", {self.district}"
        contacts = f"{self.contact_number}"
        if self.alt_number:
            contacts += f" / {self.alt_number}"
        
        return (
            f"🩸 URGENT BLOOD REQUEST 🩸\n"
            f"────────────────────────────\n"
            f"🆔 Request ID: {self.request_id}\n"
            f"🅰️ Blood Group: {self.blood_group}\n"
            f"🧪 Required Type/Component: {comp}\n"
            f"🩸 Quantity Needed: {self.units_needed} Unit(s)\n"
            f"👤 Patient Name: {self.patient_name}\n"
            f"🏥 Hospital / Location: {loc}\n"
            f"📞 Contact Person: {self.contact_person}\n"
            f"📱 Contact Phone: {contacts}\n"
            f"📋 Case / Reason: {self.case_details}{msg}\n"
            f"────────────────────────────\n"
            f"📌 Source: Raktadata Blood Request System Nepal\n"
            f"🔗 Direct Link: https://raktadata.lokeshprasai.com.np/blood-requests/{self.request_id}"
        )
    
    def to_dict(self):
        return {
            'id': self.id,
            'request_id': self.request_id,
            'patient_name': self.patient_name,
            'blood_group': self.blood_group,
            'required_component': self.required_component or 'Whole Blood',
            'units_needed': self.units_needed,
            'hospital': self.hospital,
            'district': self.district,
            'local_level': self.local_level,
            'is_emergency': self.is_emergency,
            'status': self.status,
            'hospital_paper_url': self.hospital_paper_url,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<BloodRequest {self.request_id}: {self.blood_group}>'


# ─────────────────────────────────────────────
# SUCCESS STORIES MODEL
# ─────────────────────────────────────────────
class SuccessStory(db.Model):
    __tablename__ = 'success_stories'
    
    id              = db.Column(db.Integer, primary_key=True)
    title           = db.Column(db.String(200), nullable=False)
    content         = db.Column(db.Text, nullable=False)
    author_name     = db.Column(db.String(100), nullable=False)
    district        = db.Column(db.String(80))
    blood_group     = db.Column(db.String(5))
    
    image_file      = db.Column(db.String(255), nullable=True)
    video_url       = db.Column(db.String(500), nullable=True)
    social_link     = db.Column(db.String(500), nullable=False)
    
    status          = db.Column(db.String(20), default='pending', index=True) # pending | approved | rejected | hidden
    moderation_logs = db.Column(db.Text) # AI Moderation issues JSON string
    
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def image_url(self):
        if self.image_file:
            if self.image_file.startswith('http://') or self.image_file.startswith('https://'):
                return self.image_file
            clean_filename = self.image_file.replace('static/', '').replace('uploads/stories/', '').lstrip('/')
            return f"/static/uploads/stories/{clean_filename}"
        return None


# ─────────────────────────────────────────────
# NEWS MODEL
# ─────────────────────────────────────────────
class News(db.Model):
    __tablename__ = 'news'
    
    id              = db.Column(db.Integer, primary_key=True)
    title           = db.Column(db.String(300), nullable=False)
    slug            = db.Column(db.String(350), unique=True, index=True)
    short_desc      = db.Column(db.String(500))
    content         = db.Column(db.Text, nullable=False)
    featured_image  = db.Column(db.String(255))
    category        = db.Column(db.String(30), default='news', index=True)
    author          = db.Column(db.String(100))
    tags            = db.Column(db.String(300))
    
    is_published    = db.Column(db.Boolean, default=True, index=True)
    scheduled_date  = db.Column(db.DateTime, default=datetime.utcnow) # For scheduled publication
    views           = db.Column(db.Integer, default=0)
    
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.slug and self.title:
            self.slug = self._make_slug(self.title)
    
    @staticmethod
    def _make_slug(title):
        import re
        slug = title.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_-]+', '-', slug)
        slug = slug[:100]
        uid = uuid.uuid4().hex[:6]
        return f"{slug}-{uid}"
        
    @property
    def image_url(self):
        if self.featured_image:
            return f"/static/uploads/news/{self.featured_image}"
        return "/static/images/news-placeholder.jpg"


# ─────────────────────────────────────────────
# NOTICE MODEL
# ─────────────────────────────────────────────
class Notice(db.Model):
    __tablename__ = 'notices'
    
    id              = db.Column(db.Integer, primary_key=True)
    title           = db.Column(db.String(300), nullable=False)
    content         = db.Column(db.Text, nullable=False)
    attachment      = db.Column(db.String(255))
    attachment_type = db.Column(db.String(10))
    
    published_date  = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expiry_date     = db.Column(db.DateTime)
    is_active       = db.Column(db.Boolean, default=True, index=True)
    priority        = db.Column(db.Integer, default=0)
    
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def days_left(self):
        """
        Calculates remaining days before expiry.
        Returns None if no expiry_date is set, or integer count of days remaining.
        """
        if not self.expiry_date:
            return None
        
        now = datetime.utcnow()
        if self.expiry_date < now:
            return 0
            
        delta = self.expiry_date - now
        return delta.days


# ─────────────────────────────────────────────
# ADVERTISEMENT MODEL
# ─────────────────────────────────────────────
class Advertisement(db.Model):
    __tablename__ = 'advertisements'
    
    id              = db.Column(db.Integer, primary_key=True)
    title           = db.Column(db.String(200), nullable=False)
    description     = db.Column(db.Text)
    image           = db.Column(db.String(255), nullable=False)
    redirect_url    = db.Column(db.String(500))
    ad_type         = db.Column(db.String(20), default='sidebar', index=True)  # sidebar|banner|footer
    
    start_date      = db.Column(db.DateTime, default=datetime.utcnow)
    end_date        = db.Column(db.DateTime)
    clicks          = db.Column(db.Integer, default=0)
    impressions     = db.Column(db.Integer, default=0)
    is_active       = db.Column(db.Boolean, default=True, index=True)
    
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# ─────────────────────────────────────────────
# SITE VISITOR MODEL
# ─────────────────────────────────────────────
class SiteVisitor(db.Model):
    __tablename__ = 'site_visitors'
    
    id          = db.Column(db.Integer, primary_key=True)
    ip_address  = db.Column(db.String(45), nullable=False, index=True)
    visit_date  = db.Column(db.Date, nullable=False, index=True)
    user_agent  = db.Column(db.String(255))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('ip_address', 'visit_date', name='unique_daily_visitor'),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# ─────────────────────────────────────────────
# CONTACT MODEL
# ─────────────────────────────────────────────
class Contact(db.Model):
    __tablename__ = 'contacts'
    
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(150), nullable=False)
    email       = db.Column(db.String(120), nullable=False)
    phone       = db.Column(db.String(15))
    subject     = db.Column(db.String(255), nullable=False)
    message     = db.Column(db.Text, nullable=False)
    is_read     = db.Column(db.Boolean, default=False, index=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id'), nullable=False, index=True)
    platform = db.Column(db.String(20), nullable=False) # 'web', 'android', 'ios'
    token = db.Column(db.Text, nullable=False, unique=True)
    auth_key = db.Column(db.String(255), nullable=True) # For Web Push (VAPID)
    p256dh_key = db.Column(db.String(255), nullable=True) # For Web Push (VAPID)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class NotificationQueue(db.Model):
    __tablename__ = 'notification_queue'

    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer, db.ForeignKey('notifications.id'), nullable=False, index=True)
    channel = db.Column(db.String(20), nullable=False)
    payload = db.Column(db.Text, nullable=True) # JSON payload string
    priority = db.Column(db.Integer, default=3) # 1=Emergency, 2=High, 3=Standard
    status = db.Column(db.String(20), default='queued', index=True) # queued, processing, completed, failed, dlq
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    next_attempt_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_log = db.Column(db.Text, nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class DonorResponse(db.Model):
    __tablename__ = 'donor_responses'

    id = db.Column(db.Integer, primary_key=True)
    blood_request_id = db.Column(db.String(50), nullable=False, index=True) # Logical FK to Tenant DB BloodRequest
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id'), nullable=False, index=True)
    response_type = db.Column(db.String(20), nullable=False) # 'available', 'maybe', 'unavailable', 'already_donated'
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
