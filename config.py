import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()  # Загружаем переменные из .env

def get_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'crossover.proxy.rlwy.net'),
        port=os.getenv('DB_PORT', '35160'),
        database=os.getenv('DB_NAME', 'railway'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'whrouqLGrFkJaqQcPcgipobdKyIYVZNi') 
    )
