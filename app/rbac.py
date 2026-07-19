from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user, login_required

ROLE_PERMISSIONS = {
    'superadmin': ['*'],
    'admin': [
        'manage_donors', 'manage_requests', 'manage_news', 'manage_notices', 
        'manage_events', 'manage_success_stories', 'moderate_content', 
        'manage_staff', 'manage_partners', 'manage_ads', 'view_analytics', 
        'manage_users', 'manage_blood_banks'
    ],
    'moderator': [
        'manage_donors', 'manage_requests', 'moderate_content', 'view_analytics'
    ],
    'content_manager': [
        'manage_news', 'manage_notices', 'manage_events', 'manage_success_stories', 
        'manage_ads', 'view_analytics'
    ],
    'volunteer': [
        'view_analytics', 'manage_donors', 'manage_requests'
    ]
}

def has_permission(user, permission):
    if not user or not user.is_authenticated:
        return False
    
    role = getattr(user, 'role', None)
    if not role:
        return False
        
    permissions = ROLE_PERMISSIONS.get(role, [])
    if '*' in permissions:
        return True
    return permission in permissions

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not has_permission(current_user, permission):
                flash('🚫 Access Denied: You do not have the required permissions.', 'danger')
                return redirect(url_for('admin.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
