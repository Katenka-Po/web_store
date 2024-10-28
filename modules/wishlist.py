import json

from flask import redirect
from flask import request, flash, url_for
from flask_babel import gettext as _l
from flask_login import current_user

from modules.db.database import db_session
from modules.db.models import Wishlist
from modules.decorators import login_required_with_message
from modules.email import send_wishlist_notifications


def create_wishlist_routes(app):
    @app.route("/wishlist", methods=["POST"])
    @login_required_with_message(message="You must be logged in to add items to your wishlist.", redirect_back=True)
    def wishlist():
        goods_id = request.form["goods_id"]
        variant_options = request.form.get('variant_options')

        if variant_options:
            variant_options = json.loads(variant_options)
        else:
            variant_options = {}

        variant_options_str = json.dumps(variant_options)

        user_id = current_user.id

        wishlist_item = Wishlist.query.filter_by(user_id=user_id, goods_id=goods_id,
                                                 variant_options=variant_options_str).first()

        if wishlist_item:
            db_session.delete(wishlist_item)
            db_session.commit()
            flash(_l("Product removed from your wishlist."), "success")
        else:
            new_wishlist_item = Wishlist(user_id=user_id, goods_id=goods_id, variant_options=variant_options_str)
            db_session.add(new_wishlist_item)
            db_session.commit()
            flash(_l("Product added to your wishlist!"), "success")

        return redirect(url_for('goods_page', id=goods_id))

    @app.route("/send-wishlist-notifications")
    def send_notifications():
        send_wishlist_notifications()
        flash(_l("Wishlist notifications sent successfully."), "success")
        return redirect(url_for('profile'))
