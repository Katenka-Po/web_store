from flask import redirect, render_template, request, flash, url_for
from flask_babel import gettext as _l
from flask_login import login_user, logout_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer as Serializer
from itsdangerous.exc import BadSignature, SignatureExpired
import bcrypt

from forms.forms import RegistrationForm, LoginForm
from modules.db.database import db_session
from modules.db.models import User
from modules.decorators import login_required_with_message


def create_auth_routes(app, limiter):
    @app.route("/register", methods=['GET', 'POST'])
    def register():
        form = RegistrationForm()
        if form.validate_on_submit():
            existing_user = db_session.query(User.id).filter_by(username=form.username.data).first()
            if existing_user:
                flash(_l("Username already exists. Please choose a different one."), "danger")
            else:
                hashed_password = bcrypt.hashpw(form.password.data.encode('utf-8'), bcrypt.gensalt())
                new_user = User(username=form.username.data, password=hashed_password.decode('utf-8'),
                                email=form.email.data, is_admin=True)
                db_session.add(new_user)
                db_session.commit()
                db_session.flush()
                flash(_l("Registration successful. Please log in."), "success")
                return redirect(url_for('login'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Error in the {getattr(form, field).label.text} field - {error}", "danger")
        return render_template("register.html", form=form)

    @app.route("/login", methods=['GET', 'POST'])
    @limiter.limit("10 per minute")
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            user = db_session.query(User).filter_by(username=form.username.data).first()
            if user and bcrypt.checkpw(form.password.data.encode('utf-8'), user.password.encode('utf-8')):
                db_session.refresh(user)
                login_user(user)
                flash(_l("Login successful."), "success")
                return redirect(url_for('index'))
            else:
                flash(_l("Invalid username or password."), "danger")
        return render_template("login.html", form=form)

    @app.route("/logout")
    @login_required_with_message(message="You must be logged in to log out.", category="danger")
    def logout():
        logout_user()
        flash(_l("You have been logged out."), "success")
        return redirect(url_for('index'))

    @app.route('/reset_password', methods=['GET', 'POST'])
    def reset_password():
        if request.method == 'POST':
            email = request.form['email']
            user = User.query.filter_by(email=email).first()
            if user:
                s = Serializer(app.config['SECRET_KEY'], str(1800))  
                token = s.dumps({'user_id': user.id})

                msg = Message('Password Reset Request',
                              sender=app.config['MAIL_DEFAULT_SENDER'],
                              recipients=[user.email])
                reset_url = url_for('reset_password_token', token=token, _external=True)
                msg.body = f'''To reset your password, visit the following link:
                    {reset_url}

                    If you did not make this request, simply ignore this email and no changes will be made.
                    '''

              
                flash(_l('Sending email is disabled for now.'), 'warning')
            else:
                flash(_l('No account found with that email.'), 'warning')
        return render_template('reset_password.html')

    @app.route('/reset_password/<token>', methods=['GET', 'POST'])
    def reset_password_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except SignatureExpired:
            flash(_l('The password reset token has expired.'), 'danger')
            return redirect(url_for('reset_password'))
        except BadSignature:
            flash(_l('Invalid token.'), 'danger')
            return redirect(url_for('reset_password'))

        user = User.query.get(data['user_id'])
        if not user:
            flash(_l('Invalid user.'), 'danger')
            return redirect(url_for('reset_password'))

        if request.method == 'POST':
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']
            if new_password == confirm_password:
                user.password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                db_session.commit()
                flash(_l('Your password has been reset. You can now log in with the new password.'), 'success')
                return redirect(url_for('login'))
            else:
                flash(_l('Passwords do not match.'), 'danger')

        return render_template('reset_password_token.html')