import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)


def get_database_uri():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        instance_db = os.path.join(INSTANCE_DIR, 'nepali_blood.db')
        return f"sqlite:///{instance_db}"
    
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    if db_url.startswith("sqlite:///"):
        sqlite_path = db_url.replace("sqlite:///", "")
        if sqlite_path and sqlite_path != ":memory:":
            abs_path = os.path.abspath(sqlite_path)
            parent_dir = os.path.dirname(abs_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            return f"sqlite:///{abs_path}"

    return db_url


class Config:
    # Core
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-me'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_BINDS = {
        'tenant': 'sqlite:///:memory:' # Placeholder for dynamic tenant binding
    }

    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    
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
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}