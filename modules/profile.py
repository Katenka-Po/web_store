import os

import phonenumbers
from flask import render_template, request, flash, redirect, url_for
from flask_babel import gettext as _l
from flask_dance.contrib.facebook import facebook
from flask_dance.contrib.google import google
from flask_login import current_user, login_required, login_user
from phonenumbers import NumberParseException
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from modules.db.database import db_session
from modules.db.models import User, Address, Notification, SocialAccount
from modules.decorators import login_required_with_message


def create_profile_routes(app):
    @app.route('/profile', methods=['GET', 'POST'])
    @login_required_with_message(message="You must be logged in to open profile.")
    def profile():
        if request.method == 'POST':
            if 'change_email' in request.form:
                new_email = request.form['email'].strip()
                if new_email and new_email != current_user.email:
                    existing_user = db_session.query(User).filter_by(email=new_email).first()
                    if not existing_user:
                        current_user.email = new_email
                        db_session.commit()
                        flash(_l('Email changed successfully.'), 'success')
                    else:
                        flash(_l('This email is already in use.'), 'warning')
                else:
                    flash(_l('New email is either empty or same as previous one.'), 'warning')

            elif 'change_password' in request.form:
                current_password = request.form['current_password']
                new_password = request.form['new_password']
                confirm_password = request.form['confirm_password']
                if check_password_hash(current_user.password, current_password):
                    if new_password and new_password == confirm_password:
                        current_user.password = generate_password_hash(new_password)
                        db_session.commit()
                        flash(_l('Password changed successfully.'), 'success')
                    else:
                        flash(_l('The new password and confirmation do not match.'), 'danger')
                else:
                    flash(_l('Incorrect current password.'), 'danger')

            elif 'change_phone' in request.form:
                new_phone = request.form['phone'].strip()
                if new_phone and new_phone != current_user.phone:
                    try:
                        phone_number = phonenumbers.parse(new_phone, None)
                        if not phonenumbers.is_valid_number(phone_number):
                            raise NumberParseException(0, "Invalid phone number")

                        current_user.phone = new_phone
                        db_session.commit()
                        flash(_l('Phone number successfully changed.'), 'success')
                    except NumberParseException:
                        flash(_l('Invalid phone number format.'), 'danger')
                else:
                    flash(_l('The new phone number matches the current one or is empty.'), 'warning')

            elif 'update_profile' in request.form:
                current_user.fname = request.form['fname']
                current_user.lname = request.form['lname']
                current_user.phone = request.form['phone']
                if 'profile_picture' in request.files:
                    file = request.files['profile_picture']
                    if file.filename != '':
                        _, extension = os.path.splitext(file.filename)
                        extension = extension.lower()

                        if extension in app.config['IMG_FORMATS']:
                            filename = secure_filename(file.filename)
                            os.makedirs(app.config['PROFILE_PICS_FOLDER'], exist_ok=True)
                            file.save(os.path.join(app.config['PROFILE_PICS_FOLDER'], filename))
                            current_user.profile_picture = filename
                        else:
                            flash(_l('Invalid file type. Only PNG, JPG, and BMP files are allowed.'), 'danger')
                db_session.commit()
                flash(_l('Profile updated successfully.'), 'success')

            elif 'change_language' in request.form:
                language = request.form['language']
                current_user.language = language
                db_session.commit()
                flash(_l('Language changed successfully.'), 'success')

            elif 'update_notification_settings' in request.form:
                current_user.notifications_enabled = 'notifications_enabled' in request.form
                current_user.email_notifications_enabled = 'email_notifications_enabled' in request.form
                db_session.commit()
                flash(_l('Notification settings updated successfully.'), 'success')

            else:
                flash(_l('Invalid request.'), 'danger')

        lang_names = app.config['LANGUAGE_NAMES']
        return render_template('profile.html', user=current_user, languages=app.config['LANGUAGES'],
                               lang_names=lang_names)

    @app.route('/notifications')
    @login_required
    def notifications():
        notifications = db_session.query(Notification).filter_by(user_id=current_user.id).order_by(
            Notification.created_at.desc()).all()
        return render_template('notifications.html', notifications=notifications)

    @app.route('/notifications/<int:notification_id>/mark-as-read', methods=['POST'])
    @login_required
    def mark_notification_as_read(notification_id):
        notification = db_session.query(Notification).get(notification_id)
        if not notification:
            flash(_l('Notification not found.'), 'danger')
            return redirect(url_for('notifications'))
        if notification.user_id != current_user.id:
            flash(_l('You do not have permission to mark this notification as read.'), 'danger')
            return redirect(url_for('profile'))
        notification.read = True
        db_session.commit()
        return redirect(url_for('notifications'))

    @app.route('/add-address', methods=['GET', 'POST'])
    @login_required_with_message(message="You must be logged in to add an address.")
    def add_address():
        if request.method == 'POST':
            address_line1 = request.form.get('address_line1')
            address_line2 = request.form.get('address_line2')
            city = request.form.get('city')
            state = request.form.get('state')
            zip_code = request.form.get('zip_code')
            country = request.form.get('country')

            existing_address = db_session.query(Address).filter_by(
                user_id=current_user.id,
                address_line1=address_line1,
                address_line2=address_line2,
                city=city,
                state=state,
                zip_code=zip_code,
                country=country
            ).first()

            if existing_address:
                flash(_l('This address has already been added.'), 'warning')
                return redirect(url_for('profile'))
            new_address = Address(
                user_id=current_user.id,
                address_line1=address_line1,
                address_line2=address_line2,
                city=city,
                state=state,
                zip_code=zip_code,
                country=country
            )
            db_session.add(new_address)
            db_session.commit()
            flash(_l('Address added successfully.'), 'success')

            return redirect(url_for('profile'))

        return render_template('add_address.html')

    @app.route('/addresses/edit/<int:address_id>', methods=['GET', 'POST'])
    @login_required
    def edit_address(address_id):
        address = db_session.query(Address).get(address_id)
        if not address:
            flash(_l('Address not found.'), 'danger')
            return redirect(url_for('profile'))
        if address.user_id != current_user.id:
            flash(_l('You do not have permission to edit this address.'), 'danger')
            return redirect(url_for('addresses'))
        if request.method == 'POST':
            address.address_line1 = request.form['address_line1']
            address.address_line2 = request.form['address_line2']
            address.city = request.form['city']
            address.state = request.form['state']
            address.zip_code = request.form['zip_code']
            address.country = request.form['country']
            db_session.commit()
            flash(_l('Address updated successfully.'), 'success')
            return redirect(url_for('profile'))
        return render_template('edit_address.html', address=address)

    @app.route('/addresses/delete/<int:address_id>', methods=['POST'])
    @login_required
    def delete_address(address_id):
        address = db_session.query(Address).get(address_id)
        if not address:
            flash(_l('Address not found.'), 'danger')
            return redirect(url_for('profile'))
        if address.user_id != current_user.id:
            flash(_l('You do not have permission to delete this address.'), 'danger')
        else:
            db_session.delete(address)
            db_session.commit()
            flash(_l('Address deleted successfully.'), 'success')
        return redirect(url_for('profile'))
