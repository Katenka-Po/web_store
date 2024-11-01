import json

from flask import redirect, request, url_for, flash, render_template
from flask_babel import gettext as _l
from flask_login import current_user

from modules.db.database import db_session
from modules.db.models import Goods, ComparisonHistory
from modules.decorators import login_required_with_message


def create_compare_routes(app):
    @app.route("/compare")
    @login_required_with_message()
    def compare_products():
       
        comparison_history = ComparisonHistory.query.filter_by(user_id=current_user.id).first()

        if comparison_history:
            product_ids = json.loads(comparison_history.product_ids)
            products = db_session.query(Goods).filter(Goods.id.in_(product_ids)).all()
        else:
            products = []

        return render_template("product_comparison.html", products=products)

    @app.route("/remove-from-comparison", methods=["POST"])
    @login_required_with_message()
    def remove_from_comparison():
       
        goods_id = request.form.get("goods_id")
        comparison_history = db_session.query(ComparisonHistory).filter_by(user_id=current_user.id).first()

        if comparison_history:
            product_ids = json.loads(comparison_history.product_ids)
            if goods_id in product_ids:
                product_ids.remove(goods_id)
                if product_ids:
                    comparison_history.product_ids = json.dumps(product_ids)
                else:
                    db_session.delete(comparison_history)
                db_session.commit()
                flash(_l("Product removed from comparison."), "success")
            else:
                flash(_l("Product is not in comparison."), "info")
        else:
            flash(_l("No products in comparison."), "info")

        return redirect(request.referrer or url_for('compare_products'))


def add_to_comparison(goods_id: int):
  
    product = db_session.query(Goods).get(goods_id)

    if product:
        comparison_history = db_session.query(ComparisonHistory).filter_by(user_id=current_user.id).first()

        if comparison_history:
            product_ids = json.loads(comparison_history.product_ids)
            if goods_id not in product_ids:
                if len(product_ids) >= 3:
                    flash(_l("You can only compare up to 3 products at a time."), "warning")
                else:
                    product_ids.append(goods_id)
                    comparison_history.product_ids = json.dumps(product_ids)
                    db_session.commit()
                    flash(_l("Product added to comparison."), "success")
            else:
                flash(_l("Product is already in comparison."), "info")
        else:
            new_comparison_history = ComparisonHistory(user_id=current_user.id, product_ids=json.dumps([goods_id]))
            db_session.add(new_comparison_history)
            db_session.commit()
            flash(_l("Product added to comparison."), "success")
    else:
        flash(_l("Product not found."), "error")

    return redirect(url_for('goods_page', id=goods_id))