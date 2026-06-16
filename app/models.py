from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import uuid


# ─────────────────────────────────────────────
# USER MODEL
# ─────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id              = db.Column(db.Integer, primary_key=True)
    username        = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email           = db.Column(db.String(120), unique=True, nullable=False)
    full_name       = db.Column(db.String(150))
    password_hash   = db.Column(db.String(255), nullable=False)
    role            = db.Column(db.String(20), default='admin')  # superadmin | admin
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
    
    def __repr__(self):
        return f'<User {self.username} [{self.role}]>'


# ─────────────────────────────────────────────
# DONOR MODEL
# ─────────────────────────────────────────────
BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
PROVINCES_NP = [
    'Koshi Pradesh', 'Madhesh Pradesh', 'Bagmati Pradesh',
    'Gandaki Pradesh', 'Lumbini Pradesh', 'Karnali Pradesh', 'Sudurpashchim Pradesh'
]

class Donor(db.Model):
    __tablename__ = 'donors'
    
    id                      = db.Column(db.Integer, primary_key=True)
    donor_id                = db.Column(db.String(20), unique=True, nullable=False, index=True)
    full_name               = db.Column(db.String(150), nullable=False, index=True)
    age                     = db.Column(db.Integer, nullable=False)
    weight                  = db.Column(db.Float)
    
    # Permanent Address
    perm_province           = db.Column(db.String(60))
    perm_district           = db.Column(db.String(80))
    perm_city               = db.Column(db.String(100))
    perm_local_level        = db.Column(db.String(100))
    
    # Current Address
    curr_province           = db.Column(db.String(60), nullable=False)
    curr_district           = db.Column(db.String(80), nullable=False, index=True)
    curr_city               = db.Column(db.String(100), nullable=False, index=True)
    curr_local_level        = db.Column(db.String(100))
    
    # Contact
    phone1                  = db.Column(db.String(15), nullable=False, index=True)
    phone2                  = db.Column(db.String(15))
    
    # Blood Info
    blood_group             = db.Column(db.String(5), nullable=False, index=True)
    last_donation_date      = db.Column(db.Date)
    donation_times          = db.Column(db.Integer, default=0)
    
    # Donor Meta
    donor_type              = db.Column(db.String(20), nullable=False)  # occasional|regular|emergency
    social_link             = db.Column(db.String(300))
    availability_status     = db.Column(db.String(15), default='available', index=True)
    
    # Timestamps
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
    
    @property
    def next_eligible_date(self):
        if not self.last_donation_date:
            return None
        return self.last_donation_date + timedelta(days=112)  # 16 weeks
    
    @property
    def can_donate_now(self):
        if not self.last_donation_date:
            return True
        return datetime.utcnow().date() >= self.next_eligible_date
    
    @property
    def curr_full_address(self):
        parts = [self.curr_city, self.curr_district, self.curr_province]
        return ', '.join(filter(None, parts))
    
    @property
    def perm_full_address(self):
        parts = [self.perm_city, self.perm_district, self.perm_province]
        return ', '.join(filter(None, parts))
    
    def to_dict(self):
        return {
            'id': self.id,
            'donor_id': self.donor_id,
            'full_name': self.full_name,
            'blood_group': self.blood_group,
            'district': self.curr_district,
            'city': self.curr_city,
            'phone': self.phone1,
            'donor_type': self.donor_type,
            'availability': self.availability_status,
            'last_donation': self.last_donation_date.isoformat() if self.last_donation_date else None,
            'can_donate': self.can_donate_now,
        }
    
    def __repr__(self):
        return f'<Donor {self.donor_id}: {self.full_name} [{self.blood_group}]>'


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
    hospital        = db.Column(db.String(200), nullable=False)
    hospital_address= db.Column(db.String(300))
    contact_person  = db.Column(db.String(150), nullable=False)
    contact_number  = db.Column(db.String(15), nullable=False)
    alt_number      = db.Column(db.String(15))
    status          = db.Column(db.String(15), default='active', index=True)  # active|fulfilled|closed
    is_emergency    = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.request_id:
            ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            self.request_id = f"REQ-{ts}"
    
    @property
    def age_in_hours(self):
        delta = datetime.utcnow() - self.created_at
        return int(delta.total_seconds() / 3600)
    
    @property
    def age_label(self):
        hours = self.age_in_hours
        if hours < 1:
            return "Just now"
        elif hours < 24:
            return f"{hours}h ago"
        else:
            days = hours // 24
            return f"{days}d ago"
    
    @property
    def status_badge(self):
        badges = {
            'active': 'danger',
            'fulfilled': 'success',
            'closed': 'secondary'
        }
        return badges.get(self.status, 'secondary')
    
    def to_dict(self):
        return {
            'id': self.id,
            'request_id': self.request_id,
            'patient_name': self.patient_name,
            'blood_group': self.blood_group,
            'hospital': self.hospital,
            'contact_person': self.contact_person,
            'contact_number': self.contact_number,
            'status': self.status,
            'is_emergency': self.is_emergency,
            'created_at': self.created_at.isoformat(),
            'age_label': self.age_label,
        }
    
    def __repr__(self):
        return f'<BloodRequest {self.request_id}: {self.blood_group}>'


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
    category        = db.Column(db.String(30), default='news', index=True)  # news|event|program|story
    author          = db.Column(db.String(100))
    tags            = db.Column(db.String(300))
    is_published    = db.Column(db.Boolean, default=True, index=True)
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
    def category_badge(self):
        badges = {
            'news': 'primary',
            'event': 'success',
            'program': 'warning',
            'story': 'info'
        }
        return badges.get(self.category, 'secondary')
    
    @property
    def image_url(self):
        if self.featured_image:
            return f"/static/uploads/news/{self.featured_image}"
        return "/static/images/news-placeholder.jpg"
    
    def __repr__(self):
        return f'<News: {self.title[:50]}>'


# ─────────────────────────────────────────────
# NOTICE MODEL
# ─────────────────────────────────────────────
class Notice(db.Model):
    __tablename__ = 'notices'
    
    id              = db.Column(db.Integer, primary_key=True)
    title           = db.Column(db.String(300), nullable=False)
    content         = db.Column(db.Text, nullable=False)
    attachment      = db.Column(db.String(255))
    attachment_type = db.Column(db.String(10))  # pdf|image
    published_date  = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expiry_date     = db.Column(db.DateTime)
    is_active       = db.Column(db.Boolean, default=True, index=True)
    priority        = db.Column(db.Integer, default=0)  # higher = more important
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def is_expired(self):
        if self.expiry_date:
            return datetime.utcnow() > self.expiry_date
        return False
    
    @property
    def days_left(self):
        if not self.expiry_date:
            return None
        delta = self.expiry_date - datetime.utcnow()
        return max(0, delta.days)
    
    @property
    def attachment_url(self):
        if self.attachment:
            return f"/static/uploads/notices/{self.attachment}"
        return None
    
    def __repr__(self):
        return f'<Notice: {self.title[:50]}>'


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
    ad_type         = db.Column(db.String(20), default='sidebar', index=True)  # sidebar|banner|sponsor
    start_date      = db.Column(db.DateTime, default=datetime.utcnow)
    end_date        = db.Column(db.DateTime)
    clicks          = db.Column(db.Integer, default=0)
    impressions     = db.Column(db.Integer, default=0)
    is_active       = db.Column(db.Boolean, default=True, index=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def is_valid(self):
        if not self.is_active:
            return False
        now = datetime.utcnow()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True
    
    @property
    def ctr(self):
        """Click-through rate"""
        if self.impressions == 0:
            return 0.0
        return round((self.clicks / self.impressions) * 100, 2)
    
    @property
    def image_url(self):
        if self.image:
            return f"/static/uploads/ads/{self.image}"
        return "/static/images/ad-placeholder.jpg"
    
    def __repr__(self):
        return f'<Ad {self.id}: {self.title} [{self.ad_type}]>'


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
    
    def __repr__(self):
        return f'<Contact {self.name}: {self.subject[:30]}>'