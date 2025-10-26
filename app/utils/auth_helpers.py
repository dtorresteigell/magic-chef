from functools import wraps
from flask import session, redirect, url_for, flash
from itsdangerous import URLSafeTimedSerializer
from flask import current_app
from flask_babel import gettext as _

def generate_reset_token(user_id, expires_sec=3600):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(user_id, salt='password-reset-salt')

def verify_reset_token(token, max_age=3600):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        user_id = s.loads(token, salt='password-reset-salt', max_age=max_age)
    except:
        return None
    return user_id

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash(_("Please log in first."), "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
