import os
import shutil

from config import AppConfig


def restore_database(backup_file):
    backup_path = os.path.join(AppConfig.BACKUP_DIR, backup_file)

    try:
        if os.path.isfile(backup_path):
            shutil.copy2(backup_path, AppConfig.DB_NAME)
            print(f"Database restored from backup: {backup_path}")
        else:
            print(f"Backup file not found: {backup_path}")
    except Exception as e:
        print(f"Error restoring database: {str(e)}")


backup_file = "database_backup_20240313_150646.db"

print('restore turned off in restore.py')
