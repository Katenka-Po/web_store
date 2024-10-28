from datetime import datetime

import sqlalchemy
from flask import render_template
from flask import request

from config import AppConfig
from modules.db.database import db_session
from modules.db.models import Goods, Review, goods_tags, Category, Tag, ProductPromotion


def create_filter_routes(app):
    @app.route('/filter')
    def filter_route():
        category_id = request.args.get('category_id')
        name_query = request.args.get('name_query')
        sort_by = request.args.get('sort_by')
        tag_query = request.args.get('tag_query')

        shirts_query = filter_products(category_id=category_id, name_query=name_query, sort_by=sort_by,
                                       tag_query=tag_query)
        in_total = shirts_query.count()

        page = request.args.get('page', 1, type=int)
        per_page = AppConfig.PER_PAGE
        offset = (page - 1) * per_page
        shirts = shirts_query.limit(per_page).offset(offset).all()

        total_pages = (in_total + per_page - 1) // per_page

        categories_query = Category.query.all()
        categories = [{'id': category.id, 'name': category.name, 'parent_id': category.parent_id} for category in
                      categories_query]

        current_timestamp = int(datetime.now().timestamp())
        promoted_products = shirts_query.join(ProductPromotion).filter(
            ProductPromotion.start_date <= current_timestamp,
            ProductPromotion.end_date >= current_timestamp
        ).all()

        return render_template('index.html', shirts=shirts,
                               current_page=page, total_pages=total_pages, categories=categories,
                               promoted_products=promoted_products, per_page=AppConfig.PER_PAGE, in_total=in_total)


def filter_products(category_id=None, name_query=None, sort_by=None, tag_query=None):
    query = db_session.query(Goods).filter(Goods.stock > 0)  # Only select products with stock > 0

    if category_id:
        query = query.filter(
            Goods.category.has(Category.id == category_id) | Goods.category.has(Category.parent_id == category_id))

    if name_query:
        query = query.filter(Goods.samplename.ilike(f'%{name_query}%'))

    if tag_query:
        query = query.join(goods_tags).join(Tag).filter(Tag.name.ilike(f'%{tag_query}%'))

    if sort_by == 'price_asc':
        query = query.order_by(Goods.price.asc())
    elif sort_by == 'price_desc':
        query = query.order_by(Goods.price.desc())
    elif sort_by == 'rating':
        query = query.outerjoin(Review).group_by(Goods.id).order_by(sqlalchemy.func.avg(Review.rating).desc())

    return query


def filter_products_by_id(product_id):
    shirt = db_session.query(Goods).get(product_id)
    if shirt:
        return [shirt]
    else:
        return []


def get_filter_options():
    categories_query = Category.query.all()
    categories = [{'id': category.id, 'name': category.name, 'parent_id': category.parent_id} for category in
                  categories_query]
    tags_query = Tag.query.all()
    tags = [{'id': tag.id, 'name': tag.name} for tag in tags_query]

    filter_options = {
        'categories': categories,
        'tags': tags,
    }
    return filter_options


def paginate_query(query, page):
    in_total = query.count()
    per_page = AppConfig.PER_PAGE
    offset = (page - 1) * per_page
    paginated_query = query.offset(offset).limit(per_page).all()

    total_pages = (in_total + per_page - 1) // per_page

    return paginated_query, in_total, total_pages, per_page
