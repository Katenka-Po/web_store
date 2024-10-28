from datetime import datetime
from typing import Tuple, List, Optional

from flask_login import current_user, UserMixin
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, Date, ForeignKey, CheckConstraint, \
    Table, DateTime, UniqueConstraint, Enum
from sqlalchemy.orm import relationship, backref, joinedload
from sqlalchemy.sql import func

from modules.db.database import Base, db_session


class User(Base, UserMixin):
   
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, nullable=False, unique=True, index=True)
    password = Column(Text, nullable=False)
    fname = Column(Text)
    lname = Column(Text)
    email = Column(Text, unique=True, index=True)
    phone = Column(Text)
    profile_picture = Column(Text)
    language = Column(String(5), default='en')
    notifications_enabled = Column(Boolean, default=True)
    email_notifications_enabled = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    role = Column(Enum('applicant', 'secretary', 'employee', 'admin', name='user_roles'), nullable=False,
                  default='client')

    @property
    def is_applicant(self):
        return self.role == 'applicant'

    @property
    def is_secretary(self):
        return self.role == 'secretary'

    @property
    def is_employee(self):
        return self.role == 'employee'

    addresses = relationship('Address', backref='user', lazy='select')
    cart_items = relationship('Cart', backref='user', lazy='select')
    purchases = relationship('Purchase', backref='user', lazy='select')
    reviews = relationship('Review', backref='user', lazy='select')
    wishlist_items = relationship('Wishlist', backref='user',
                                  lazy='dynamic')
    notifications = relationship('Notification', backref='user', lazy='select')
    social_accounts = relationship('SocialAccount', backref=backref('user_account', lazy='select'), lazy='select')

    recently_viewed_products = relationship('RecentlyViewedProduct', backref='user', lazy='select')
    preferences = relationship('UserPreference', backref='user', lazy='select')

    def __str__(self):
        return self.username

    @staticmethod
    def get_wishlist_notifications() -> Tuple[List['Goods'], List['Goods']]:

        wishlist_items = db_session.query(Wishlist).options(joinedload(Wishlist.goods)).filter_by(
            user_id=current_user.id).all()

        on_sale_items = []
        back_in_stock_items = []

        for item in wishlist_items:
            goods = item.goods

            if goods.onSale:
                on_sale_items.append(goods)
            elif goods.stock > 0:
                back_in_stock_items.append(goods)

        return on_sale_items, back_in_stock_items


class RecentlyViewedProduct(Base):
    __tablename__ = 'recently_viewed_products'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    goods_id = Column(Integer, ForeignKey('goods.id'), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    goods = relationship('Goods', backref='recently_viewed_by', lazy='select')

    def __str__(self):
        return f'RecentlyViewedProduct {self.id}'


class UserPreference(Base):
    __tablename__ = 'user_preferences'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False, index=True)
    interest_level = Column(Integer, nullable=False)

    category = relationship('Category', backref='user_preferences', lazy='select')

    def __str__(self):
        return f'UserPreference {self.id} {self.interest_level}'


class Cart(Base):
    __tablename__ = 'cart'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    goods_id = Column(Integer, ForeignKey('goods.id'), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    variant_options = Column(Text)

    goods = relationship('Goods', backref='cart_items', lazy='joined')

    def __str__(self):
        return f'Cart {self.id}'

    @staticmethod
    def update_stock(goods_id: int, quantity: int) -> None:

        goods = db_session.query(Goods).get(goods_id)
        if goods:
            goods.stock -= quantity
            db_session.commit()

    @staticmethod
    def total_quantity() -> int:
      
        if current_user.is_authenticated:

            cart_items = db_session.query(Cart).filter_by(user_id=current_user.id).all()
            total_quantity = sum(item.quantity for item in cart_items)
            return total_quantity
        else:
            return 0

    @staticmethod
    def subtotal() -> float:
    
        if current_user.is_authenticated:

            cart_items = db_session.query(Cart).filter_by(user_id=current_user.id).all()
            subtotal = sum(item.price * item.quantity for item in cart_items)
            return subtotal
        else:
            return 0

    @staticmethod
    def cart_info() -> Tuple[int, float, float]:
      
        discount_percentage = 0
        if current_user.is_authenticated:

            cart_items = db_session.query(Cart).filter_by(user_id=current_user.id).all()
            user_discounts = db_session.query(UserDiscount).filter_by(user_id=current_user.id).all()

            total_items = sum(item.quantity for item in cart_items)
            subtotal = sum(item.quantity * item.price for item in cart_items)

            current_date = datetime.now().date()
            applicable_discounts = [discount for discount in user_discounts if
                                    discount.discount.start_date <= current_date <= discount.discount.end_date]

            if applicable_discounts:
                max_discount = max(applicable_discounts, key=lambda x: x.discount.percentage)
                discount_percentage = max_discount.discount.percentage
                current_user.discount = discount_percentage
                discount_amount = subtotal * (discount_percentage / 100)
                total_amount = subtotal - discount_amount
            else:
                current_user.discount = 0
                total_amount = subtotal
        else:
            total_items = 0
            total_amount = 0

        return total_items, total_amount, discount_percentage


related_products = Table('related_products', Base.metadata,
                         Column('goods_id1', Integer, ForeignKey('goods.id', ondelete='CASCADE'),
                                primary_key=True),
                         Column('goods_id2', Integer, ForeignKey('goods.id', ondelete='CASCADE'),
                                primary_key=True)
                         )


class Goods(Base):
    __tablename__ = 'goods'

    id = Column(Integer, primary_key=True, autoincrement=True)
    samplename = Column(Text)
    image = Column(Text)
    price = Column(Float)
    onSale = Column(Integer)
    onSalePrice = Column(Float)
    kind = Column(Text)
    goods_type = Column(Text)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey('categories.id'), index=True)
    stock = Column(Integer, nullable=False, default=0)

    category = relationship('Category', backref='goods', lazy='select')
    purchase_items = relationship('PurchaseItem', lazy='select', passive_deletes=True)
    reviews = relationship('Review', backref='goods', lazy='select', passive_deletes=True)
    wishlist_items = relationship('Wishlist', backref='goods', lazy='select', passive_deletes=True)
    variants = relationship('Variant', backref='goods', lazy='select', passive_deletes=True)
    tags = relationship('Tag', secondary='goods_tags', backref='goods', lazy='select', passive_deletes=True)
    related_products = relationship('Goods', secondary='related_products',
                                    primaryjoin=(id == related_products.c.goods_id1),
                                    secondaryjoin=(id == related_products.c.goods_id2),
                                    backref=backref('related_to', lazy='select'),
                                    lazy='select',
                                    passive_deletes=True)

    def __str__(self):
        return f'{self.samplename}: {self.description[:20]}..'

    @property
    def avg_rating(self) -> Optional[float]:
      

        if self.reviews:
            avg_rating = db_session.query(func.avg(Review.rating)).filter_by(goods_id=self.id).scalar()
            return avg_rating
        else:
            return 0

    @property
    def current_price(self) -> float:
    
        return self.onSalePrice if self.onSale else self.price


class SocialAccount(Base):
    __tablename__ = 'social_accounts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    social_id = Column(String(255), nullable=False)
    access_token = Column(String(255), nullable=False)

    def __str__(self):
        return self.social_id


class ComparisonHistory(Base):
    __tablename__ = 'comparison_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    product_ids = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship('User', backref='comparison_history', lazy='joined')

    def __str__(self):
        return f'ComparisonHistory {self.id} {self.timestamp} {self.product_ids}'


class Purchase(Base):
    __tablename__ = 'purchases'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    date = Column(Date, nullable=False, default=func.current_date())
    total_price = Column(Float, nullable=False)
    discount_amount = Column(Float, nullable=False, default=0)
    delivery_fee = Column(Float, nullable=False, default=0)
    status = Column(Text)
    tracking_number = Column(Text)
    shipping_method = Column(Text)
    payment_method = Column(Text)
    payment_id = Column(Text)

    items = relationship('PurchaseItem', lazy='joined')
    shipping_address = relationship('ShippingAddress', uselist=False)

    @staticmethod
    def update_stock(purchase: 'Purchase') -> None:
        """
        Update the stock of goods items after a purchase.
        """

        for item in purchase.items:
            goods = db_session.query(Goods).get(item.goods_id)
            if goods:
                goods.stock -= item.quantity
        db_session.commit()


class ShippingMethod(Base):
    __tablename__ = 'shipping_methods'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    price = Column(Float, nullable=False)


class PurchaseItem(Base):
    __tablename__ = 'purchase_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    purchase_id = Column(Integer, ForeignKey('purchases.id'), nullable=False, index=True)
    goods_id = Column(Integer, ForeignKey('goods.id'), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)

    @property
    def goods(self) -> Goods:
     
        return Goods.query.get(self.goods_id)


class ReportedReview(Base):
    __tablename__ = "reported_reviews"

    id = Column(Integer, primary_key=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    explanation = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    review = relationship("Review", backref="reported_reviews")
    user = relationship("User", backref="reported_reviews")

    def __str__(self):
        return f'ReportedReview {self.id}'


class Review(Base):
    __tablename__ = 'reviews'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    goods_id = Column(Integer, ForeignKey('goods.id'), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    review = Column(Text)
    title = Column(Text)
    pros = Column(Text)
    cons = Column(Text)
    images = Column(Text)
    date = Column(Date, nullable=False, default=func.current_date())
    moderated = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5'),
    )

    def __str__(self):
        return f'{self.review}..'


class Address(Base):
    __tablename__ = 'addresses'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    address_line1 = Column(Text, nullable=False)
    address_line2 = Column(Text)
    city = Column(Text, nullable=False)
    state = Column(Text, nullable=False)
    zip_code = Column(Text, nullable=False)
    country = Column(Text, nullable=False)

    def __str__(self):
        return f'{self.address_line1}'


class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    parent_id = Column(Integer, ForeignKey('categories.id'), index=True)

    parent = relationship('Category', remote_side=[id], backref='subcategories', lazy='joined')

    def __str__(self):
        return self.name


class ShippingAddress(Base):
    __tablename__ = 'shipping_addresses'

    id = Column(Integer, primary_key=True, autoincrement=True)
    purchase_id = Column(Integer, ForeignKey('purchases.id'), nullable=False)
    address_line1 = Column(Text, nullable=False)
    address_line2 = Column(Text)
    city = Column(Text, nullable=False)
    state = Column(Text, nullable=False)
    zip_code = Column(Text, nullable=False)
    country = Column(Text, nullable=False)

    def __repr__(self):
        return f'ShippingAddress {self.id}: {self.address_line1}>'


class Wishlist(Base):
    __tablename__ = 'wishlists'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    goods_id = Column(Integer, ForeignKey('goods.id'), nullable=False)
    variant_options = Column(Text)

    def __str__(self):
        return f'Wishlist {self.id}'


class Variant(Base):
    __tablename__ = 'variants'

    id = Column(Integer, primary_key=True, autoincrement=True)
    goods_id = Column(Integer, ForeignKey('goods.id'), nullable=False)
    name = Column(Text, nullable=False)
    value = Column(Text, nullable=False)

    def __str__(self):
        return f'{self.name}: {self.value}'


class Discount(Base):
    __tablename__ = 'discounts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Text, nullable=False)
    percentage = Column(Float, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    def __str__(self):
        return f'{self.code}: {self.percentage}%'


class UserDiscount(Base):
    __tablename__ = 'user_discounts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    discount_id = Column(Integer, ForeignKey('discounts.id'), nullable=False)

    discount = relationship('Discount', backref='users', lazy='joined')
    user = relationship('User', backref='discounts', lazy='joined')

    __table_args__ = (
        UniqueConstraint('user_id', 'discount_id', name='unique_user_discount'),
    )


class Notification(Base):
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    message = Column(Text, nullable=False)
    read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=func.current_timestamp())

    def __str__(self):
        return f'{self.message[:20]}..'


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)

    def __str__(self):
        return self.name


goods_tags = Table('goods_tags', Base.metadata,
                   Column('goods_id', Integer, ForeignKey('goods.id', ondelete='CASCADE'),
                          primary_key=True),
                   Column('tag_id', Integer, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
                   )


class ProductPromotion(Base):
    __tablename__ = 'product_promotions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    goods_id = Column(Integer, ForeignKey('goods.id'), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    description = Column(Text, nullable=False)

    goods = relationship('Goods', backref='promotions', lazy='joined')

    def __str__(self):
        return f'{self.description[:20]}..'