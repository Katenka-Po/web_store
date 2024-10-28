import json
import logging
import os
from typing import Dict, Union

import sqlalchemy
from flask import Flask
from flask import flash
from flask import g
from flask import jsonify
from flask import redirect, session, url_for
from flask import render_template
from flask import request
from flask_babel import Babel, gettext as _l
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_mail import Mail
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy import exists
from sqlalchemy.orm import joinedload, selectinload
import modules.filter
from config import AppConfig
from modules.admin import create_admin
from modules.auth import create_auth_routes
from modules.cache import cache
from modules.cart import create_cart_routes, add_to_cart, apply_discount_code
from modules.compare import add_to_comparison, create_compare_routes
from modules.db.backup import backup_database
from modules.db.database import init_db
from modules.db.models import *
from modules.decorators import login_required_with_message
from modules.error_handlers import create_error_handlers
from modules.filter import create_filter_routes, get_filter_options, filter_products
from modules.profile import create_profile_routes
from modules.purchase_history import create_purchase_history_routes
from modules.recommendations import get_recommended_products, update_recently_viewed_products
from modules.reviews import create_reviews_routes, has_purchased
from modules.wishlist import create_wishlist_routes
from apscheduler.schedulers.background import BackgroundScheduler


logger = logging.getLogger(__name__)




def setup_template_loader(app: Flask) -> None:
  
    template_dir = app.template_folder
    loaders = [FileSystemLoader(os.path.join(template_dir, ''))]
    for root, dirs, files in os.walk(template_dir):
        for dir_name in dirs:
            loaders.append(FileSystemLoader(os.path.join(root, dir_name)))
    app.jinja_loader = ChoiceLoader(loaders)


def get_locale() -> str:
 
    if current_user.is_authenticated:
        return current_user.language
    return 'ru'


def create_app() -> Flask:
  
    app = Flask(__name__)
    setup_template_loader(app)
    app.secret_key = 'secret_key'
    app.config.from_object(AppConfig)

    init_db()

    babel = Babel(app, locale_selector=get_locale)

    create_error_handlers(app, logger)

    login_manager = LoginManager()
    login_manager.init_app(app)

    mail = Mail(app)

    cache.init_app(app)

    scheduler = BackgroundScheduler()

    scheduler.add_job(backup_database, 'interval', minutes=30, args=[AppConfig.BACKUP_DIR])

    scheduler.start()

    create_profile_routes(app)
    create_auth_routes(app, Limiter(app=app,
                                    key_func=get_remote_address,
                                    default_limits=[AppConfig.DEFAULT_LIMIT_RATE],
                                    storage_uri="memory://"))
    create_cart_routes(app)
    create_purchase_history_routes(app)
    create_filter_routes(app)
    create_wishlist_routes(app)
    create_reviews_routes(app)
    create_compare_routes(app)
    create_admin(app)

    @app.before_request
    def before_request() -> None:
       
        db_session.permanent = True
        app.permanent_session_lifetime = AppConfig.PERMANENT_SESSION_LIFETIME
        db_session.modified = True
        g.total_items, g.total_amount, g.discount_percentage = Cart.cart_info()

        if current_user.is_authenticated:
            g.mini_cart_items = Cart.query.filter_by(user_id=current_user.id).all()
            g.unread_notifications_count = Notification.query.filter_by(user_id=current_user.id, read=False).count()
        else:
            g.mini_cart_items = []
            g.unread_notifications_count = 0

    @app.context_processor
    def inject_cart_info() -> Dict[str, Union[int, float, List, str]]:
      
        return dict(
            total_items=g.total_items,
            total_amount=g.total_amount,
            discount_percentage=g.discount_percentage,
            mini_cart_items=g.get('mini_cart_items', []),
            _l=_l,
            unread_notifications_count=g.unread_notifications_count
        )

    @login_manager.user_loader
    def load_user(user_id: int) -> User:
       
        try:
            user = User.query.get(user_id)
            if user:
                db_session.refresh(user)  
            return user
        except:
            return None

    @app.after_request
    def after_request(response):
       
        if 'last_active' in session:
            last_active = datetime.fromisoformat(session['last_active'])
            if (datetime.now() - last_active) > AppConfig.PERMANENT_SESSION_LIFETIME:
                db_session.clear()
                return redirect(url_for('login'))
        session['last_active'] = datetime.now().isoformat()

        
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        return response

    return app


app = create_app()


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


@app.route("/")
def index():
  
    if 'filter_options' not in session:
        session['filter_options'] = get_filter_options()

    page = request.args.get('page', 1, type=int)
    per_page = AppConfig.PER_PAGE

    shirts_query = filter_products(None, None, None).options(
        sqlalchemy.orm.joinedload(Goods.tags),
    )

    paginated_query, in_total, total_pages, per_page = modules.filter.paginate_query(shirts_query, page)

    categories_query = Category.query.all()
    categories = [{'id': category.id, 'name': category.name, 'parent_id': category.parent_id} for category in
                  categories_query]

    current_timestamp = int(datetime.now().timestamp())
    promoted_products = db_session.query(Goods).join(ProductPromotion).filter(
        ProductPromotion.start_date <= current_timestamp,
        ProductPromotion.end_date >= current_timestamp,
        Goods.stock > 0
    ).all()

    return render_template("index.html", shirts=paginated_query,
                           current_page=page,
                           total_pages=total_pages,
                           categories=categories,
                           promoted_products=promoted_products,
                           per_page=per_page, in_total=in_total)


@app.route("/autocomplete")
def autocomplete():
    query = request.args.get('query', '')
    if not query:
        return jsonify([])

    avg_rating_subquery = db_session.query(
        Review.goods_id,
        sqlalchemy.func.avg(Review.rating).label('avg_rating')
    ).group_by(Review.goods_id).subquery()

    suggestions = db_session.query(Goods).filter(
        sqlalchemy.or_(
            Goods.samplename.ilike(f'%{query}%'),
            Goods.description.ilike(f'%{query}%')
        )
    ).outerjoin(
        avg_rating_subquery,
        Goods.id == avg_rating_subquery.c.goods_id
    ).order_by(
        sqlalchemy.case(
            (Goods.samplename.ilike(f'{query}%'), 3),
            (Goods.samplename.ilike(f'%{query}%'), 2),
            (Goods.description.ilike(f'%{query}%'), 1),
            else_=0
        ).desc(),
        avg_rating_subquery.c.avg_rating.desc().nullslast(),
        sqlalchemy.case(
            (Goods.onSale == 1, Goods.onSalePrice),
            else_=Goods.price
        ).asc()
    ).limit(5).all()

    suggestions = [
        {
            'id': suggestion.id,
            'name': suggestion.samplename,
            'current_price': suggestion.current_price,
            'avg_rating': suggestion.avg_rating or 0,  
            'description': suggestion.description
        }
        for suggestion in suggestions
    ]

    return jsonify(suggestions)


@app.route("/search")
def search_route():
    """
    Search products.
    """
    query = request.args.get('query')
    page = request.args.get('page', 1, type=int)

    if query:
        shirts = db_session.query(Goods).filter(Goods.samplename.ilike(f'%{query}%'))
    else:
        shirts = db_session.query(Goods)

    paginated_shirts, in_total, total_pages, per_page = modules.filter.paginate_query(shirts, page)

    return render_template("index.html", shirts=paginated_shirts, query=query, total_pages=total_pages,
                           current_page=page, per_page=per_page, in_total=in_total)
    return render_template("index.html", shirts=paginated_shirts, query=query, total_pages=total_pages,
                           current_page=page, per_page=per_page, in_total=in_total)
    return render_template("index.html", shirts=paginated_shirts, query=query, total_pages=total_pages,
                           current_page=page, per_page=per_page, in_total=in_total)
    return render_template("index.html", shirts=paginated_shirts, query=query, total_pages=total_pages,
                           current_page=page, per_page=per_page, in_total=in_total)
    return render_template("index.html", shirts=paginated_shirts, query=query, total_pages=total_pages,
                           current_page=page, per_page=per_page, in_total=in_total)


@app.route("/goods/<int:id>")
def goods_page(id: int):
    shirt = Goods.query.options(joinedload(Goods.category), joinedload(Goods.tags)).get(id)
    if not shirt:
        flash(_l("Product not found"), "danger")
        return redirect(url_for('index'))

    reviews = db_session.query(Review, User).join(User).filter(Review.goods_id == id) \
        .order_by(Review.date.desc()).all()

    variants = Variant.query.filter_by(goods_id=id).all()
    variant_options = {variant.name: [] for variant in variants}
    for variant in variants:
        variant_options[variant.name].append(variant.value)

    user_id = current_user.id if current_user.is_authenticated else None
    in_wishlist = False
    no_review = True
    user_has_purchased = False

    if current_user.is_authenticated:
        user_has_purchased = has_purchased(user_id, id)

        no_review = not db_session.query(exists().where(Review.user_id == user_id, Review.goods_id == id)).scalar()
        in_wishlist = db_session.query(exists().where(Wishlist.user_id == user_id, Wishlist.goods_id == id)).scalar()

        user_id = current_user.id
        update_recently_viewed_products(user_id, id)

    products_related_to_current = Goods.query.filter(
        Goods.category_id == shirt.category_id,
        Goods.id != shirt.id,
        Goods.stock > 0
    ).limit(3).all()

    product_in_comparison = False
    if current_user.is_authenticated:
        comparison_history = ComparisonHistory.query.options(selectinload(ComparisonHistory.user)) \
            .filter_by(user_id=user_id).order_by(ComparisonHistory.timestamp.desc()).first()
        if comparison_history:
            product_in_comparison = str(id) in json.loads(comparison_history.product_ids)
    else:
        comparison_history = None

    return render_template("goods_page.html", shirt=shirt, reviews=reviews,
                           average_rating=shirt.avg_rating,
                           user_has_purchased=user_has_purchased,
                           no_review=no_review, related_products=products_related_to_current,
                           tags=shirt.tags, variant_names=list(variant_options.keys()),
                           in_wishlist=in_wishlist, variant_options=variant_options,
                           comparison_history=comparison_history,
                           product_in_comparison=product_in_comparison)


@app.route("/handle_form", methods=["POST"])
def handle_form():
   
    action = request.form.get("action")
    goods_id = int(request.form.get("goods_id"))
    quantity = int(request.form.get("quantity", 1))

    variant_options = {}
    for key, value in request.form.items():
        if key not in ["action", "goods_id", "quantity"]:
            variant_options[key] = value

    goods = db_session.query(Goods).get(goods_id)
    if not goods:
        flash(_l("Product not found."), "error")
        return redirect(url_for('goods_page', id=goods_id))

    if action == "add_to_cart":
        if not current_user.is_authenticated:
            flash(_l("You must be logged in to add items to your cart."), "danger")
            return redirect(url_for('index'))
        add_to_cart(goods, quantity, variant_options)
    elif action == "add_to_wishlist":
        variant_options_str = json.dumps(variant_options)
        wishlist_item = db_session.query(Wishlist).filter_by(user_id=current_user.id, goods_id=goods_id).first()
        if wishlist_item:
            db_session.delete(wishlist_item)
            db_session.commit()
            flash(_l("Product removed from your wishlist."), "success")
        else:
            new_wishlist_item = Wishlist(user_id=current_user.id, goods_id=goods_id,
                                         variant_options=variant_options_str)
            db_session.add(new_wishlist_item)
            db_session.commit()
            flash(_l("Product added to your wishlist!"), "success")
    elif action == "add_to_comparison":
        add_to_comparison(goods_id=goods_id)

    else:
        flash(_l("Invalid action."), "danger")

    return redirect(url_for('goods_page', id=goods_id))


@app.route("/recommendations")
@login_required_with_message()
def recommendations():
    user_id = current_user.id
    recently_viewed_products = RecentlyViewedProduct.query.filter_by(user_id=user_id).order_by(
        RecentlyViewedProduct.timestamp.desc()).limit(5).all()
    recs = get_recommended_products(user_id)
    return render_template("recommendations.html", recently_viewed_products=recently_viewed_products,
                           recommendations=recs)


@app.route("/apply-discount", methods=["POST"])
@login_required_with_message()
def apply_discount():
 
    discount_code = request.form.get("discount_code")
    discount_applied = apply_discount_code(discount_code)
    if discount_applied == "success":
        flash(_l("Discount code applied successfully."), "success")
    elif discount_applied == "already_used":
        flash(_l("You have already used this discount code."), "danger")
    else:
        flash(_l("Invalid discount code."), "danger")
    return redirect(url_for('cart'))


@app.route("/terms")
def terms():
 
    return render_template("auth/terms.html")



if __name__ == "__main__":
    app.run(debug=True)