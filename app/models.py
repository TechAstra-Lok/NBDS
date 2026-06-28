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
    
    def __repr__(self):
        return f'<User {self.username} [{self.role}]>'


# ─────────────────────────────────────────────
# DONOR MODEL
# ─────────────────────────────────────────────
BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

class Donor(UserMixin, db.Model):
    __tablename__ = 'donors'
    
    id                      = db.Column(db.Integer, primary_key=True)
    donor_id                = db.Column(db.String(20), unique=True, nullable=False, index=True)
    full_name               = db.Column(db.String(150), nullable=False, index=True)
    email                   = db.Column(db.String(120), unique=True, nullable=False)
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
    donor_type              = db.Column(db.String(20), nullable=False)  # occasional|regular|emergency
    social_link             = db.Column(db.String(300))
    availability_status     = db.Column(db.String(30), default='available', index=True) # available | recently_donated | unavailable
    available_after         = db.Column(db.Date)
    
    # Auth & System
    is_email_verified       = db.Column(db.Boolean, default=False)
    is_phone_verified       = db.Column(db.Boolean, default=False)
    is_active               = db.Column(db.Boolean, default=True)
    created_at              = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at              = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
        return self.last_donation_date + timedelta(days=90)  # 90 days as per user rules
    
    def __repr__(self):
        return f'<Donor {self.donor_id}: {self.full_name} [{self.blood_group}]>'


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


# ─────────────────────────────────────────────
# STAFF MODEL
# ─────────────────────────────────────────────
class StaffMember(db.Model):
    __tablename__ = 'staff_members'
    
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


# ─────────────────────────────────────────────
# BLOOD REQUEST MODEL
# ─────────────────────────────────────────────
class BloodRequest(db.Model):
    __tablename__ = 'blood_requests'
    
    id              = db.Column(db.Integer, primary_key=True)
    request_id      = db.Column(db.String(20), unique=True, nullable=False, index=True)
    patient_name    = db.Column(db.String(150), nullable=False)
    request_message = db.Column(db.Text, nullable=False)
    case_details    = db.Column(db.String(255), nullable=False)
    blood_group     = db.Column(db.String(5), nullable=False, index=True)
    units_needed    = db.Column(db.Integer, default=1)
    
    # Location
    hospital        = db.Column(db.String(200), nullable=False)
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
    creator_id      = db.Column(db.Integer, db.ForeignKey('donors.id'), nullable=True) # Optional, if logged in
    
    # Tracking
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fulfilled_date  = db.Column(db.DateTime)
    
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


# ─────────────────────────────────────────────
# AUDIT LOG MODEL
# ─────────────────────────────────────────────
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.String(50), index=True) # E.g. "admin_1" or "donor_4"
    action      = db.Column(db.String(50), nullable=False) # Login, Delete, Edit, Create, Publish
    module      = db.Column(db.String(50)) # Model name or Route
    details     = db.Column(db.Text)
    ip_address  = db.Column(db.String(45))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)


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