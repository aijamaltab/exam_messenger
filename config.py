import MySQLdb
import os

def get_connection():
    return MySQLdb.connect(
        host=os.getenv('DB_HOST', 'db4free.net'),
        user=os.getenv('DB_USER', 'sellin29'),
        passwd=os.getenv('DB_PASSWORD', 'aijamal29062004'),
        db=os.getenv('DB_NAME', 'messenger_chat'),
        charset='utf8mb4'
    )
