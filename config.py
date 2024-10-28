import os
from dataclasses import dataclass
from datetime import timedelta


@dataclass
class AppConfig:
    SECRET_KEY: str = 'secret_key'
    PROJECT_ROOT: str = os.path.abspath(os.path.dirname(__file__))

    DEFAULT_LIMIT_RATE: str = '10 per minute'

    DB_PATH: str = os.path.join(PROJECT_ROOT, 'instance') 
    DB_NAME: str = 'data.db'  
    BACKUP_DIR: str = os.path.join(PROJECT_ROOT, 'modules', 'db', 'backups')  
    SQLALCHEMY_DATABASE_URI: str = 'sqlite:///' + DB_PATH + '/' + DB_NAME
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(minutes=15)
    SHOP_NAME: str = 'Электронный магазин одежды'
    PROFILE_PICS_FOLDER: str = os.path.join(PROJECT_ROOT, 'static', 'img', 'profile_pictures')
    IMG_FORMATS = ['.png', '.jpg', '.jpeg', '.bmp']
    REVIEW_PICS_FOLDER: str = os.path.join('static', 'img', 'review_pictures')
    IMAGES_FOLDER: str = os.path.join('static', 'img')
    MAIL_DEFAULT_SENDER: str = 'default'
    WEBSITE_URL: str = 'https://example.com'

    PER_PAGE: int = 9  

    TERMS_LAST_UPDATED: str = '01.04.2024'
    CONTACT_EMAIL: str = 'contact@example.com'
    CONTACT_PHONE: str = '+7 123 123 12 12'
    JURISDICTION: str = 'Москва, РФ'

    BABEL_DEFAULT_LOCALE: str = 'ru'
    BABEL_TRANSLATION_DIRECTORIES: str = 'translations'
    LANGUAGES = ['en', 'ru']
    LANGUAGE_NAMES = {
        'en': 'English',
        'ru': 'Русский'
    }

    DEBUG: bool = True  

