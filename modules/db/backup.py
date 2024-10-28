import os
import shutil
from datetime import datetime

from config import AppConfig


def backup_database(backup_dir=AppConfig.BACKUP_DIR):
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_file = f"database_backup_{timestamp}.db"

    backup_path = os.path.join(backup_dir, backup_file)

    try:
        shutil.copyfile(AppConfig.DB_PATH + '/' + AppConfig.DB_NAME, backup_path)
        print(f"Database backup created: {backup_path}")
    except Exception as e:
        print(f"Error creating database backup: {str(e)}")



print('backup turned off in backup.py')