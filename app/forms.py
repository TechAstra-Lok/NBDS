import re
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileSize
from urllib.parse import urlparse
from wtforms import (
    StringField, TextAreaField, SelectField, IntegerField,
    FloatField, PasswordField, SubmitField, DateField,
    BooleanField, URLField, HiddenField
)
from wtforms.validators import (
    DataRequired, Email, Length, NumberRange,
    Regexp, Optional, ValidationError, URL, EqualTo
)
from app.models import Donor


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


# ─── Blood Request Form ───────────────────────
class BloodRequestForm(FlaskForm):
    patient_name    = StringField('Patient Name *', validators=[
        DataRequired(), Length(min=2, max=150, message="Name must be 2-150 characters")
    ])
    case_details    = StringField('Case / Medical Condition *', validators=[
        DataRequired(), Length(min=3, max=255)
    ])
    request_message = TextAreaField('Blood Request Message *', validators=[
        DataRequired(), Length(min=20, max=2000)
    ], render_kw={"rows": 5, "placeholder": "Describe the urgency and details..."})
    blood_group     = SelectField('Blood Group Required *', choices=BLOOD_GROUP_CHOICES, validators=[
        DataRequired(message="Please select a blood group")
    ])
    units_needed    = IntegerField('Units Needed', default=1, validators=[
        DataRequired(), NumberRange(min=1, max=20)
    ])
    hospital        = StringField('Hospital Name *', validators=[
        DataRequired(), Length(min=3, max=200)
    ])
    hospital_address= StringField('Hospital Address', validators=[Optional(), Length(max=300)])
    contact_person  = StringField('Contact Person Name *', validators=[
        DataRequired(), Length(min=2, max=150)
    ])
    contact_number  = StringField('Contact Number *', validators=[
        DataRequired(message="Please enter a contact number")
    ])
    alt_number      = StringField('Alternate Number', validators=[
        Optional()
    ])
    is_emergency    = BooleanField('Mark as EMERGENCY')

    def validate_contact_person(self, field):
        # Encourage a real full name (first + last)
        name = (field.data or '').strip()
        if len(name) < 3:
            raise ValidationError('Please provide a valid full name (first and last).')
        # require at least two words to reduce anonymous/spam posts
        if len(name.split()) < 2:
            raise ValidationError('Please include both first and last name.')

    def _normalize_nepal_mobile(self, value):
        if not value:
            return ''
        cleaned = re.sub(r'[^0-9]', '', value)
        if cleaned.startswith('977') and len(cleaned) == 12:
            cleaned = cleaned[3:]
        return cleaned

    def validate_contact_number(self, field):
        normalized = self._normalize_nepal_mobile(field.data)
        if not re.match(r'^[9][678]\d{8}$', normalized):
            raise ValidationError("Enter valid Nepal mobile number (9XXXXXXXXX or +9779XXXXXXXXX)")
        field.data = normalized

    def validate_alt_number(self, field):
        if not field.data:
            return
        normalized = self._normalize_nepal_mobile(field.data)
        if not re.match(r'^[9][678]\d{8}$', normalized):
            raise ValidationError("Enter valid Nepal mobile number (9XXXXXXXXX or +9779XXXXXXXXX)")
        field.data = normalized
    submit          = SubmitField('Submit Blood Request')


# ─── Donor Registration Form ─────────────────
class DonorRegistrationForm(FlaskForm):
    full_name           = StringField('Full Name *', validators=[
        DataRequired(), Length(min=3, max=150)
    ])
    age                 = IntegerField('Age *', validators=[
        DataRequired(),
        NumberRange(min=18, max=65, message="Age must be between 18-65 years")
    ])
    weight              = FloatField('Weight (kg) *', validators=[
        DataRequired(),
        NumberRange(min=50, max=150, message="Weight must be 50-150 kg")
    ])
    
    # Permanent Address
    perm_province       = SelectField('Province', choices=PROVINCE_CHOICES, validators=[Optional()])
    perm_district       = StringField('District', validators=[Optional(), Length(max=80)])
    perm_city           = StringField('City/Village', validators=[Optional(), Length(max=100)])
    perm_local_level    = StringField('Local Level / VDC / Municipality', validators=[Optional(), Length(max=100)])
    
    # Current Address
    curr_province       = SelectField('Province *', choices=PROVINCE_CHOICES, validators=[
        DataRequired(message="Please select province")
    ])
    curr_district       = StringField('District *', validators=[
        DataRequired(), Length(min=2, max=80)
    ])
    curr_city           = StringField('City/Town *', validators=[
        DataRequired(), Length(min=2, max=100)
    ])
    curr_local_level    = StringField('Local Level / Municipality', validators=[Optional(), Length(max=100)])
    
    # Contact
    phone1              = StringField('Primary Phone *', validators=[
        DataRequired(),
        Regexp(r'^[9][678]\d{8}$', message="Enter valid Nepal mobile number (9XXXXXXXXX)")
    ])
    phone2              = StringField('Secondary Phone (Optional)', validators=[
        Optional(),
        Regexp(r'^[9][678]\d{8}$', message="Enter valid Nepal mobile number")
    ])
    
    # Blood Info
    blood_group         = SelectField('Blood Group *', choices=BLOOD_GROUP_CHOICES, validators=[
        DataRequired()
    ])
    last_donation_date  = DateField('Last Donation Date', format='%Y-%m-%d', validators=[Optional()])
    donation_times      = IntegerField('Total Previous Donations', default=0, validators=[
        Optional(), NumberRange(min=0, max=500)
    ])
    
    # Donor Meta
    donor_type          = SelectField('Donor Type *', choices=DONOR_TYPE_CHOICES, validators=[
        DataRequired()
    ])
    social_link         = StringField('Social Media Profile Link (Optional)', validators=[
        Optional(), Length(max=300)
    ])
    
    submit              = SubmitField('Register as Blood Donor')
    
    def validate_phone1(self, field):
        existing = Donor.query.filter_by(phone1=field.data).first()
        if existing:
            raise ValidationError(f'Phone {field.data} is already registered as donor {existing.donor_id}.')
    
    def validate_last_donation_date(self, field):
        if field.data:
            from datetime import date
            if field.data > date.today():
                raise ValidationError('Last donation date cannot be in the future.')


class DonorEditForm(DonorRegistrationForm):
    donor_id            = HiddenField()
    availability_status = SelectField('Availability Status *', choices=[
        ('available', 'Available to Donate'),
        ('unavailable', 'Currently Unavailable'),
    ])
    submit = SubmitField('Update Donor Profile')
    
    def validate_phone1(self, field):
        existing = Donor.query.filter_by(phone1=field.data).first()
        if existing and str(existing.id) != str(self.donor_id.data):
            raise ValidationError(f'Phone {field.data} is already registered.')


# ─── Admin Login Form ─────────────────────────
class AdminLoginForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(), Length(min=3, max=80)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(), Length(min=6)
    ])
    remember = BooleanField('Remember Me')
    submit   = SubmitField('Login to Admin Panel')


# ─── News Form ────────────────────────────────
class NewsForm(FlaskForm):
    title           = StringField('News Title *', validators=[
        DataRequired(), Length(min=5, max=300)
    ])
    short_desc      = TextAreaField('Short Description *', validators=[
        DataRequired(), Length(min=10, max=500)
    ], render_kw={"rows": 3})
    content         = TextAreaField('Full Content *', validators=[
        DataRequired(), Length(min=50)
    ], render_kw={"rows": 15, "id": "rich-editor"})
    category        = SelectField('Category *', choices=[
        ('news', 'News'),
        ('event', 'Event'),
        ('program', 'Blood Donation Program'),
        ('story', 'Success Story'),
    ], validators=[DataRequired()])
    author          = StringField('Author Name *', validators=[
        DataRequired(), Length(min=2, max=100)
    ])
    tags            = StringField('Tags (comma separated)', validators=[Optional(), Length(max=300)])
    featured_image  = FileField('Featured Image', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Images only!')
    ])
    is_published    = BooleanField('Publish Now', default=True)
    submit          = SubmitField('Save News Post')


# ─── Notice Form ─────────────────────────────
class NoticeForm(FlaskForm):
    title           = StringField('Notice Title *', validators=[
        DataRequired(), Length(min=5, max=300)
    ])
    content         = TextAreaField('Notice Content *', validators=[
        DataRequired(), Length(min=10)
    ], render_kw={"rows": 8})
    expiry_date     = DateField('Expiry Date (Optional)', format='%Y-%m-%d', validators=[Optional()])
    priority        = SelectField('Priority', choices=[
        ('0', 'Normal'),
        ('1', 'Important'),
        ('2', 'Urgent'),
    ], default='0')
    attachment      = FileField('Attachment (PDF/Image)', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'PDF or Images only!')
    ])
    is_active       = BooleanField('Make Active', default=True)
    submit          = SubmitField('Publish Notice')


# ─── Advertisement Form ───────────────────────
class AdvertisementForm(FlaskForm):
    title           = StringField('Ad Title *', validators=[
        DataRequired(), Length(min=3, max=200)
    ])
    description     = TextAreaField('Description', validators=[Optional()], render_kw={"rows": 3})
    image           = FileField('Banner Image *', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Images only!')
    ])
    redirect_url    = StringField('Redirect URL', validators=[
        Optional(), Length(max=500)
    ])
    ad_type         = SelectField('Ad Type *', choices=[
        ('sidebar', 'Sidebar Advertisement'),
        ('banner', 'Homepage Banner'),
        ('sponsor', 'Sponsor Advertisement'),
    ], validators=[DataRequired()])
    start_date      = DateField('Start Date *', validators=[DataRequired()])
    end_date        = DateField('End Date *', validators=[DataRequired()])
    is_active       = BooleanField('Active', default=True)
    submit          = SubmitField('Save Advertisement')
    
    def validate_end_date(self, field):
        if self.start_date.data and field.data:
            if field.data <= self.start_date.data:
                raise ValidationError('End date must be after start date.')

    def validate_redirect_url(self, field):
        if field.data:
            url = field.data.strip()
            if url.lower().startswith(('javascript:', 'data:', 'vbscript:')):
                raise ValidationError('Invalid redirect URL.')
            parsed = urlparse(url)
            if parsed.scheme:
                if parsed.scheme not in ('http', 'https'):
                    raise ValidationError('URL must use http or https.')
            elif not url.startswith('/'):
                raise ValidationError('URL must be an absolute or root-relative path.')


# ─── Contact Form ─────────────────────────────
class ContactForm(FlaskForm):
    name    = StringField('Your Name *', validators=[DataRequired(), Length(min=3, max=150)])
    email   = StringField('Email Address *', validators=[DataRequired(), Email()])
    phone   = StringField('Phone Number', validators=[
        Optional(), Regexp(r'^[9][678]\d{8}$', message="Enter valid Nepal mobile number")
    ])
    subject = StringField('Subject *', validators=[DataRequired(), Length(min=5, max=255)])
    message = TextAreaField('Message *', validators=[
        DataRequired(), Length(min=20, max=3000)
    ], render_kw={"rows": 7})
    submit  = SubmitField('Send Message')


class RequestManagementForm(FlaskForm):
    request_id     = StringField('Request ID *', validators=[
        DataRequired(), Length(min=5, max=30)
    ])
    contact_number = StringField('Contact Number *', validators=[
        DataRequired(), Regexp(r'^[9][678]\d{8}$', message="Enter valid Nepal mobile number")
    ])
    submit         = SubmitField('Find Request')


# ─── Admin User Form ──────────────────────────
class AdminUserForm(FlaskForm):
    username    = StringField('Username *', validators=[DataRequired(), Length(min=3, max=80)])
    email       = StringField('Email *', validators=[DataRequired(), Email()])
    full_name   = StringField('Full Name *', validators=[DataRequired(), Length(min=3, max=150)])
    role        = SelectField('Role *', choices=[
        ('admin', 'Content Admin'),
        ('superadmin', 'Super Admin'),
    ])
    password    = PasswordField('Password', validators=[Optional(), Length(min=8)])
    confirm_pw  = PasswordField('Confirm Password', validators=[EqualTo('password')])
    is_active   = BooleanField('Active Account', default=True)
    submit      = SubmitField('Save Admin User')