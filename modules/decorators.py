from functools import wraps

from flask import flash, redirect, request, url_for
from flask_babel import gettext as _l
from flask_login import current_user


def login_required_with_message(message=_l("You must be logged in to view this page."), category="danger",
                                redirect_back=False):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash(message, category)
                if redirect_back:
                    referrer = request.headers.get("Referer")
                    if referrer:
                        return redirect(referrer)
                    else:
                        return redirect(url_for('index'))
                else:
                    return redirect(url_for('index'))
            return f(*args, **kwargs)

        return decorated_function

    return decorator

def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("You don't have permission to access this page.", "warning")
            return redirect(url_for("index"))
        return func(*args, **kwargs)
    return decorated_view