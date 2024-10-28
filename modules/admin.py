import io

import pandas as pd
from flask import flash
from flask import redirect, url_for, request
from flask import send_file
from flask_admin import Admin, AdminIndexView, expose, BaseView
from flask_admin.contrib.sqla import ModelView
from flask_babel import gettext as _l
from flask_login import current_user
from sqlalchemy import inspect
from ydata_profiling import ProfileReport

from modules.db.database import db_session
from modules.db.models import *
from modules.decorators import login_required_with_message, admin_required


def get_table_names():
    inspector = inspect(db_session.bind)
    return inspector.get_table_names()


def _number_formatter(view, context, model, name):
    value = getattr(model, name)
    if value is not None:
        return '{:.2f}'.format(value)
    return ''


class AdminView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))


class MyAdminIndexView(AdminIndexView):
    @expose('/')
    @login_required_with_message()
    @admin_required
    def index(self):
        if not current_user.is_admin:
            flash(_l('You do not have permission to access this page.'), 'danger')
            return redirect(url_for('login'))
        return self.render('admin/index.html')


class UserView(AdminView):
    column_searchable_list = ['username', 'email']
    column_filters = ['is_admin', 'is_active']
    column_editable_list = ['is_admin', 'is_active']
    form_excluded_columns = ['password']
    column_exclude_list = ['password']


class StatisticsView(BaseView):
    @expose('/', methods=['GET', 'POST'])
    @login_required_with_message()
    @admin_required
    def index(self):

        table_names = get_table_names()

        if request.method == 'POST':
            tables = request.form.getlist('tables')
            data_percentage = int(request.form.get('data_percentage', 100))

            profile_reports = []
            for table in tables:
                if table in table_names:
                    query = f"SELECT * FROM {table} ORDER BY id DESC LIMIT (SELECT CAST(COUNT(*) * {data_percentage / 100.0} AS INTEGER) FROM {table})"
                    df = pd.read_sql_query(query, db_session.bind)
                    profile = ProfileReport(df, title=f"{table.capitalize()} Dataset")
                    profile_reports.append(profile)

            if profile_reports:
                merged_report = profile_reports[0]
                for report in profile_reports[1:]:
                    merged_report.add_report(report)

                profile_html = merged_report.to_html()

                output = io.BytesIO()
                output.write(profile_html.encode('utf-8'))
                output.seek(0)
                return send_file(output, mimetype='text/html', as_attachment=True,
                                 download_name='statistics_report.html')

        return self.render('admin/statistics.html', table_names=table_names)


class ReportsView(BaseView):
    @expose('/', methods=['GET', 'POST'])
    @login_required_with_message()
    @admin_required
    def index(self):
        table_names = get_table_names()

        if request.method == 'POST':
            tables = request.form.getlist('tables')
            file_format = request.form.get('file_format')

            data_frames = []
            for table in tables:
                if table in table_names:
                    df = pd.read_sql_table(table, db_session.bind)
                    data_frames.append(df)

            if file_format == 'csv':
                output = io.BytesIO()
                for i, df in enumerate(data_frames):
                    df.to_csv(output, index=False, header=True)
                    if i < len(data_frames) - 1:
                        output.write(b'\n')
                output.seek(0)
                return send_file(output, mimetype='text/csv', as_attachment=True, download_name='data.csv')
            elif file_format == 'json':
                output = io.StringIO()
                for i, df in enumerate(data_frames):
                    df.to_json(output, orient='records')
                    if i < len(data_frames) - 1:
                        output.write('\n')
                output.seek(0)
                return send_file(output, mimetype='application/json', as_attachment=True, download_name='data.json')
            elif file_format == 'excel':
                output = io.BytesIO()
                writer = pd.ExcelWriter(output, engine='openpyxl')
                for i, df in enumerate(data_frames):
                    df.to_excel(writer, sheet_name=f'Sheet{i + 1}', index=False)
                writer.save()
                output.seek(0)
                return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                 as_attachment=True, download_name='data.xlsx')

        return self.render('admin/reports.html', table_names=table_names)


class GoodsView(AdminView):
    column_searchable_list = ['samplename', 'description']
    column_filters = ['onSale', 'category']
    column_editable_list = ['price', 'onSale', 'onSalePrice', 'stock']
    form_excluded_columns = ['purchase_items', 'reviews', 'wishlist_items', 'cart_items', 'recently_viewed_by']
    form_widget_args = {
        'description': {'rows': 10},
    }
    form_ajax_refs = {
        'category': {
            'fields': ['name'],
            'page_size': 10
        },
        'tags': {
            'fields': ['name'],
            'page_size': 10
        },
        'related_products': {
            'fields': ['samplename'],
            'page_size': 10
        }
    }

    column_formatters = {
        'price': _number_formatter,
        'onSalePrice': _number_formatter,
    }


class CategoryView(AdminView):
    column_searchable_list = ['name']
    form_excluded_columns = ['goods']
    form_ajax_refs = {
        'parent': {
            'fields': ['name'],
            'page_size': 10
        }
    }


class PurchaseView(AdminView):
    column_searchable_list = ['user.username', 'date']
    column_filters = ['status']
    column_editable_list = ['status']
    form_excluded_columns = ['items']


class ReviewView(AdminView):
    column_searchable_list = ['user.username', 'goods.samplename']
    column_filters = ['moderated']
    column_editable_list = ['moderated']


class WishlistView(AdminView):
    column_searchable_list = ['user.username', 'goods.samplename']


class TagView(AdminView):
    column_searchable_list = ['name']
    form_excluded_columns = ['goods']


class ProductPromotionView(AdminView):
    form_excluded_columns = ['goods']


class DiscountView(AdminView):
    column_searchable_list = ['code']
    column_filters = ['start_date', 'end_date']
    form_excluded_columns = ['users']


class ShippingMethodView(AdminView):
    column_searchable_list = ['name']


class ReportedReviewView(AdminView):
    column_searchable_list = ['review.user.username', 'review.goods.samplename']
    column_filters = ['created_at']
    form_excluded_columns = ['user', 'review']


    
def create_admin(app):
    admin = Admin(app, name='Admin Panel', template_mode='bootstrap4', index_view=MyAdminIndexView(name='Dashboard'))
    admin.add_view(UserView(User, db_session, name='Users'))
    admin.add_view(GoodsView(Goods, db_session, name='Goods'))
    admin.add_view(CategoryView(Category, db_session, name='Categories'))
    admin.add_view(PurchaseView(Purchase, db_session, name='Purchases'))
    admin.add_view(ReviewView(Review, db_session, name='Reviews'))
    admin.add_view(WishlistView(Wishlist, db_session, name='Wishlists'))
    admin.add_view(TagView(Tag, db_session, name='Tags'))
    admin.add_view(ProductPromotionView(ProductPromotion, db_session, name='Promotions'))
    admin.add_view(DiscountView(Discount, db_session, name='Discounts'))
    admin.add_view(ShippingMethodView(ShippingMethod, db_session, name='Shipping Methods'))
    admin.add_view(ReportedReviewView(ReportedReview, db_session, name='Reported Reviews'))
    admin.add_view(StatisticsView(name='Statistics', endpoint='statistics', category='Statistics'))
    admin.add_view(ReportsView(name='Reports', endpoint='reports', category='Reports'))