import os
from flask import Flask, render_template, request, redirect, session, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
from datetime import datetime
from dotenv import load_dotenv
import mysql.connector
from urllib.parse import urlparse

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
socketio = SocketIO(app)
last_message_id = 0

# MySQL connection helper
def get_connection():
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        # Parse URL like mysql://user:pass@host:port/dbname
        result = urlparse(db_url)
        config = {
            'host':     result.hostname,
            'port':     result.port,
            'user':     result.username,
            'password': result.password,
            'database': result.path.lstrip('/')
        }
    else:
        # fallback to individual ENV
        config = {
            'host':     os.getenv('DB_HOST',     'localhost'),
            'port':     int(os.getenv('DB_PORT',  3306)),
            'user':     os.getenv('DB_USER',     ''),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME',     '')
        }
    # DEBUG: залогировать параметры (кроме пароля)  
    print(f">> Connecting to MySQL: {config['user']}@{config['host']}:{config['port']}/{config['database']}")
    return mysql.connector.connect(**config)

@app.route('/sip-config', methods=['GET'])
def sip_config():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({
        'wsServers':         [os.getenv('SIP_WS_URI')],              # WebSocket URL
        'uri':               f"sip:{os.getenv('SIP_USER')}@{os.getenv('SIPS_DOMAIN')}",  
        'authorizationUser': os.getenv('SIP_USER'),
        'password':          os.getenv('SIP_PASS'),
        'domain':            os.getenv('SIPS_DOMAIN'),               # <-- вот это
        'iceServers':        [{'urls': ['stun:stun.l.google.com:19302']}]
    })


@app.route('/')
def home():
    return redirect('/chat') if 'user_id' in session else redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']
        password = request.form['password']
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password, name FROM users WHERE phone = %s", (phone,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['user_name'] = user[2]
            return redirect('/chat')
        return 'Неверный номер или пароль'
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        raw_password = request.form.get('password')
        if not (name and phone and raw_password):
            return 'Все поля обязательны'
        password = generate_password_hash(raw_password)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, phone, password) VALUES (%s, %s, %s)",
                (name, phone, password)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            return f'Ошибка при регистрации: {e}'
        return redirect('/login')
    return render_template('register.html')

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect('/login')
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone FROM users WHERE id != %s", (session['user_id'],))
    users = cursor.fetchall()
    conn.close()
    return render_template('chat.html', users=users, current_user=session['user_name'])

@app.route('/send', methods=['POST'])
def send_message():
    data = request.get_json()
    from_user = session.get('user_id')
    to_user = data.get('to_user_id')
    message = data.get('message')
    if not (from_user and to_user and message):
        return jsonify({'error': 'Invalid data'}), 400
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (sender_id, receiver_id, message) VALUES (%s, %s, %s)",
        (from_user, to_user, message)
    )
    conn.commit()
    msg_id = cursor.lastrowid
    conn.close()
    global last_message_id
    last_message_id = msg_id
    socketio.emit('new_message', {
        'message': message,
        'from_user_id': from_user,
        'to_user_id': to_user,
        'message_id': msg_id
    })
    return jsonify({'status': 'sent'})

@app.route('/messages/<int:user_id>')
def get_messages(user_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender_id, message, timestamp FROM messages "
        "WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s) "
        "ORDER BY timestamp",
        (session['user_id'], user_id, user_id, session['user_id'])
    )
    rows = cursor.fetchall()
    conn.close()
    msgs = []
    for sid, msg, ts in rows:
        msgs.append({
            'from_me': sid == session['user_id'],
            'message': msg,
            'timestamp': ts.strftime('%H:%M')
        })
    return jsonify(msgs)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 8080)))
