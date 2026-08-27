import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from config import config
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from sqlalchemy import inspect, text
from flask_caching import Cache

from flask import g
from flask_sqlalchemy.session import Session

from flask_socketio import SocketIO

class TenantAwareSession(Session):
    def get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
        if mapper is not None:
            bind_key = getattr(mapper.class_, '__bind_key__', None)
            if bind_key == 'tenant':
                if hasattr(g, 'tenant_engine') and g.tenant_engine:
                    return g.tenant_engine
                # Fallback: return main engine so legacy data is still accessible.
                # This allows admin/API routes to work on banks not yet provisioned.
                import logging
                logging.getLogger(__name__).debug(
                    "Tenant model accessed without tenant context — falling back to main DB."
                )
                mapper = None
        return super().get_bind(mapper=mapper, clause=clause, bind=bind, **kwargs)

csrf = CSRFProtect()
db = SQLAlchemy(session_options={"class_": TenantAwareSession})
cache = Cache(config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})
login_manager = LoginManager()
login_manager.login_view = 'admin.login'
login_manager.login_message = 'Please log in to access the admin panel.'
login_manager.login_message_category = 'warning'
migrate = Migrate()
socketio = SocketIO(cors_allowed_origins="*")

try:
    from flask_babel import Babel, gettext as _  # type: ignore[import-untyped]
    has_babel = True
except ImportError:
    has_babel = False
    class Babel:
        def init_app(self, app, **kwargs):
            pass
    def _(text):
        return text

try:
    import nepali_datetime  # type: ignore[import-untyped]
    has_nepali_datetime = True
except ImportError:
    has_nepali_datetime = False

import datetime
from datetime import timezone

def get_locale():
    from flask import session, request
    return session.get('lang', request.accept_languages.best_match(['en', 'ne']))

babel = Babel()
scheduler = APScheduler()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])
    if hasattr(config[config_name], 'init_app'):
        config[config_name].init_app(app)
        
    # Logging Configuration
    if not app.debug and not app.testing:
        os.makedirs('logs', exist_ok=True)
        file_handler = RotatingFileHandler('logs/nepali_blood_donors.log', maxBytes=10240000, backupCount=10)

        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('रक्तदान र रक्तदाता startup')
    
    # एक्सटेन्सनहरू एप्लिकेसनसँग जोड्ने (Initialize extensions)
    db.init_app(app)
    migrate.init_app(app, db)  # type: ignore[arg-type]
    login_manager.init_app(app)
    csrf.init_app(app)
    cache.init_app(app)
    babel.init_app(app, locale_selector=get_locale)
    socketio.init_app(app, cors_allowed_origins="*")  # type: ignore[arg-type]
    
    @app.template_filter('to_bs')
    def to_bs_filter(dt):
        if not dt:
            return ""
        if isinstance(dt, datetime.datetime):
            dt_date = dt.date()
        elif isinstance(dt, datetime.date):
            dt_date = dt
        elif isinstance(dt, str):
            try:
                dt_date = datetime.datetime.strptime(dt, '%Y-%m-%d').date()
            except:
                return dt
        else:
            return str(dt)
        if has_nepali_datetime:
            try:
                bs_date = nepali_datetime.date.from_datetime_date(dt_date)
                return bs_date.strftime('%Y-%m-%d')
            except Exception:
                return str(dt)
        return str(dt)
    
    # Initialize and start the APScheduler
    if not app.testing:
        try:
            scheduler.init_app(app)
            scheduler.start()
        except Exception:
            # Ignore if scheduler is already running (e.g. in auto-reloader or CLI)
            pass

    # अपलोड फोल्डरहरू स्वतः सिर्जना गर्ने (तस्बिरको सुरक्षाको लागि)
    _create_upload_dirs(app)
    
    with app.app_context():
        # मोडेलहरू इम्पोर्ट गर्ने (डाटाबेस माइग्रेसनको लागि अनिवार्य)
        from app import models as _models  # noqa: F401 — side-effect import to register all ORM models
        
        db.create_all()
        _ensure_legacy_schema_columns(app)
        
        # सिड एडमिन अकाउन्ट बनाउने
        try:
            _seed_admin(app)
        except Exception:
            pass
        
        # ब्लुप्रिन्टहरू (Blueprints) इम्पोर्ट र रजिस्टर गर्ने (Circular Import नहुने सुरक्षित तरिका)
        from app.routes.public import public_bp
        from app.routes.admin import admin_bp
        from app.routes.api import api_bp
        from app.routes.notifications import notifications_bp
        from app.routes.bloodbank import bloodbank_bp
        from app.routes.seo import seo_bp
        
        app.register_blueprint(public_bp)
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.register_blueprint(api_bp, url_prefix='/api/v1')
        app.register_blueprint(notifications_bp)
        app.register_blueprint(bloodbank_bp, url_prefix='/bloodbank')
        app.register_blueprint(seo_bp)
        
        # Socket.IO Event Handlers
        try:
            from app import sockets as _sockets  # noqa: F401
        except Exception as sock_err:
            app.logger.warning("Failed to import sockets: %s", sock_err)
        
        # एरर ह्यान्डलरहरू सुचारु गर्ने
        _register_error_handlers(app)
        
        # कन्टेक्स्ट प्रोसेसरहरू सुचारु गर्ने (ग्लोबल डाटाहरूको लागि)
        _register_context_processors(app)
        
        # Register render_pagination as a Jinja2 global helper
        from markupsafe import Markup
        from flask import url_for as _url_for

        def render_pagination(pagination, endpoint, **kwargs):
            """Render Bootstrap 5 pagination links for any paginated query."""
            if not pagination or pagination.pages <= 1:
                return Markup('')
            
            pages = pagination.iter_pages(left_edge=1, left_current=2, right_current=2, right_edge=1)
            html = ['<nav aria-label="Page navigation"><ul class="pagination justify-content-center flex-wrap">']
            
            # Previous button
            if pagination.has_prev:
                html.append(
                    f'<li class="page-item"><a class="page-link" href="{_url_for(endpoint, page=pagination.prev_num, **kwargs)}">'
                    f'<i class="fas fa-chevron-left"></i></a></li>'
                )
            else:
                html.append('<li class="page-item disabled"><span class="page-link"><i class="fas fa-chevron-left"></i></span></li>')
            
            for p in pages:
                if p:
                    if p == pagination.page:
                        html.append(f'<li class="page-item active"><span class="page-link">{p}</span></li>')
                    else:
                        html.append(
                            f'<li class="page-item"><a class="page-link" href="{_url_for(endpoint, page=p, **kwargs)}">{p}</a></li>'
                        )
                else:
                    html.append('<li class="page-item disabled"><span class="page-link">…</span></li>')
            
            # Next button
            if pagination.has_next:
                html.append(
                    f'<li class="page-item"><a class="page-link" href="{_url_for(endpoint, page=pagination.next_num, **kwargs)}">'
                    f'<i class="fas fa-chevron-right"></i></a></li>'
                )
            else:
                html.append('<li class="page-item disabled"><span class="page-link"><i class="fas fa-chevron-right"></i></span></li>')
            
            html.append('</ul></nav>')
            return Markup(''.join(html))

        app.jinja_env.globals['render_pagination'] = render_pagination  # type: ignore[assignment]
        
        # Schedule Background Jobs
        if not app.testing:
            from app.tasks import schedule_jobs
            schedule_jobs(app, scheduler)
    
    return app


def _create_upload_dirs(app):
    # 'stories' फोल्डर यहाँ थपिएको छ ता कि सफलताका कथाहरूको फोटो सुरक्षित रहन सकोस्
    dirs = ['news', 'notices', 'ads', 'general', 'stories', 'staff', 'partners', 'request_papers']
    for d in dirs:
        path = os.path.join(app.config['UPLOAD_FOLDER'], d)
        os.makedirs(path, exist_ok=True)


def _ensure_legacy_schema_columns(app):
    try:
        from app.models import (
            User,
            Donor,
            AuditLog,
            BloodBank,
            BloodBankAccount,
            BloodInventory,
            BloodInventoryMovement,
            BloodRequest,
            BloodReservation,
            BloodTransfer,
            LowStockAlert,
            Notification,
            DonorDonationHistory,
            NotificationDeliveryLog,
            DonorNotificationPreference,
            PublicBloodBankCache,
            StaffMember,
            BloodBankShift,
            BloodBankShiftAssignment,
            BloodBankNotification,
            BloodBankAlertSettings,
            BloodBankNotificationDelivery,
            Volunteer,
            Partner,
            News,
            Notice,
            Advertisement,
            Contact,
            SuccessStory,
            SiteConfig,
            SiteVisitor,
        )

        db.create_all()
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        model_tables = [
            ('users', User),
            ('donors', Donor),
            ('volunteers', Volunteer),
            ('partners', Partner),
            ('news', News),
            ('notices', Notice),
            ('advertisements', Advertisement),
            ('contacts', Contact),
            ('success_stories', SuccessStory),
            ('blood_requests', BloodRequest),
            ('blood_banks', BloodBank),
            ('blood_bank_accounts', BloodBankAccount),
            ('blood_inventory', BloodInventory),
            ('blood_reservations', BloodReservation),
            ('blood_inventory_movements', BloodInventoryMovement),
            ('blood_transfers', BloodTransfer),
            ('low_stock_alerts', LowStockAlert),
            ('notifications', Notification),
            ('audit_logs', AuditLog),
            ('donor_donation_history', DonorDonationHistory),
            ('notification_delivery_logs', NotificationDeliveryLog),
            ('donor_notification_preferences', DonorNotificationPreference),
            ('public_blood_bank_cache', PublicBloodBankCache),
            ('staff_members', StaffMember),
            ('blood_bank_shifts', BloodBankShift),
            ('blood_bank_shift_assignments', BloodBankShiftAssignment),
            ('blood_bank_notifications', BloodBankNotification),
            ('blood_bank_alert_settings', BloodBankAlertSettings),
            ('blood_bank_notification_deliveries', BloodBankNotificationDelivery),
            ('site_configs', SiteConfig),
            ('site_visitors', SiteVisitor),
        ]

        for table_name, model_cls in model_tables:
            if table_name not in existing_tables:
                continue

            table_columns = {col['name'] for col in inspector.get_columns(table_name)}
            for column in model_cls.__table__.columns:  # type: ignore[attr-defined]
                if column.name not in table_columns:
                    try:
                        # Compile type according to the active database dialect (e.g. BYTEA on PostgreSQL, BLOB on SQLite)
                        try:
                            sql_type = str(column.type.compile(db.engine.dialect))
                        except Exception:
                            is_pg = (db.engine.name == 'postgresql')
                            col_type_str = str(column.type).upper()
                            if "VARCHAR" in col_type_str or "STRING" in col_type_str:
                                length = getattr(column.type, 'length', 255) or 255
                                sql_type = f"VARCHAR({length})"
                            elif "TEXT" in col_type_str:
                                sql_type = "TEXT"
                            elif "INTEGER" in col_type_str or "INT" in col_type_str:
                                sql_type = "INTEGER"
                            elif "BOOLEAN" in col_type_str or "BOOL" in col_type_str:
                                sql_type = "BOOLEAN"
                            elif "DATETIME" in col_type_str or "TIMESTAMP" in col_type_str:
                                sql_type = "TIMESTAMP"
                            elif "BLOB" in col_type_str or "LARGEBINARY" in col_type_str or "LARGE_BINARY" in col_type_str or "BYTEA" in col_type_str:
                                sql_type = "BYTEA" if is_pg else "BLOB"
                            elif "FLOAT" in col_type_str or "REAL" in col_type_str:
                                sql_type = "REAL"
                            elif "DATE" in col_type_str:
                                sql_type = "DATE"
                            else:
                                sql_type = "VARCHAR(255)"
                        
                        # Always add as nullable to avoid CockroachDB/PG rejection
                        # of NOT NULL columns on tables with existing rows.
                        db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column.name} {sql_type} NULL"))
                        db.session.commit()
                        # Apply default value for known sentinel columns
                        default_val = None
                        col_default = getattr(column, 'default', None)
                        if col_default is not None and hasattr(col_default, 'arg') and not callable(col_default.arg):
                            default_val = col_default.arg
                        if default_val is None:
                            col_type_upper = str(column.type).upper()
                            if 'BOOL' in col_type_upper:
                                default_val = 'FALSE'
                            elif 'INT' in col_type_upper:
                                default_val = 0
                        if default_val is not None:
                            db.session.execute(text(f"UPDATE {table_name} SET {column.name} = :v WHERE {column.name} IS NULL"), {'v': default_val})
                            db.session.commit()
                        print(f"[SCHEMA] Successfully added missing column '{column.name}' ({sql_type}) to table '{table_name}'.")
                    except Exception as col_err:
                        db.session.rollback()
                        print(f"[WARN] Failed to add column {column.name} to {table_name}: {col_err}")

        # Ensure donors.email is nullable on PostgreSQL and SQLite
        if 'donors' in existing_tables:
            try:
                if db.engine.name == 'postgresql':
                    db.session.execute(text("ALTER TABLE donors ALTER COLUMN email DROP NOT NULL;"))
                    db.session.commit()
                elif db.engine.name == 'sqlite':
                    cols = inspector.get_columns('donors')
                    email_col = next((c for c in cols if c['name'] == 'email'), None)
                    if email_col and not email_col.get('nullable', True):
                        import re
                        db.session.execute(text("PRAGMA foreign_keys=OFF;"))
                        create_sql = db.session.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='donors'")).scalar()
                        if create_sql:
                            new_sql = re.sub(r'email\s+VARCHAR\(\d+\)\s+NOT\s+NULL', 'email VARCHAR(120)', create_sql, flags=re.IGNORECASE)
                            new_sql = re.sub(r'email\s+VARCHAR\s+NOT\s+NULL', 'email VARCHAR(120)', new_sql, flags=re.IGNORECASE)
                            new_sql = new_sql.replace('CREATE TABLE donors', 'CREATE TABLE donors_migrated', 1).replace('CREATE TABLE "donors"', 'CREATE TABLE "donors_migrated"', 1)
                            db.session.execute(text(new_sql))
                            db.session.execute(text("INSERT INTO donors_migrated SELECT * FROM donors;"))
                            db.session.execute(text("DROP TABLE donors;"))
                            db.session.execute(text("ALTER TABLE donors_migrated RENAME TO donors;"))
                            db.session.execute(text("PRAGMA foreign_keys=ON;"))
                            db.session.commit()
                            print("[SCHEMA] Successfully migrated SQLite donors table to make email nullable.")
            except Exception as e:
                db.session.rollback()
                print(f"[WARN] Failed to make donors.email nullable: {e}")

    except Exception as exc:
        db.session.rollback()
        print(f"[WARN] Failed to ensure legacy schema columns: {exc}")


def _seed_admin(app):
    from app.models import User, BloodBank
    from werkzeug.security import generate_password_hash
    from app.seed_blood_banks import seed_blood_banks
    
    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'Admin@1234')
    
    if admin_username and admin_password:
        user = User.query.filter_by(username=admin_username).first()
        if not user:
            admin = User(
                username=admin_username,
                email=os.environ.get('ADMIN_EMAIL', 'admin@nepaliblooddonors.org'),
                full_name=os.environ.get('ADMIN_FULL_NAME', 'Super Admin'),
                role='superadmin',
                is_active=True,
                password_hash=generate_password_hash(admin_password)
            )
            db.session.add(admin)
            db.session.commit()
            print(f"[OK] Admin created: {admin_username}")
        else:
            user.is_active = True
            user.password_hash = generate_password_hash(admin_password)
            db.session.commit()
            print(f"[OK] Admin password updated: {admin_username}")

    if not BloodBank.query.first():
        inserted_count = seed_blood_banks()
        if inserted_count == 0:
            default_bank = BloodBank(
                name='Nepal Red Cross Blood Bank',
                hospital_name='Central Blood Transfusion Service',
                province='Bagmati Pradesh',
                district='Kathmandu',
                city='Kathmandu',
                service_type='National Center',
                phone='+977-1-4423000',
                email='info@nrcs.org',
                emergency_available=True,
                is_active=True,
                status='active',
            )
            db.session.add(default_bank)
            db.session.commit()


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

    @app.errorhandler(429)
    def too_many_requests(e):
        from flask import render_template
        return render_template('errors/429.html'), 429

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template('errors/403.html'), 403

    # ── Site Visitor Tracking (Accurate Page Views & Unique Visitors) ──
    @app.before_request
    def track_site_visitor():
        from flask import request
        if request.method != 'GET':
            return
        path = request.path
        # Ignore static assets, icons, service workers, and telemetry polls
        if (path.startswith('/static') or 
            path.startswith('/api/v1/stats') or
            path == '/health' or 
            path == '/favicon.ico' or 
            path == '/sw.js' or 
            path == '/robots.txt' or 
            path == '/manifest.json' or
            path.startswith('/socket.io')):
            return
            
        if not app.testing:
            from app.models import SiteVisitor, db
            from datetime import datetime, timezone
            try:
                # Accurately extract client IP (supporting reverse proxies & Cloudflare)
                visitor_ip = (
                    request.headers.get('CF-Connecting-IP') or 
                    request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or 
                    request.remote_addr or 
                    '127.0.0.1'
                )[:45]
                
                now_utc = datetime.now(timezone.utc)
                today = now_utc.date()
                ua = (request.headers.get('User-Agent') or '')[:255]
                
                existing = SiteVisitor.query.filter_by(
                    ip_address=visitor_ip,
                    visit_date=today
                ).first()
                
                if existing:
                    existing.hits = (existing.hits or 1) + 1
                    existing.page_url = path[:500]
                    existing.updated_at = now_utc
                    if ua and not existing.user_agent:
                        existing.user_agent = ua
                else:
                    new_visitor = SiteVisitor(
                        ip_address=visitor_ip,
                        visit_date=today,
                        user_agent=ua,
                        page_url=path[:500],
                        hits=1,
                        created_at=now_utc,
                        updated_at=now_utc
                    )
                    db.session.add(new_visitor)
                db.session.commit()
            except Exception:
                db.session.rollback()

    # ── Security Headers ──────────────────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(self), microphone=(), camera=()'
        # Only add HSTS in production
        if not app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response


def _register_context_processors(app):
    @app.context_processor
    def inject_globals():
        from app.models import Notice, Advertisement, SiteVisitor, db
        from sqlalchemy import func
        from datetime import datetime, timezone
        
        now_utc = datetime.now(timezone.utc)
        today = now_utc.date()

        # भिजिटर मेट्रिक्स (Live Visitor Metrics from Database)
        total_site_visits = 0
        total_unique_visitors = 0
        today_visitors = 0
        try:
            total_site_visits = db.session.query(func.coalesce(func.sum(SiteVisitor.hits), 0)).scalar() or 0
            total_unique_visitors = SiteVisitor.query.count()
            today_visitors = SiteVisitor.query.filter_by(visit_date=today).count()
        except Exception:
            pass
        
        # सक्रिय सूचनाहरू (Active Notices)
        active_notices = Notice.query.filter(
            Notice.is_active == True,
            (Notice.expiry_date == None) | (Notice.expiry_date >= now_utc)
        ).order_by(Notice.published_date.desc()).limit(5).all()
        
        # साइडबार विज्ञापनहरू (Active Sidebar Ads)
        sidebar_ads = Advertisement.query.filter(
            Advertisement.is_active == True,
            Advertisement.ad_type == 'sidebar',
            (Advertisement.end_date == None) | (Advertisement.end_date >= now_utc)
        ).all()
        
        return dict(
            site_name=app.config['SITE_NAME'],
            site_tagline=app.config['SITE_TAGLINE'],
            ga_tracking_id=app.config['GA_TRACKING_ID'],
            contact_email=app.config.get('CONTACT_EMAIL', ''),
            active_notices=active_notices,
            sidebar_ads=sidebar_ads,
            current_year=now_utc.year,
            total_site_visits=total_site_visits,
            total_unique_visitors=total_unique_visitors,
            today_visitors=today_visitors,
        )
    
    @app.context_processor
    def inject_translations():
        from flask import session
        from app.translations import get_translation
        lang = session.get('lang', 'en')
        
        class TranslationDict:
            """Allows dot-access (t.home) and bracket-access (t['home']) with fallback."""
            def __init__(self, data):
                self._data = data
            def __getattr__(self, key):
                return self._data.get(key, key)
            def __getitem__(self, key):
                return self._data.get(key, key)
            def get(self, key, default=None):
                return self._data.get(key, default or key)
        
        return dict(
            t=TranslationDict(get_translation(lang)),
            current_lang=lang
        )


@login_manager.unauthorized_handler
def handle_unauthorized():
    """Smart redirect: send each user type to the correct login page."""
    from flask import request as _req, redirect as _redir, url_for as _url_for, flash as _flash
    path = _req.path or ''
    if path.startswith('/donor'):
        _flash('Please log in to access your donor account.', 'warning')
        return _redir(_url_for('public.donor_login'))
    elif path.startswith('/bloodbank') or path.startswith('/blood-bank'):
        _flash('Please log in to access the blood bank dashboard.', 'warning')
        return _redir(_url_for('bloodbank.login'))
    elif path.startswith('/volunteer'):
        _flash('Please log in to access the volunteer portal.', 'warning')
        return _redir(_url_for('public.volunteer_login'))
    else:
        _flash('Please log in to access the admin panel.', 'warning')
        return _redir(_url_for('admin.login'))


@login_manager.user_loader
def load_user(user_id):
    from app.models import User, Donor, Volunteer
    try:
        parts = str(user_id).split('_')
        if len(parts) == 2:
            model_type, model_id = parts[0], int(parts[1])
            if model_type == 'user':
                return User.query.get(model_id)
            elif model_type == 'donor':
                return Donor.query.get(model_id)
            elif model_type == 'volunteer':
                return Volunteer.query.get(model_id)
        # Fallback for old sessions that might just have integer IDs
        return User.query.get(int(user_id))
    except Exception:
        return None