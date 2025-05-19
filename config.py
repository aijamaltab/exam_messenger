import MySQLdb

def get_connection():
    return MySQLdb.connect(
        host="localhost",
        user="root",
        passwd="tasa2004",
        db="messenger_db",
        charset='utf8mb4'
    )
