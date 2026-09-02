import os
from typing import Any
from datetime import timedelta
from dotenv import load_dotenv
try:
    from sqlalchemy.pool import StaticPool
    _has_static_pool = True
except ImportError:
    _has_static_pool = False

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)


def _is_cockroachdb_url(url: str) -> bool:
    """Detect CockroachDB connection URLs by host pattern or explicit scheme."""
    return (
        url.startswith('cockroachdb')
        or 'cockroachlabs.cloud' in url
        or 'cockroachdb' in url.lower()
    )


def get_database_uri() -> str:
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        instance_db = os.path.join(INSTANCE_DIR, 'nepali_blood.db')
        return f"sqlite:///{instance_db}"

    # Fix Render/Heroku legacy postgres:// prefix → postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # Clean quotes/spaces and fix common AWS/Neon region typos (e.g. ap-southeast1 -> ap-southeast-1)
    db_url = db_url.strip().strip("'\"")
    if ".ap-southeast1.aws.neon.tech" in db_url:
        db_url = db_url.replace(".ap-southeast1.aws.neon.tech", ".ap-southeast-1.aws.neon.tech")

    # Rewrite postgresql:// → cockroachdb+psycopg2:// for CockroachDB hosts.
    # SQLAlchemy's built-in PostgreSQL dialect cannot parse CockroachDB version
    # strings (e.g. 'CockroachDB CCL v26.2.5 ...'), causing an AssertionError.
    # Using the sqlalchemy-cockroachdb dialect avoids this entirely.
    if _is_cockroachdb_url(db_url):
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "cockroachdb+psycopg2://", 1)
        elif db_url.startswith("cockroachdb://"):
            db_url = db_url.replace("cockroachdb://", "cockroachdb+psycopg2://", 1)
        return db_url

    if db_url.startswith("sqlite:///"):
        sqlite_path = db_url.replace("sqlite:///", "")
        if sqlite_path and sqlite_path != ":memory:":
            abs_path = os.path.abspath(sqlite_path)
            parent_dir = os.path.dirname(abs_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            return f"sqlite:///{abs_path}"

    return db_url


def get_engine_options() -> dict[str, Any]:
    """Return SQLAlchemy engine options. Enforce connection pooling and automatic reconnects for CockroachDB / PostgreSQL."""
    db_url = os.environ.get('DATABASE_URL', '')
    if any(db_url.startswith(prefix) for prefix in ('postgresql', 'postgres', 'cockroachdb')):
        options: dict[str, Any] = {
            'pool_pre_ping': True,  # Automatically reconnects if connection drops
            'pool_recycle': 300,
        }
        # Enforce SSL if not already explicitly stated in the URL
        if 'sslmode' not in db_url:
            options['connect_args'] = {'sslmode': 'require'}
        return options
    # SQLite: Enable pool_pre_ping for resilient connections
    return {'pool_pre_ping': True}


class Config:
    # Core
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-me'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = get_engine_options()
    SQLALCHEMY_BINDS = {
        'tenant': get_database_uri()
    }


    
    # Session (Permanent login for donors)
    PERMANENT_SESSION_LIFETIME = timedelta(days=365)
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=365)
    REMEMBER_COOKIE_REFRESH_EACH_REQUEST = True
    
    # CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    
    # Uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_FILE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}
    
    # Pagination
    DONORS_PER_PAGE = 12
    REQUESTS_PER_PAGE = 10
    NEWS_PER_PAGE = 6
    
    # Analytics
    GA_TRACKING_ID = os.environ.get('GA_TRACKING_ID', '')
    
    # Site Info
    SITE_NAME = "रक्तदान र रक्तदाता"
    SITE_TAGLINE = "Donate Blood, Save Lives"
    CONTACT_EMAIL = "info@nepaliblooddonors.org"
    CONTACT_PHONE = "+977 9816003020"
    CONTACT_ADDRESS = "Jhapa, Nepal"
    
    # Scheduler
    SCHEDULER_API_ENABLED = True
    
    # AI / Generative services
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        if app.config['SECRET_KEY'] == 'dev-secret-key-change-me':
            raise RuntimeError('SECRET_KEY must be set to a secure value in production.')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_BINDS = {
        'tenant': 'sqlite:///:memory:'
    }
    WTF_CSRF_ENABLED = False



config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}