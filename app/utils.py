import os
import uuid
import bleach
from PIL import Image
from datetime import datetime
from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'blockquote', 'a', 'img', 'table', 'tr', 'td', 'th',
    'thead', 'tbody', 'span', 'div', 'hr', 'code', 'pre'
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'width', 'height', 'class'],
    '*': ['class']
}
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def sanitize_html(content):
    """Sanitize HTML content to prevent XSS"""
    return bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True
    )


def allowed_image(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in current_app.config['ALLOWED_IMAGE_EXTENSIONS']


def allowed_file(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in current_app.config['ALLOWED_FILE_EXTENSIONS']


def save_image(file_obj, subfolder, max_width=1200, max_height=800):
    """Save and optionally resize an uploaded image"""
    if not file_obj or not file_obj.filename:
        return None
    
    orig_filename = file_obj.filename
    if '.' not in orig_filename:
        raise ValueError('Invalid image file.')
    ext = orig_filename.rsplit('.', 1)[1].lower()
    if ext not in current_app.config['ALLOWED_IMAGE_EXTENSIONS']:
        raise ValueError('Unsupported image type.')
    
    # Generate unique filename
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    
    filepath = os.path.join(upload_dir, unique_name)
    
    # Save & resize with Pillow
    try:
        img = Image.open(file_obj)
        
        # Convert RGBA to RGB for JPEG
        if img.mode in ('RGBA', 'P') and ext in ('jpg', 'jpeg'):
            img = img.convert('RGB')
        
        # Resize if too large
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        img.save(filepath, optimize=True, quality=85)
        return unique_name
    except Exception as e:
        print(f"Image save error: {e}")
        # Fallback: save raw
        file_obj.seek(0)
        file_obj.save(filepath)
        return unique_name


def save_file(file_obj, subfolder):
    """Save any file (PDF/Image)"""
    if not file_obj or not file_obj.filename:
        return None, None
    
    orig_filename = file_obj.filename
    if '.' not in orig_filename:
        raise ValueError('Invalid file upload.')
    ext = orig_filename.rsplit('.', 1)[1].lower()
    if ext not in current_app.config['ALLOWED_FILE_EXTENSIONS']:
        raise ValueError('Unsupported file type.')
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    
    filepath = os.path.join(upload_dir, unique_name)
    file_obj.save(filepath)
    
    return unique_name, ext


def delete_file(filename, subfolder):
    """Delete uploaded file"""
    if not filename:
        return False
    
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder, filename)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
    except Exception as e:
        print(f"File delete error: {e}")
    return False


def paginate_query(query, page, per_page):
    """Helper for pagination"""
    return query.paginate(page=page, per_page=per_page, error_out=False)


def get_blood_group_stats():
    """Get donor count per blood group"""
    from app.models import Donor, db
    
    stats = db.session.query(
        Donor.blood_group,
        db.func.count(Donor.id).label('total'),
        db.func.sum(
            db.case((Donor.availability_status == 'available', 1), else_=0)
        ).label('available')
    ).group_by(Donor.blood_group).all()
    
    return {
        s.blood_group: {
            'total': s.total,
            'available': s.available or 0
        }
        for s in stats
    }


def format_nepali_date(dt):
    """Format date for display"""
    if not dt:
        return "N/A"
    if hasattr(dt, 'strftime'):
        return dt.strftime("%B %d, %Y")
    return str(dt)


import time
from functools import wraps
from flask import request, abort
from collections import defaultdict

_rate_limits = defaultdict(list)

def rate_limit(limit=10, window=60, methods=None):
    """
    Rate limiter disabled as per user request to never show 429 errors.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated
    return decorator