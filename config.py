import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))
        

class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLAlchemy pool options — tune if needed
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        # "pool_size": 5,
        # "max_overflow": 10,
        # "pool_recycle": 280,
    }
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'images', 'recipes')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    PDF_FOLDER = os.path.join(basedir, 'pdfs')

    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = os.getenv("MAIL_PORT", 587)
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

    # Babel configuration
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_TRANSLATION_DIRECTORIES = '../translations'


class DevConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///recipes.db"
    )
    DEBUG = True

class ProdConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]  # must exist in prod
    DEBUG = False
