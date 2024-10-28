import json
import random
from datetime import datetime

import stripe
from flask import jsonify
from flask import redirect, request, url_for, flash, render_template
from flask_babel import gettext as _l
from flask_login import current_user

from modules.db.database import db_session
from modules.db.models import Goods, Cart, Discount, UserDiscount, ShippingMethod, Purchase
from modules.decorators import login_required_with_message
from modules.email import send_order_confirmation_email
from modules.purchase_history import save_purchase_history


def create_cart_routes(app):
    @app.template_filter('from_json')
    def from_json(value):
        return json.loads(value)

    @app.route("/add-to-cart", methods=["POST"])
    @login_required_with_message(redirect_back=True)
    def add_to_cart_route():
        quantity = int(request.form['quantity'])
        goods_id = request.form['id']
        variant_options = request.form.to_dict(flat=False).get('variant_options', {})  

        goods = Goods.query.get(goods_id)
        if goods:
            add_to_cart(goods, quantity, variant_options)
        else:
            flash(_l("Product not found."), "danger")

        return redirect(url_for('goods_page', id=goods_id))

    @app.route("/cart")
    @login_required_with_message(redirect_back=True)
    def cart():
        cart_items = Cart.query.filter_by(user_id=current_user.id).all()
        subtotal = sum(item.price * item.quantity for item in cart_items)
        discount_percentage = getattr(current_user, 'discount', 0)
        total_amount = subtotal - (subtotal * discount_percentage / 100)

        return render_template("cart.html", cart=cart_items, subtotal=subtotal,
                               discount_percentage=discount_percentage, total_amount=total_amount)

    @app.route("/update-cart", methods=["POST"])
    @login_required_with_message()
    def update_cart_route():
        try:
            quantity = int(request.form['quantity'])
            cart_item_id = int(request.form['cart_item_id'])
            status = update_cart(cart_item_id, quantity)

            total_items, total_amount, discount_percentage = Cart.cart_info()
            cart_items = Cart.total_quantity()

            cart_item = Cart.query.get(cart_item_id)
            item_subtotal = cart_item.price * cart_item.quantity

            return jsonify({
                'subtotal': '${:,.2f}'.format(total_amount),
                'discount': '-${:,.2f}'.format(total_amount * discount_percentage),
                'cart_items': cart_items,
                'cart_total': '${:,.2f}'.format(total_amount * (1 - discount_percentage)),
                'item_subtotal': '${:,.2f}'.format(item_subtotal),
                'status': status,
            })
        except ValueError:
            return jsonify({'status': False})

    @app.route("/remove-from-cart/<int:cart_item_id>")
    @login_required_with_message()
    def remove_from_cart_route(cart_item_id):
        remove_from_cart(cart_item_id)
        flash(_l("Item removed from cart."), "success")
        return redirect(url_for('cart'))

    @app.route("/checkout", methods=["GET", "POST"])
    @login_required_with_message()
    def checkout():
        cart_items = Cart.query.filter_by(user_id=current_user.id).all()
        if not cart_items:
            flash(_l("Your cart is empty."), "danger")
            return redirect(url_for('cart'))

        if not current_user.addresses:
            flash(_l("Please add an address before proceeding to checkout."), "warning")
            return redirect(url_for('profile'))

        shipping_methods = ShippingMethod.query.all()
        addresses = current_user.addresses

        subtotal = Cart.subtotal()
        shipping_price = shipping_methods[0].price if shipping_methods else 0
        total = subtotal + shipping_price

        if request.method == "POST":
            shipping_address_id = request.form.get("shipping_address")
            shipping_method_id = request.form.get("shipping_method")
            payment_method = request.form.get("payment_method")
            stripe.api_key = app.config['STRIPE_SECRET_KEY']

            try:
     
                original_prices = {item.id: item.price for item in cart_items}
                save_purchase_history(cart_items,
                                      original_prices,
                                      shipping_address_id,
                                      shipping_method_id,
                                      payment_method, random.randint(100000, 999999)) 
                clear_cart()
                current_user.discount = 0
                db_session.commit()

                send_order_confirmation_email(current_user.email, current_user.fname)
                flash(_l("Purchase completed. Thank you for shopping with us!"), "success")
                return redirect(url_for('order_confirmation'))

            except stripe.error.CardError as e:
                flash(_l("Payment failed") + ":" + e.user_message, "danger")

        return render_template("checkout.html", cart_items=cart_items, shipping_methods=shipping_methods,
                               addresses=addresses, subtotal=subtotal, shipping_price=shipping_price, total=total)

    @app.route("/order-confirmation")
    @login_required_with_message()
    def order_confirmation():
        latest_purchase = Purchase.query.filter_by(user_id=current_user.id).order_by(Purchase.id.desc()).first()
        total_amount = sum(item.price * item.quantity for item in latest_purchase.items)
        return render_template("order_confirmation.html", purchase=latest_purchase, total_amount=total_amount)


def clear_cart():
    Cart.query.filter_by(user_id=current_user.id).delete()
    db_session.commit()


def update_cart(cart_item_id: int, quantity: int) -> bool:
    cart_item = Cart.query.get(cart_item_id)
    if cart_item and cart_item.user_id == current_user.id:
        goods = Goods.query.get(cart_item.goods_id)
        stock_difference = quantity - cart_item.quantity

        if goods.stock >= stock_difference:
            if quantity > 0:
                cart_item.quantity = quantity
                goods.stock -= stock_difference
            else:
                remove_from_cart(cart_item_id)
                goods.stock += cart_item.quantity

            db_session.commit()
            return True
        else:
            flash(_l("Not enough stock available for this product."), "danger")

    return False


def remove_from_cart(cart_item_id):
    cart_item = Cart.query.get(cart_item_id)
    if cart_item and cart_item.user_id == current_user.id:
        db_session.delete(cart_item)
        db_session.commit()


def add_to_cart(goods: Goods, quantity: int, variant_options: dict) -> bool:
    variant_options_str = json.dumps(variant_options)

    cart_item = Cart.query.filter_by(user_id=current_user.id, goods_id=goods.id,
                                     variant_options=variant_options_str).first()
    if goods.stock >= quantity:
        if cart_item:
            cart_item.quantity += quantity
        else:
            price = goods.onSalePrice if goods.onSale else goods.price
            new_cart_item = Cart(
                user_id=current_user.id,
                goods_id=goods.id,
                quantity=quantity,
                price=price,
                variant_options=variant_options_str
            )
            db_session.add(new_cart_item)

        goods.stock -= quantity
        db_session.commit()
        flash(_l("Item added to cart."), "success")
        return True
    else:
        flash(_l("Not enough stock available for this product."), "danger")
        return False


def apply_discount_code(discount_code):
    discount = Discount.query.filter_by(code=discount_code).first()
    if discount:
        current_date = datetime.now().date()
        if discount.start_date <= current_date <= discount.end_date:
            user_discount = UserDiscount.query.filter_by(user_id=current_user.id, discount_id=discount.id).first()
            if user_discount:
                return "already_used"
            else:
                cart_items = Cart.query.filter_by(user_id=current_user.id).all()
                for item in cart_items:
                    discounted_price = item.price - (item.price * discount.percentage / 100)
                    item.price = discounted_price
                new_user_discount = UserDiscount(user_id=current_user.id, discount_id=discount.id)
                db_session.add(new_user_discount)
                db_session.commit()
                return "success"
    return "invalid"
