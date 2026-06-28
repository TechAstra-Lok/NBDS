import re
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from urllib.parse import urlparse
from wtforms import (
    StringField, TextAreaField, SelectField, IntegerField,
    FloatField, PasswordField, SubmitField, DateField,
    BooleanField, URLField, HiddenField
)
from wtforms.validators import (
    DataRequired, Email, Length, NumberRange,
    Regexp, Optional, ValidationError, EqualTo
)
from app.models import Donor, Volunteer


# ─── Constants ───────────────────────────────
BLOOD_GROUP_CHOICES = [
    ('', '-- Select Blood Group --'),
    ('A+', 'A+'), ('A-', 'A-'),
    ('B+', 'B+'), ('B-', 'B-'),
    ('AB+', 'AB+'), ('AB-', 'AB-'),
    ('O+', 'O+'), ('O-', 'O-'),
]

PROVINCE_CHOICES = [
    ('', '-- Select Province --'),
    ('Koshi Pradesh', 'Koshi Pradesh'),
    ('Madhesh Pradesh', 'Madhesh Pradesh'),
    ('Bagmati Pradesh', 'Bagmati Pradesh'),
    ('Gandaki Pradesh', 'Gandaki Pradesh'),
    ('Lumbini Pradesh', 'Lumbini Pradesh'),
    ('Karnali Pradesh', 'Karnali Pradesh'),
    ('Sudurpashchim Pradesh', 'Sudurpashchim Pradesh'),
]

DONOR_TYPE_CHOICES = [
    ('', '-- Select Type --'),
    ('occasional', 'Occasional Donor'),
    ('regular', 'Regular Donor'),
    ('emergency', 'Emergency Only'),
]

VOLUNTEER_DESIGNATION_CHOICES = [
    ('', '-- Select Designation --'),
    ('Doctor', 'Doctor'),
    ('Nurse', 'Nurse'),
    ('HA', 'Health Assistant (HA)'),
    ('Other', 'Other Medical Staff'),
]

# ─── Base Functions ──────────────────────────
def _normalize_nepal_mobile(value):
    if not value:
        return ''
    cleaned = re.sub(r'[^0-9]', '', value)
    if cleaned.startswith('977') and len(cleaned) == 12:
        cleaned = cleaned[3:]
    return cleaned

def validate_nepal_mobile(form, field):
    normalized = _normalize_nepal_mobile(field.data)
    if not re.match(r'^[9][678]\d{8}$', normalized):
        raise ValidationError("Enter valid Nepal mobile number (9XXXXXXXXX)")
    field.data = normalized


# ─── Authentication Forms ─────────────────────
class DonorLoginForm(FlaskForm):
    phone1   = StringField('Mobile Number *', validators=[DataRequired(), validate_nepal_mobile])
    pin      = PasswordField('4-Digit PIN *', validators=[DataRequired(), Length(min=4, max=4)])
    remember = BooleanField('Remember Me')
    submit   = SubmitField('Login as Donor')


class VolunteerLoginForm(FlaskForm):
    phone1   = StringField('Mobile Number *', validators=[DataRequired(), validate_nepal_mobile])
    pin      = PasswordField('4-Digit PIN *', validators=[DataRequired(), Length(min=4, max=4)])
    remember = BooleanField('Remember Me')
    submit   = SubmitField('Login as Volunteer')


class AdminLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    remember = BooleanField('Remember Me')
    submit   = SubmitField('Login to Admin Panel')


# ─── Donor Forms ─────────────────────────────
class DonorRegistrationForm(FlaskForm):
    full_name           = StringField('Full Name *', validators=[DataRequired(), Length(min=3, max=150)])
    email               = StringField('Email Address *', validators=[DataRequired(), Email(), Length(max=120)])
    phone1              = StringField('Primary Mobile *', validators=[DataRequired(), validate_nepal_mobile])
    phone2              = StringField('Secondary Mobile (Optional)', validators=[Optional(), validate_nepal_mobile])
    
    pin                 = PasswordField('4-Digit PIN *', validators=[
        DataRequired(), Regexp(r'^\d{4}$', message="PIN must be exactly 4 digits")
    ])
    confirm_pin         = PasswordField('Confirm PIN *', validators=[
        DataRequired(), EqualTo('pin', message='PINs must match')
    ])
    
    age                 = IntegerField('Age *', validators=[DataRequired(), NumberRange(min=18, max=65)])
    weight              = FloatField('Weight (kg) *', validators=[DataRequired(), NumberRange(min=45, max=150)])
    
    # Permanent Address
    perm_province       = SelectField('Province', choices=PROVINCE_CHOICES, validators=[Optional()])
    perm_district       = SelectField('District', choices=[('', '-- Select District --')], validate_choice=False)
    perm_local_level    = SelectField('Local Level', choices=[('', '-- Select Municipality --')], validate_choice=False)
    perm_ward           = StringField('Ward No', validators=[Optional(), Length(max=10)])
    perm_tole           = StringField('Tole / Street', validators=[Optional(), Length(max=100)])
    
    # Current Address
    curr_province       = SelectField('Province *', choices=PROVINCE_CHOICES, validators=[DataRequired()])
    curr_district       = SelectField('District *', choices=[('', '-- Select District --')], validate_choice=False, validators=[DataRequired()])
    curr_local_level    = SelectField('Local Level *', choices=[('', '-- Select Municipality --')], validate_choice=False, validators=[DataRequired()])
    curr_ward           = StringField('Ward No', validators=[Optional(), Length(max=10)])
    curr_tole           = StringField('Tole / Street', validators=[Optional(), Length(max=100)])
    
    # Blood Info
    blood_group         = SelectField('Blood Group *', choices=BLOOD_GROUP_CHOICES, validators=[DataRequired()])
    last_donation_date  = DateField('Last Donation Date', format='%Y-%m-%d', validators=[Optional()])
    donation_times      = IntegerField('Total Previous Donations', default=0, validators=[Optional(), NumberRange(min=0, max=500)])
    
    donor_type          = SelectField('Donor Type *', choices=DONOR_TYPE_CHOICES, validators=[DataRequired()])
    social_link         = StringField('Social Media Link (Optional)', validators=[Optional(), Length(max=300)])
    
    submit              = SubmitField('Register as Blood Donor')
    
    def validate_phone1(self, field):
        if Donor.query.filter_by(phone1=field.data).first():
            raise ValidationError(f'Phone {field.data} is already registered.')
            
    def validate_email(self, field):
        if Donor.query.filter_by(email=field.data).first():
            raise ValidationError(f'Email {field.data} is already registered.')


class DonorEditForm(FlaskForm):
    availability_status = SelectField('Availability Status *', choices=[
        ('available', 'Available to Donate'),
        ('recently_donated', 'Recently Donated (0-90 Days)'),
        ('unavailable', 'Currently Unavailable'),
    ])
    last_donation_date  = DateField('Last Donation Date', format='%Y-%m-%d', validators=[Optional()])
    curr_province       = SelectField('Province *', choices=PROVINCE_CHOICES, validators=[DataRequired()])
    curr_district       = SelectField('District *', choices=[('', '-- Select District --')], validate_choice=False, validators=[DataRequired()])
    curr_local_level    = SelectField('Local Level *', choices=[('', '-- Select Municipality --')], validate_choice=False, validators=[DataRequired()])
    curr_ward           = StringField('Ward No', validators=[Optional(), Length(max=10)])
    curr_tole           = StringField('Tole / Street', validators=[Optional(), Length(max=100)])
    submit = SubmitField('Update Donor Profile')


# ─── Volunteer Forms ─────────────────────────
class VolunteerRegistrationForm(FlaskForm):
    full_name           = StringField('Full Name *', validators=[DataRequired(), Length(min=3, max=150)])
    email               = StringField('Email Address *', validators=[DataRequired(), Email(), Length(max=120)])
    phone1              = StringField('Primary Mobile *', validators=[DataRequired(), validate_nepal_mobile])
    phone2              = StringField('Secondary Mobile (Optional)', validators=[Optional(), validate_nepal_mobile])
    
    pin                 = PasswordField('4-Digit PIN *', validators=[
        DataRequired(), Regexp(r'^\d{4}$', message="PIN must be exactly 4 digits")
    ])
    confirm_pin         = PasswordField('Confirm PIN *', validators=[
        DataRequired(), EqualTo('pin', message='PINs must match')
    ])
    
    designation         = SelectField('Designation *', choices=VOLUNTEER_DESIGNATION_CHOICES, validators=[DataRequired()])
    working_field       = StringField('Working Field (e.g. Ortho, Neuro)', validators=[Optional(), Length(max=100)])
    
    perm_address        = StringField('Permanent Address *', validators=[DataRequired(), Length(max=200)])
    curr_address        = StringField('Current Working Address *', validators=[DataRequired(), Length(max=200)])
    curr_district       = SelectField('Working District *', choices=[('', '-- Select District --')], validate_choice=False, validators=[DataRequired()])
    
    availability_time   = StringField('Availability Time (e.g. 10AM - 5PM)', validators=[Optional(), Length(max=150)])
    
    submit              = SubmitField('Register as Volunteer')
    
    def validate_phone1(self, field):
        if Volunteer.query.filter_by(phone1=field.data).first():
            raise ValidationError(f'Phone {field.data} is already registered.')
            
    def validate_email(self, field):
        if Volunteer.query.filter_by(email=field.data).first():
            raise ValidationError(f'Email {field.data} is already registered.')


# ─── Blood Request Form ───────────────────────
class BloodRequestForm(FlaskForm):
    patient_name    = StringField('Patient Name *', validators=[DataRequired(), Length(min=2, max=150)])
    case_details    = StringField('Case / Medical Condition *', validators=[DataRequired(), Length(min=3, max=255)])
    request_message = TextAreaField('Blood Request Message *', validators=[DataRequired(), Length(min=20, max=2000)], render_kw={"rows": 5})
    blood_group     = SelectField('Blood Group Required *', choices=BLOOD_GROUP_CHOICES, validators=[DataRequired()])
    units_needed    = IntegerField('Units Needed', default=1, validators=[DataRequired(), NumberRange(min=1, max=20)])
    
    hospital        = StringField('Hospital Name *', validators=[DataRequired(), Length(min=3, max=200)])
    province        = SelectField('Province *', choices=PROVINCE_CHOICES, validators=[DataRequired()])
    district        = SelectField('District *', choices=[('', '-- Select District --')], validate_choice=False, validators=[DataRequired()])
    local_level     = SelectField('Local Level *', choices=[('', '-- Select Municipality --')], validate_choice=False, validators=[DataRequired()])
    ward_no         = StringField('Ward No', validators=[Optional(), Length(max=10)])
    
    contact_person  = StringField('Contact Person Name *', validators=[DataRequired(), Length(min=2, max=150)])
    contact_number  = StringField('Contact Number *', validators=[DataRequired(), validate_nepal_mobile])
    alt_number      = StringField('Alternate Number', validators=[Optional(), validate_nepal_mobile])
    is_emergency    = BooleanField('Mark as EMERGENCY')
    submit          = SubmitField('Submit Blood Request')


# ─── Success Story Form ───────────────────────
class SuccessStoryForm(FlaskForm):
    author_name     = StringField('Your Name *', validators=[DataRequired(), Length(min=2, max=100)])
    title           = StringField('Story Title *', validators=[DataRequired(), Length(min=5, max=200)])
    content         = TextAreaField('Your Story *', validators=[DataRequired(), Length(min=50)], render_kw={"rows": 6})
    district        = SelectField('District', choices=[('', '-- Select District --')], validate_choice=False, validators=[Optional()])
    blood_group     = SelectField('Blood Group', choices=BLOOD_GROUP_CHOICES, validators=[Optional()])
    social_link     = StringField('Social Media Profile Link *', validators=[DataRequired(), Length(max=500)])
    video_url       = StringField('Video URL (Optional)', validators=[Optional(), Length(max=500)])
    image_file      = FileField('Upload Photo *', validators=[DataRequired(), FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Images only!')])
    submit          = SubmitField('Submit Success Story')


# ─── Admin Content Forms (News, Notice, Ad) ───
class NewsForm(FlaskForm):
    title           = StringField('News Title *', validators=[DataRequired(), Length(min=5, max=300)])
    short_desc      = TextAreaField('Short Description *', validators=[DataRequired(), Length(min=10, max=500)], render_kw={"rows": 3})
    content         = TextAreaField('Full Content *', validators=[DataRequired(), Length(min=50)], render_kw={"rows": 15, "id": "rich-editor"})
    category        = SelectField('Category *', choices=[
        ('news', 'News'),
        ('event', 'Event'),
        ('program', 'Blood Donation Program'),
        ('story', 'Success Story'),
    ], validators=[DataRequired()])
    author          = StringField('Author Name *', validators=[DataRequired(), Length(min=2, max=100)])
    tags            = StringField('Tags (comma separated)', validators=[Optional(), Length(max=300)])
    featured_image  = FileField('Featured Image', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Images only!')])
    is_published    = BooleanField('Publish', default=True)
    scheduled_date  = DateField('Schedule Publication (Optional)', format='%Y-%m-%d', validators=[Optional()])
    submit          = SubmitField('Save News Post')


class NoticeForm(FlaskForm):
    title           = StringField('Notice Title *', validators=[DataRequired(), Length(min=5, max=300)])
    content         = TextAreaField('Notice Content *', validators=[DataRequired(), Length(min=10)], render_kw={"rows": 8})
    expiry_date     = DateField('Expiry Date (Optional)', format='%Y-%m-%d', validators=[Optional()])
    priority        = SelectField('Priority', choices=[('0', 'Normal'), ('1', 'Important'), ('2', 'Urgent')], default='0')
    attachment      = FileField('Attachment (PDF/Image)', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'PDF or Images only!')])
    is_active       = BooleanField('Make Active', default=True)
    submit          = SubmitField('Publish Notice')


class AdvertisementForm(FlaskForm):
    title           = StringField('Ad Title *', validators=[DataRequired(), Length(min=3, max=200)])
    description     = TextAreaField('Description', validators=[Optional()], render_kw={"rows": 3})
    image           = FileField('Banner Image *', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Images only!')])
    redirect_url    = StringField('Redirect URL', validators=[Optional(), Length(max=500)])
    ad_type         = SelectField('Ad Type *', choices=[
        ('sidebar', 'Sidebar Advertisement'),
        ('banner', 'Homepage Banner'),
        ('footer', 'Footer Banner'),
    ], validators=[DataRequired()])
    start_date      = DateField('Start Date *', validators=[DataRequired()])
    end_date        = DateField('End Date *', validators=[DataRequired()])
    is_active       = BooleanField('Active', default=True)
    submit          = SubmitField('Save Advertisement')


class ContactForm(FlaskForm):
    name    = StringField('Your Name *', validators=[DataRequired(), Length(min=3, max=150)])
    email   = StringField('Email Address *', validators=[DataRequired(), Email()])
    phone   = StringField('Phone Number', validators=[Optional(), validate_nepal_mobile])
    subject = StringField('Subject *', validators=[DataRequired(), Length(min=5, max=255)])
    message = TextAreaField('Message *', validators=[DataRequired(), Length(min=20, max=3000)], render_kw={"rows": 7})
    submit  = SubmitField('Send Message')


class AdminUserForm(FlaskForm):
    username    = StringField('Username *', validators=[DataRequired(), Length(min=3, max=80)])
    email       = StringField('Email *', validators=[DataRequired(), Email()])
    full_name   = StringField('Full Name *', validators=[DataRequired(), Length(min=3, max=150)])
    role        = SelectField('Role *', choices=[
        ('admin', 'Admin'),
        ('superadmin', 'Super Admin'),
        ('moderator', 'Moderator'),
        ('content_manager', 'Content Manager'),
    ])
    password    = PasswordField('Password', validators=[Optional(), Length(min=8)])
    confirm_pw  = PasswordField('Confirm Password', validators=[EqualTo('password')])
    is_active   = BooleanField('Active Account', default=True)
    submit      = SubmitField('Save Admin User')


# ─── Staff & Partner Forms ───────────────────
class StaffMemberForm(FlaskForm):
    full_name       = StringField('Full Name *', validators=[DataRequired(), Length(max=150)])
    designation     = StringField('Designation *', validators=[DataRequired(), Length(max=100)])
    email           = StringField('Email', validators=[Optional(), Email()])
    contact_number  = StringField('Contact Number', validators=[Optional(), validate_nepal_mobile])
    profile_photo   = FileField('Profile Photo', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp'])])
    province        = SelectField('Province', choices=PROVINCE_CHOICES, validators=[Optional()])
    district        = SelectField('District', choices=[('', '-- Select District --')], validate_choice=False, validators=[Optional()])
    local_level     = SelectField('Local Level', choices=[('', '-- Select Municipality --')], validate_choice=False, validators=[Optional()])
    ward_number     = StringField('Ward No', validators=[Optional(), Length(max=10)])
    tole            = StringField('Tole', validators=[Optional(), Length(max=100)])
    is_active       = BooleanField('Active', default=True)
    submit          = SubmitField('Save Staff Member')


class PartnerForm(FlaskForm):
    partner_name    = StringField('Partner Name *', validators=[DataRequired(), Length(max=200)])
    description     = TextAreaField('Description', validators=[Optional()], render_kw={"rows": 4})
    website_url     = StringField('Website URL', validators=[Optional(), Length(max=300)])
    email           = StringField('Email', validators=[Optional(), Email()])
    contact_number  = StringField('Contact Number', validators=[Optional()])
    address         = StringField('Address', validators=[Optional(), Length(max=255)])
    logo_file       = FileField('Partner Logo', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp'])])
    is_active       = BooleanField('Active', default=True)
    submit          = SubmitField('Save Partner')


# ─── Request Management Form ────────────────
class RequestManagementForm(FlaskForm):
    request_id      = StringField('Request ID *', validators=[DataRequired(), Length(min=5, max=30)])
    contact_number  = StringField('Contact Number *', validators=[DataRequired(), validate_nepal_mobile])
    submit          = SubmitField('Find My Request')