import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from config import config
from flask_migrate import Migrate

# एक्सटेन्सनहरू सुरुमै सिर्जना गर्ने (Global instance)
csrf = CSRFProtect()
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'admin.login'
login_manager.login_message = 'Please log in to access the admin panel.'
login_manager.login_message_category = 'warning'
migrate = Migrate()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])
    if hasattr(config[config_name], 'init_app'):
        config[config_name].init_app(app)
    
    # एक्सटेन्सनहरू एप्लिकेसनसँग जोड्ने (Initialize extensions)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # अपलोड फोल्डरहरू स्वतः सिर्जना गर्ने (तस्बिरको सुरक्षाको लागि)
    _create_upload_dirs(app)
    
    with app.app_context():
        # मोडेलहरू इम्पोर्ट गर्ने (डाटाबेस माइग्रेसनको लागि अनिवार्य)
        from app import models
        
        # टेबलहरू सिर्जना गर्ने
        db.create_all()
        
        # सिड एडमिन अकाउन्ट बनाउने
        _seed_admin(app)
        
        # ब्लुप्रिन्टहरू (Blueprints) इम्पोर्ट र रजिस्टर गर्ने (Circular Import नहुने सुरक्षित तरिका)
        from app.routes.public import public_bp
        from app.routes.admin import admin_bp
        from app.routes.api import api_bp
        
        app.register_blueprint(public_bp)
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.register_blueprint(api_bp, url_prefix='/api/v1')
        
        # एरर ह्यान्डलरहरू सुचारु गर्ने
        _register_error_handlers(app)
        
        # कन्टेक्स्ट प्रोसेसरहरू सुचारु गर्ने (ग्लोबल डाटाहरूको लागि)
        _register_context_processors(app)
    
    return app


def _create_upload_dirs(app):
    # 'stories' फोल्डर यहाँ थपिएको छ ता कि सफलताका कथाहरूको फोटो सुरक्षित रहन सकोस्
    dirs = ['news', 'notices', 'ads', 'general', 'stories']
    for d in dirs:
        path = os.path.join(app.config['UPLOAD_FOLDER'], d)
        os.makedirs(path, exist_ok=True)


def _seed_admin(app):
    from app.models import User
    from werkzeug.security import generate_password_hash
    
    admin_username = os.environ.get('ADMIN_USERNAME')
    admin_password = os.environ.get('ADMIN_PASSWORD')
    
    if admin_username and admin_password:
        if not User.query.filter_by(username=admin_username).first():
            admin = User(
                username=admin_username,
                email=os.environ.get('ADMIN_EMAIL', 'admin@nepaliblooddonors.org'),
                full_name=os.environ.get('ADMIN_FULL_NAME', 'Super Admin'),
                role='superadmin',
                password_hash=generate_password_hash(admin_password)
            )
            db.session.add(admin)
            db.session.commit()
            print(f"✅ Admin created: {admin_username}")


def _register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(413)
    def too_large(e):
        from flask import flash, redirect, url_for
        flash('File too large. Maximum size is 16MB.', 'danger')
        return redirect(url_for('public.index'))


def _register_context_processors(app):
    @app.context_processor
    def inject_globals():
        from app.models import Notice, Advertisement, SiteVisitor
        from datetime import datetime
        from flask import request
        
        # भिजिटर ट्र्याकिङ प्रणाली (Visitor Tracking)
        try:
            visitor_ip = request.remote_addr
            today = datetime.utcnow().date()
            existing = SiteVisitor.query.filter_by(
                ip_address=visitor_ip,
                visit_date=today
            ).first()
            if not existing:
                new_visitor = SiteVisitor(
                    # pyrefly: ignore [unexpected-keyword]
                    ip_address=visitor_ip,
                    # pyrefly: ignore [unexpected-keyword]
                    visit_date=today,
                    # pyrefly: ignore [unexpected-keyword]
                    user_agent=request.headers.get('User-Agent', '')[:255]
                )
                db.session.add(new_visitor)
                db.session.commit()
        except Exception:
            db.session.rollback()
            pass
        
        # सक्रिय सूचनाहरू (Active Notices)
        active_notices = Notice.query.filter(
            Notice.is_active == True,
            (Notice.expiry_date == None) | (Notice.expiry_date >= datetime.utcnow())
        ).order_by(Notice.published_date.desc()).limit(5).all()
        
        # साइडबार विज्ञापनहरू (Active Sidebar Ads)
        sidebar_ads = Advertisement.query.filter(
            Advertisement.is_active == True,
            Advertisement.ad_type == 'sidebar',
            (Advertisement.end_date == None) | (Advertisement.end_date >= datetime.utcnow())
        ).all()
        
        return dict(
            site_name=app.config['SITE_NAME'],
            site_tagline=app.config['SITE_TAGLINE'],
            ga_tracking_id=app.config['GA_TRACKING_ID'],
            contact_email=app.config.get('CONTACT_EMAIL', ''),
            active_notices=active_notices,
            sidebar_ads=sidebar_ads,
            current_year=datetime.utcnow().year
        )


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))