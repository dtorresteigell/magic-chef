# app/__init__.py
from flask import Flask, request, session
from flask import current_app
from flask_babel import Babel
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import current_user
from flask_login import LoginManager
from flask_mail import Mail
from sqlalchemy import text
import time
from sqlalchemy.exc import OperationalError
from config import DevConfig, ProdConfig
import logging
from logging.handlers import RotatingFileHandler
import sys
import os

db = SQLAlchemy()
migrate = Migrate()

login_manager = LoginManager()
login_manager.login_view = "auth.login"

# Import all models to ensure they're registered with SQLAlchemy
from app.models import User, Recipe, ChatMessage

mail = Mail()

# Create Babel instance globally (not attached to app yet)
babel = Babel()


def get_locale():
    """Determine which language to use"""
    # 1. Authenticated user? Use their saved preference
    if current_user and current_user.is_authenticated:
        return current_user.language

    # 2. Anonymous user? Check cookie
    language = request.cookies.get("language")
    if language:
        return language

    # 3. Fall back to browser preference
    fallback = request.accept_languages.best_match(["en", "de", "es", "fr"]) or "en"
    return fallback


def wait_for_db(max_attempts=10, delay=1):
    """Wait until database is reachable (used at startup in Docker environments)"""
    for attempt in range(max_attempts):
        try:
            db.session.execute(text("SELECT 1"))
            print("✅ Database is ready.")
            return
        except OperationalError as e:
            print(f"⚠️ Waiting for database... ({attempt + 1}/{max_attempts}) - {e}")
            time.sleep(delay)
    raise RuntimeError("❌ Database not ready after multiple attempts.")


def create_app():
    app = Flask(__name__)
    env = os.environ.get("FLASK_ENV", "development")
    app.config.from_object(ProdConfig if env == "production" else DevConfig)
    mail.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)

    # ADD BABEL CONFIG HERE - AFTER loading config, BEFORE init_app
    app.config["BABEL_DEFAULT_LOCALE"] = "en"
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = "../translations"

    # Initialize Babel with the app
    babel.init_app(app, locale_selector=get_locale)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        wait_for_db()  # ensures Postgres is ready before continuing
        # Create tables if they don't exist yet
        db.create_all()

    # Setup logging
    if not app.debug:
        # Console handler (so Docker logs show it)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
            )
        )
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.INFO)
    else:
        # Debug mode
        app.logger.setLevel(logging.DEBUG)

    app.logger.info("Application startup")

    # Ensure required directories exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["PDF_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(app.instance_path, "..", "data"), exist_ok=True)

    # Register blueprints
    from app.routes import (
        main,
        search,
        pdf,
        ai_recipes,
        table_view,
        digitaliser,
        auth,
        chat,
    )

    app.register_blueprint(main.bp)
    app.register_blueprint(search.bp)
    app.register_blueprint(pdf.bp)
    app.register_blueprint(ai_recipes.bp)
    app.register_blueprint(table_view.bp)
    app.register_blueprint(digitaliser.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(chat.bp)

    # Create database tables
    with app.app_context():
        db.create_all()

    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)

    # @app.context_processor
    # def inject_user():
    #     return dict(current_user=current_user)

    return app
