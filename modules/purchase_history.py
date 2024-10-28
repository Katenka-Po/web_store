import datetime

from flask import redirect, url_for, flash, render_template
from flask_babel import gettext as _l
from flask_login import current_user

from modules.db.database import db_session
from modules.db.models import Purchase, PurchaseItem, ShippingAddress, Address, ShippingMethod
from modules.decorators import login_required_with_message
from modules.email import send_email


def create_purchase_history_routes(app):
    @app.route("/purchase-history")
    @login_required_with_message(message="Вы должны быть зарегистрированы, чтобы просматривать историю покупок")
    def purchase_history():
        purchases = get_purchase_history()
        return render_template("history.html", purchases=purchases)

    @app.route("/purchase-details/<int:purchase_id>")
    @login_required_with_message(message="You must be logged in to view purchase details.")
    def purchase_details(purchase_id):
        purchase = db_session.query(Purchase).get(purchase_id)
        if not purchase:
            return 404, "Purchase not found"
        if purchase.user_id != current_user.id:
            flash(_l("You don't have permission to view this purchase."), "danger")
            return redirect(url_for('purchase_history'))
        return render_template("purchase_details.html", purchase=purchase)

    @app.route("/cancel-order/<int:purchase_id>", methods=['POST'])
    @login_required_with_message(message="You must be logged in to cancel an order.")
    def cancel_order(purchase_id):
        purchase = db_session.query(Purchase).get(purchase_id)
        if not purchase:
            return 404, "Purchase not found"
        if purchase.user_id != current_user.id:
            flash(_l("You don't have permission to cancel this order."), "danger")
            return redirect(url_for('purchase_history'))
        if purchase.status != 'Pending':
            flash(_l("This order cannot be cancelled."), "danger")
            return redirect(url_for('purchase_details', purchase_id=purchase_id))
        purchase.status = 'Cancelled'
        db_session.commit()
        send_email(current_user.email, 'Order Cancelled', 'Your order has been successfully cancelled.')
        flash(_l("Order cancelled successfully."), "success")
        return redirect(url_for('purchase_history'))


def save_purchase_history(cart_items, original_prices, shipping_address_id, shipping_method_id, payment_method,
                          payment_id):
    if not cart_items:
        return  

    user_id = current_user.id
    subtotal = sum(original_prices[item.id] * item.quantity for item in cart_items)
    discount_percentage = getattr(current_user, 'discount', 0)
    discount_amount = subtotal * (discount_percentage / 100)
    shipping_method = ShippingMethod.query.get(shipping_method_id)
    delivery_fee = shipping_method.price if shipping_method else 0
    total_price = subtotal - discount_amount + delivery_fee
    tracking_number = 'TRACK' + str(datetime.datetime.now().timestamp()).replace('.', '')[:10]  
    shipping_address = Address.query.get(shipping_address_id)

    new_purchase = Purchase(user_id=user_id,
                            date=datetime.datetime.now(),
                            total_price=total_price,
                            discount_amount=discount_amount,
                            delivery_fee=delivery_fee,
                            status="Completed",
                            tracking_number=tracking_number,
                            shipping_method=shipping_method.name if shipping_method else None,
                            payment_method=payment_method,
                            payment_id=payment_id
                            )
    db_session.add(new_purchase)
    db_session.flush()  

    new_shipping_address = ShippingAddress(
        purchase_id=new_purchase.id,
        address_line1=shipping_address.address_line1,
        address_line2=shipping_address.address_line2,
        city=shipping_address.city,
        state=shipping_address.state,
        zip_code=shipping_address.zip_code,
        country=shipping_address.country
    )
    db_session.add(new_shipping_address)

    for item in cart_items:
        new_purchase_item = PurchaseItem(
            purchase_id=new_purchase.id,
            goods_id=item.goods_id,
            quantity=item.quantity,
            price=original_prices[item.id]
        )
        db_session.add(new_purchase_item)

    db_session.commit()
    Purchase.update_stock(new_purchase)
    send_email(current_user.email, 'Order Confirmation', 'Thank you for your order! Your order is being processed.')


def get_purchase_history():
    user_id = current_user.id
    purchases = db_session.query(Purchase).filter_by(user_id=user_id).order_by(Purchase.date.desc()).all()
    for purchase in purchases:
        items_subtotal = sum(item.quantity * item.price for item in purchase.items)
        purchase.items_subtotal = items_subtotal
    return purchases
