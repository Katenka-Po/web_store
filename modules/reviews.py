import os

from flask import redirect, request, url_for, flash
from flask_babel import gettext as _l
from flask_login import current_user
from werkzeug.utils import secure_filename

from modules.db.database import db_session
from modules.db.models import Purchase, Review, PurchaseItem, \
    ReportedReview
from modules.decorators import login_required_with_message


def create_reviews_routes(app):
    @app.route("/review/<int:review_id>/report", methods=["POST"])
    @login_required_with_message(message="You must be logged in to report a review.")
    def report_review(review_id):
        review = Review.query.get(review_id)
        if not review:
            return 404, _l("Review not found")

        explanation = request.form.get("explanation")
        if not explanation:
            flash(_l("Please provide an explanation for reporting the review."), "danger")
            return redirect(url_for("goods_page", id=review.goods_id))
        reported_review = ReportedReview(review_id=review.id, user_id=current_user.id, explanation=explanation)
        db_session.add(reported_review)
        db_session.commit()
        flash(_l("Review reported. Thank you for your feedback."), "success")
        return redirect(url_for("goods_page", id=review.goods_id))

    @app.route("/add-review", methods=["POST"])
    @login_required_with_message(message="You must be logged in to review a product.")
    def add_review():
        user_id = current_user.id
        goods_id = request.form["goods_id"]
        rating = request.form["rating"]
        review_text = request.form["review"]
        title = request.form["title"]
        pros = request.form["pros"]
        cons = request.form["cons"]

        if not has_purchased(user_id, goods_id):
            flash(_l("You must purchase the product before reviewing it."), "danger")
            return redirect(url_for('goods_page', id=goods_id))

        existing_review = Review.query.filter_by(user_id=user_id, goods_id=goods_id).first()
        if existing_review:
            flash(_l("You have already reviewed this product."), "danger")
            return redirect(url_for('goods_page', id=goods_id))

        images = []
        for file in request.files.getlist('images'):
            if file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['REVIEW_PICS_FOLDER'], filename)
                file.save(file_path)
                images.append(filename)

        new_review = Review(user_id=user_id, goods_id=goods_id, rating=rating, review=review_text,
                            title=title, pros=pros, cons=cons, images=','.join(images))
        db_session.add(new_review)
        db_session.commit()

        flash(_l("Your review has been added!"), "success")
        return redirect(url_for('goods_page', id=goods_id))


def has_purchased(user_id, goods_id):
    purchase_item = PurchaseItem.query.join(Purchase).filter(
        Purchase.user_id == user_id,
        PurchaseItem.goods_id == goods_id
    ).first()
    return purchase_item is not None
