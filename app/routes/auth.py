# app/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response, current_app
from flask_login import login_user, logout_user, login_required
from app import db, mail
from app.models import User
from app.utils.auth_helpers import generate_reset_token, verify_reset_token
from flask_mail import Message

bp = Blueprint('auth', __name__, url_prefix='/auth')


# -----------------------
# Registration
# -----------------------
@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        password2 = request.form.get('password2')

        if not username or not email or not password:
            flash("Please fill all fields", "error")
            return render_template("auth/register.html")  # no _form

        if password != password2:
            flash("Passwords do not match", "error")
            return render_template("auth/register.html")

        if User.query.filter((User.username==username)|(User.email==email)).first():
            flash("Username or email already exists", "error")
            return render_template("auth/register.html")

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created successfully. Please log in.", "success")

        resp = make_response('', 204)
        resp.headers['HX-Redirect'] = url_for('auth.login')
        return resp

    return render_template("auth/register.html")



# -----------------------
# Login
# -----------------------
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            session['user_id'] = user.id
            session['username'] = user.username

            # HTMX redirect
            resp = make_response('', 204)  # no content
            resp.headers['HX-Redirect'] = url_for('main.index')
            return resp
        else:
            # Invalid login → return login form again (HTMX will swap content)
            flash("Invalid username or password", "error")
            return render_template('auth/login.html')

    return render_template('auth/login.html')


# -----------------------
# Logout
# -----------------------
@bp.route('/logout')
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out", "success")
    return redirect(url_for('main.index'))


# -----------------------
# Request password reset
# -----------------------
@bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_reset_token(user.id)
            reset_url = url_for('auth.reset_password', token=token, _external=True)

            msg = Message(
                subject="Reset Your Password",
                sender=current_app.config['MAIL_USERNAME'],
                recipients=[email]
            )
            msg.body = f"""Hi {user.username},

Click the link below to reset your password:

{reset_url}

If you did not request this, ignore this email.
"""
            mail.send(msg)
            flash("Password reset link sent! Check your email.", "success")
        else:
            flash("Email not found.", "error")

        return render_template('auth/reset_password_request.html')

    return render_template('auth/reset_password_request.html')


# -----------------------
# Reset password with token
# -----------------------
@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user_id = verify_reset_token(token)
    if not user_id:
        flash("Invalid or expired token", "error")
        return redirect(url_for('auth.reset_password_request'))

    user = User.query.get(user_id)
    if request.method == 'POST':
        password = request.form.get('password')
        password2 = request.form.get('password2')

        if not password or password != password2:
            flash("Passwords must match", "error")
            return render_template('auth/reset_password.html', token=token)

        user.set_password(password)
        db.session.commit()
        flash("Your password has been updated!", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)