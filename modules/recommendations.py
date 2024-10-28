from datetime import datetime
from typing import List

from sqlalchemy import desc

from modules.db.database import db_session
from modules.db.models import RecentlyViewedProduct, Goods, UserPreference


def update_recently_viewed_products(user_id: int, goods_id: int) -> None:
  
    recently_viewed_product = RecentlyViewedProduct.query.filter_by(user_id=user_id, goods_id=goods_id).first()
    if recently_viewed_product:
        recently_viewed_product.timestamp = datetime.utcnow()
    else:
        recently_viewed_product = RecentlyViewedProduct(user_id=user_id, goods_id=goods_id)
        db_session.add(recently_viewed_product)
    db_session.commit()


def get_related_products(user_id: int, goods_id: int) -> List[Goods]:
   
    current_product = Goods.query.get(goods_id)
    user_preferences = UserPreference.query.filter_by(user_id=user_id).order_by(
        desc(UserPreference.interest_level)).all()
    related_products = Goods.query.filter(
        Goods.category_id.in_([pref.category_id for pref in user_preferences]),
        Goods.id != goods_id,
        Goods.stock > 0
    ).order_by(desc(Goods.avg_rating)).limit(5).all()
    return related_products


def get_recommended_products(user_id: int) -> List[Goods]:
   
    user_preferences = UserPreference.query.filter_by(user_id=user_id).order_by(
        desc(UserPreference.interest_level)).all()
    recommended_products = Goods.query.filter(
        Goods.category_id.in_([pref.category_id for pref in user_preferences]),
        Goods.stock > 0
    ).order_by(desc(Goods.id)).limit(10).all()
    return recommended_products
