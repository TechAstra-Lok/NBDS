import re
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, TextAreaField, SelectField, IntegerField,
    FloatField, PasswordField, SubmitField, DateField,
    BooleanField
)
from wtforms.widgets import HiddenInput
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
    ('regular', 'Regular Donor'),
    ('emergency', 'Emergency Donor'),
    ('platelet', 'Platelet Donor'),
    ('rare', 'Rare Blood Donor'),
    ('volunteer', 'Volunteer Donor'),
    ('occasional', 'Occasional Donor'),
    ('other', 'Other'),
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
    login_id = StringField('Mobile Number or Email *', validators=[DataRequired()])
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
    email               = StringField('Email Address (Optional)', validators=[Optional(), Email(), Length(max=120)])
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
    consent             = BooleanField('I confirm that the information provided is accurate and I agree to be contacted by patients in need of blood. I understand my phone number will be visible to people searching for donors.', validators=[DataRequired(message='You must agree to the terms and conditions to register.')])
    
    submit              = SubmitField('Register as Blood Donor')
    
    def validate_phone1(self, field):
        if field.data and Donor.query.filter_by(phone1=field.data.strip()).first():
            raise ValidationError(f'Phone {field.data} is already registered.')
            
    def validate_email(self, field):
        if field.data and field.data.strip():
            if Donor.query.filter_by(email=field.data.strip()).first():
                raise ValidationError(f'Email {field.data} is already registered.')


class DonorAdminCreateForm(FlaskForm):
    """Admin-specific form for adding new donors from the admin dashboard."""
    full_name           = StringField('Full Name *', validators=[DataRequired(), Length(min=3, max=150)])
    email               = StringField('Email Address (Optional)', validators=[Optional(), Email(), Length(max=120)])
    phone1              = StringField('Primary Mobile *', validators=[DataRequired(), validate_nepal_mobile])
    phone2              = StringField('Secondary Mobile (Optional)', validators=[Optional(), validate_nepal_mobile])
    
    age                 = IntegerField('Age *', validators=[DataRequired(), NumberRange(min=18, max=65)])
    weight              = FloatField('Weight (kg) *', validators=[DataRequired(), NumberRange(min=45, max=150)])
    
    # Permanent Address
    perm_province       = SelectField('Province', choices=PROVINCE_CHOICES, validators=[Optional()])
    perm_district       = StringField('District', validators=[Optional(), Length(max=80)])
    perm_local_level    = StringField('Local Level / Municipality', validators=[Optional(), Length(max=100)])
    perm_ward           = StringField('Ward No', validators=[Optional(), Length(max=10)])
    perm_tole           = StringField('Tole / Street', validators=[Optional(), Length(max=100)])
    
    # Current Address
    curr_province       = SelectField('Province *', choices=PROVINCE_CHOICES, validators=[DataRequired()])
    curr_district       = StringField('District *', validators=[DataRequired(), Length(max=80)])
    curr_local_level    = StringField('Local Level / Municipality *', validators=[DataRequired(), Length(max=100)])
    curr_ward           = StringField('Ward No', validators=[Optional(), Length(max=10)])
    curr_tole           = StringField('Tole / Street', validators=[Optional(), Length(max=100)])
    
    # Blood Info
    blood_group         = SelectField('Blood Group *', choices=BLOOD_GROUP_CHOICES, validators=[DataRequired()])
    last_donation_date  = DateField('Last Donation Date', format='%Y-%m-%d', validators=[Optional()])
    donation_times      = IntegerField('Total Previous Donations', default=0, validators=[Optional(), NumberRange(min=0, max=500)])
    
    donor_type          = SelectField('Donor Type *', choices=DONOR_TYPE_CHOICES, validators=[DataRequired()])
    social_link         = StringField('Social Media Link (Optional)', validators=[Optional(), Length(max=300)])
    
    submit              = SubmitField('Add Blood Donor')
    
    def validate_phone1(self, field):
        if field.data and Donor.query.filter_by(phone1=field.data.strip()).first():
            raise ValidationError(f'Phone number {field.data} is already registered.')
            
    def validate_email(self, field):
        if field.data and field.data.strip():
            if Donor.query.filter_by(email=field.data.strip()).first():
                raise ValidationError(f'Email {field.data} is already registered.')


class DonorEditForm(FlaskForm):
    record_id           = IntegerField(widget=HiddenInput())
    full_name           = StringField('Full Name *', validators=[DataRequired(), Length(min=3, max=150)])
    email               = StringField('Email Address (Optional)', validators=[Optional(), Email(), Length(max=120)])
    phone1              = StringField('Primary Mobile *', validators=[DataRequired(), validate_nepal_mobile])
    phone2              = StringField('Secondary Mobile', validators=[Optional(), validate_nepal_mobile])
    age                 = IntegerField('Age *', validators=[DataRequired(), NumberRange(min=18, max=65)])
    weight              = FloatField('Weight (kg)', validators=[Optional(), NumberRange(min=45, max=150)])
    blood_group         = SelectField('Blood Group *', choices=BLOOD_GROUP_CHOICES, validators=[DataRequired()])
    donor_type          = SelectField('Donor Type *', choices=DONOR_TYPE_CHOICES, validators=[DataRequired()])
    availability_status = SelectField('Availability Status *', choices=[
        ('available', 'Available to Donate'),
        ('recently_donated', 'Recently Donated (0-30 Days)'),
        ('unavailable', 'Currently Unavailable'),
    ])
    last_donation_date  = DateField('Last Donation Date', format='%Y-%m-%d', validators=[Optional()])
    donation_times      = IntegerField('Total Donations', default=0, validators=[Optional(), NumberRange(min=0)])
    social_link         = StringField('Social Media Link', validators=[Optional(), Length(max=300)])
    gender              = SelectField('Gender', choices=[
        ('', '-- Select --'),
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer Not to Say'),
    ], validators=[Optional()])
    emergency_contact   = StringField('Emergency Contact', validators=[Optional(), Length(max=15)])
    donor_notes         = TextAreaField('Notes', validators=[Optional()], render_kw={"rows": 3})
    is_public           = BooleanField('Public Profile', default=True)
    
    # Address
    curr_province       = SelectField('Province *', choices=PROVINCE_CHOICES, validators=[DataRequired()])
    curr_district       = StringField('District *', validators=[DataRequired(), Length(max=80)])
    curr_local_level    = StringField('Local Level *', validators=[DataRequired(), Length(max=100)])
    curr_ward           = StringField('Ward No', validators=[Optional(), Length(max=10)])
    curr_tole           = StringField('Tole / Street', validators=[Optional(), Length(max=100)])
    perm_province       = SelectField('Province', choices=PROVINCE_CHOICES, validators=[Optional()])
    perm_district       = StringField('District', validators=[Optional(), Length(max=80)])
    perm_local_level    = StringField('Local Level', validators=[Optional(), Length(max=100)])
    perm_ward           = StringField('Ward No', validators=[Optional(), Length(max=10)])
    perm_tole           = StringField('Tole / Street', validators=[Optional(), Length(max=100)])
    
    submit = SubmitField('Update Donor Profile')

    def validate_phone1(self, field):
        if field.data and field.data.strip():
            existing = Donor.query.filter_by(phone1=field.data.strip()).first()
            if existing and existing.id != self.record_id.data:
                raise ValidationError(f'Phone {field.data} is already registered to another donor.')

    def validate_email(self, field):
        if field.data and field.data.strip():
            existing = Donor.query.filter_by(email=field.data.strip()).first()
            if existing and existing.id != self.record_id.data:
                raise ValidationError(f'Email {field.data} is already registered to another donor.')


class DonorProfileEditForm(FlaskForm):
    """Form for donors to edit their own profile from the dashboard."""
    full_name           = StringField('Full Name *', validators=[DataRequired(), Length(min=3, max=150)])
    phone2              = StringField('Secondary Mobile', validators=[Optional(), validate_nepal_mobile])
    age                 = IntegerField('Age *', validators=[DataRequired(), NumberRange(min=18, max=65)])
    weight              = FloatField('Weight (kg)', validators=[Optional(), NumberRange(min=45, max=150)])
    donor_type          = SelectField('Donor Type *', choices=DONOR_TYPE_CHOICES, validators=[DataRequired()])
    social_link         = StringField('Social Media Link', validators=[Optional(), Length(max=300)])
    gender              = SelectField('Gender', choices=[
        ('', '-- Select --'),
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer Not to Say'),
    ], validators=[Optional()])
    emergency_contact   = StringField('Emergency Contact', validators=[Optional(), Length(max=15)])
    donor_notes         = TextAreaField('Notes', validators=[Optional()], render_kw={"rows": 3})
    is_public           = BooleanField('Show Profile Publicly', default=True)
    
    # Current Address (editable)
    curr_province       = SelectField('Province *', choices=PROVINCE_CHOICES, validators=[DataRequired()])
    curr_district       = SelectField('District *', choices=[('', '-- Select District --')], validate_choice=False, validators=[DataRequired()])
    curr_local_level    = SelectField('Local Level *', choices=[('', '-- Select Municipality --')], validate_choice=False, validators=[DataRequired()])
    curr_ward           = StringField('Ward No', validators=[Optional(), Length(max=10)])
    curr_tole           = StringField('Tole / Street', validators=[Optional(), Length(max=100)])
    
    # Notification Preferences
    email_alerts        = BooleanField('Email Alerts', default=True)
    sms_alerts          = BooleanField('SMS Alerts', default=True)
    in_app_alerts       = BooleanField('In-App Alerts', default=True)
    
    # Profile Photo
    profile_photo       = FileField('Profile Photo', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Only image files (jpg, png, webp) are allowed.')
    ])
    
    submit = SubmitField('Save Profile Changes')


class DonationHistoryForm(FlaskForm):
    """Form for adding/editing a donation record."""
    donation_date   = DateField('Donation Date *', format='%Y-%m-%d', validators=[DataRequired()])
    donation_type   = SelectField('Donation Type *', choices=[
        ('whole_blood', 'Whole Blood'),
        ('platelet', 'Platelet (SDP)'),
        ('plasma', 'Plasma'),
        ('sdp', 'Single Donor Platelet'),
        ('other', 'Other'),
    ], validators=[DataRequired()])
    location        = StringField('Hospital / Blood Bank Name', validators=[Optional(), Length(max=200)])
    units           = FloatField('Units Donated', default=1.0, validators=[Optional(), NumberRange(min=0.5, max=5)])
    notes           = TextAreaField('Notes (Optional)', validators=[Optional(), Length(max=500)], render_kw={"rows": 3})
    submit          = SubmitField('Save Donation Record')


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


BLOOD_COMPONENT_CHOICES = [
    ('Whole Blood', 'Whole Blood (सबै रगत)'),
    ('Packed Red Blood Cells (PRBC/PCV)', 'Packed Red Blood Cells (PRBC / PCV)'),
    ('Platelet Concentrate (RDP)', 'Platelet Concentrate (RDP)'),
    ('Single Donor Platelets (SDP)', 'Single Donor Platelets (SDP)'),
    ('Fresh Frozen Plasma (FFP)', 'Fresh Frozen Plasma (FFP)'),
    ('White Blood Cells (WBC)', 'White Blood Cells (WBC / Granulocytes)'),
    ('Cryoprecipitate', 'Cryoprecipitate (क्रायो)'),
    ('Other / Special', 'Other / Special Requirement')
]


# ─── Blood Request Form ───────────────────────
class BloodRequestForm(FlaskForm):
    patient_name    = StringField('Patient Name *', validators=[DataRequired(), Length(min=2, max=150)])
    case_details    = StringField('Case / Medical Condition *', validators=[DataRequired(), Length(min=3, max=255)])
    request_message = TextAreaField('Blood Request Message (Optional)', validators=[Optional(), Length(max=2000)], render_kw={"rows": 5})
    blood_group     = SelectField('Blood Group Required *', choices=BLOOD_GROUP_CHOICES, validators=[DataRequired()])
    required_component = SelectField('Required Blood Type / Component *', choices=BLOOD_COMPONENT_CHOICES, default='Whole Blood', validators=[DataRequired()])
    units_needed    = IntegerField('Units Needed', default=1, validators=[DataRequired(), NumberRange(min=1, max=20)])
    
    hospital        = StringField('Hospital Name *', validators=[DataRequired(), Length(min=3, max=200)])
    province        = SelectField('Province *', choices=PROVINCE_CHOICES, validators=[DataRequired()])
    district        = SelectField('District *', choices=[('', '-- Select District --')], validate_choice=False, validators=[DataRequired()])
    local_level     = SelectField('Local Level *', choices=[('', '-- Select Municipality --')], validate_choice=False, validators=[DataRequired()])
    ward_no         = StringField('Ward No', validators=[Optional(), Length(max=10)])
    
    contact_person  = StringField('Contact Person Name *', validators=[DataRequired(), Length(min=2, max=150)])
    contact_number  = StringField('Contact Number *', validators=[DataRequired(), validate_nepal_mobile])
    alt_number      = StringField('Alternate Number', validators=[Optional(), validate_nepal_mobile])
    
    pin             = PasswordField('4-Digit PIN *', validators=[
        DataRequired(), Regexp(r'^\d{4}$', message="PIN must be exactly 4 digits")
    ])
    confirm_pin     = PasswordField('Confirm PIN *', validators=[
        DataRequired(), EqualTo('pin', message='PINs must match')
    ])
    
    is_emergency    = BooleanField('Mark as EMERGENCY')
    hospital_paper  = FileField('Hospital Request Paper (Optional)', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')])
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
    priority        = SelectField('Priority', choices=[(0, 'Normal'), (1, 'Important'), (2, 'Urgent')], coerce=int, default=0)
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


# ─── Blood Bank Form ─────────────────────────────
class BloodBankForm(FlaskForm):
    name = StringField('Blood Bank Name', validators=[DataRequired(), Length(max=200)])
    display_name = StringField('Display Name (Optional)', validators=[Optional(), Length(max=200)])
    hospital_name = StringField('Hospital Name (Optional)', validators=[Optional(), Length(max=200)])
    branch_type = StringField('Branch Type', default='Main/Sub Branch', validators=[Length(max=60)])
    service_type = SelectField('Service Type', choices=[
        ('Blood Transfusion Service', 'Blood Transfusion Service'),
        ('Emergency Panel', 'Emergency Panel'),
        ('Regional Center', 'Regional Center'),
        ('Hospital Blood Bank', 'Hospital Blood Bank')
    ])
    province = SelectField('Province', choices=PROVINCE_CHOICES, validators=[DataRequired()])
    district = StringField('District', validators=[DataRequired(), Length(max=80)])
    city = StringField('City/Municipality', validators=[Optional(), Length(max=120)])
    contact_number = StringField('Contact Number', validators=[DataRequired(), Length(max=20)])
    alternate_contact_number = StringField('Alternate Contact (Optional)', validators=[Optional(), Length(max=20)])
    maps_url = StringField('Google Maps Link / Plus Code', validators=[Optional(), Length(max=500)])
    is_emergency_panel = BooleanField('Is Emergency Panel?')
    is_grouped_entry = BooleanField('Is Grouped Entry?')
    is_active = BooleanField('Is Active?', default=True)
    notes = TextAreaField('Notes/Address Details', validators=[Optional()])
    submit = SubmitField('Save Blood Bank')


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
STAFF_DESIGNATION_CHOICES = [
    ('', '-- Select Designation --'),
    ('Medical Officer', 'Medical Officer / Duty Doctor'),
    ('Lab Technician', 'Lab Technician'),
    ('Senior Lab Technologist', 'Senior Lab Technologist'),
    ('Blood Collection Officer', 'Blood Collection Officer / Phlebotomist'),
    ('Nurse', 'Staff Nurse / Nursing Officer'),
    ('Receptionist', 'Receptionist / Front Desk'),
    ('Emergency Coordinator', 'Emergency Coordinator'),
    ('Ambulance Driver', 'Ambulance Driver'),
    ('Counselor', 'Donor Counselor'),
    ('Quality Manager', 'Quality Control Manager'),
    ('Volunteer', 'Volunteer / Intern'),
    ('Other', 'Other Designation'),
]

STAFF_AVAILABILITY_CHOICES = [
    ('available', 'Available (Off-Duty Standard)'),
    ('on_duty', 'Currently On Duty'),
    ('emergency_standby', 'Emergency Standby (Ready to Deploy)'),
    ('on_leave', 'On Leave'),
    ('off_duty', 'Off Duty'),
    ('unavailable', 'Unavailable'),
]

STAFF_EMPLOYMENT_CHOICES = [
    ('active', 'Active Employee'),
    ('on_leave', 'On Leave'),
    ('inactive', 'Inactive / Suspended'),
    ('resigned', 'Resigned / Former Staff'),
]

STAFF_VISIBILITY_CHOICES = [
    ('public', 'Public (Visible on Blood Bank Public Profile)'),
    ('private', 'Private (Internal Blood Bank & Admin Only)'),
]

class StaffMemberForm(FlaskForm):
    full_name           = StringField('Full Name *', validators=[DataRequired(), Length(max=150)])
    designation         = StringField('Designation *', validators=[DataRequired(), Length(max=100)])
    qualification       = StringField('Qualification / Degree', validators=[Optional(), Length(max=150)])
    registration_number = StringField('Medical / NMC / NHPC Reg. No.', validators=[Optional(), Length(max=100)])
    
    email               = StringField('Email', validators=[Optional(), Email()])
    contact_number      = StringField('Primary Contact Number', validators=[Optional(), validate_nepal_mobile])
    secondary_contact   = StringField('Secondary Contact Number', validators=[Optional(), validate_nepal_mobile])
    emergency_contact   = StringField('Emergency Contact Number', validators=[Optional(), validate_nepal_mobile])
    
    profile_photo       = FileField('Profile Photo', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp'])])
    
    # Status & Privacy
    availability_status = SelectField('Availability Status', choices=STAFF_AVAILABILITY_CHOICES, default='available')
    employment_status   = SelectField('Employment Status', choices=STAFF_EMPLOYMENT_CHOICES, default='active')
    profile_visibility  = SelectField('Profile Visibility', choices=STAFF_VISIBILITY_CHOICES, default='public')
    is_active           = BooleanField('System Active', default=True)

    # Address
    province            = SelectField('Province', choices=PROVINCE_CHOICES, validators=[Optional()])
    district            = SelectField('District', choices=[('', '-- Select District --')], validate_choice=False, validators=[Optional()])
    local_level         = SelectField('Local Level', choices=[('', '-- Select Municipality --')], validate_choice=False, validators=[Optional()])
    ward_number         = StringField('Ward No', validators=[Optional(), Length(max=10)])
    tole                = StringField('Tole / Street', validators=[Optional(), Length(max=100)])
    
    submit              = SubmitField('Save Staff Member')


class BloodBankShiftForm(FlaskForm):
    shift_name          = StringField('Shift Name *', validators=[DataRequired(), Length(max=100)])
    shift_type          = SelectField('Shift Type', choices=[
        ('morning', 'Morning Shift'),
        ('evening', 'Evening Shift'),
        ('night', 'Night Shift'),
        ('emergency', 'Emergency Shift'),
        ('custom', 'Custom Shift'),
    ], default='morning')
    start_time          = StringField('Start Time (HH:MM) *', validators=[
        DataRequired(), Regexp(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', message="Enter time in 24-hour format (e.g. 06:00, 14:00)")
    ])
    end_time            = StringField('End Time (HH:MM) *', validators=[
        DataRequired(), Regexp(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', message="Enter time in 24-hour format (e.g. 14:00, 22:00)")
    ])
    notes               = TextAreaField('Shift Notes / Description', validators=[Optional()], render_kw={"rows": 2})
    is_active           = BooleanField('Active', default=True)
    submit              = SubmitField('Save Shift')


class BloodBankShiftAssignmentForm(FlaskForm):
    shift_id            = SelectField('Shift *', coerce=int, validators=[DataRequired()])
    staff_id            = SelectField('Staff Member *', coerce=int, validators=[DataRequired()])
    role_in_shift       = StringField('Role In Shift', validators=[Optional(), Length(max=100)])
    submit              = SubmitField('Assign Staff to Shift')


class DonorForcedPinChangeForm(FlaskForm):
    new_pin             = PasswordField('New 4-Digit PIN *', validators=[
        DataRequired(),
        Regexp(r'^\d{4}$', message="PIN must be exactly 4 digits (numeric 0-9).")
    ])
    confirm_pin         = PasswordField('Confirm New PIN *', validators=[
        DataRequired(),
        EqualTo('new_pin', message="PIN confirmation does not match.")
    ])
    submit              = SubmitField('Set New PIN & Continue')

    def validate_new_pin(self, field):
        val = str(field.data or '').strip()
        WEAK_PINS = {'1234', '4321', '0000', '1111', '2222', '3333', '4444', '5555', '6666', '7777', '8888', '9999'}
        if val in WEAK_PINS:
            raise ValidationError("Please choose a stronger PIN. Sequences like 1234 or repeating digits like 1111 are not allowed.")


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
    pin             = PasswordField('4-Digit PIN *', validators=[
        DataRequired(), Regexp(r'^\d{4}$', message="PIN must be exactly 4 digits")
    ])
    submit          = SubmitField('Find My Request')