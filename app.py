import os
from flask import Flask, render_template, request, redirect, session, jsonify
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

# MySQL connection helper
def get_connection():
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        result = urlparse(db_url)
        config = {
            'host': result.hostname,
            'port': result.port,
            'user': result.username,
            'password': result.password,
            'database': result.path.lstrip('/')
        }
    else:
        config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', ''),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', '')
        }
    print(f">> Connecting to MySQL: {config['user']}@{config['host']}:{config['port']}/{config['database']}")
    return mysql.connector.connect(**config)

connected_users = {}

@socketio.on('connect')
def on_connect():
    # здесь session['user_id'] уже должен быть установлен вашим login-миддлварем
    user_id = session.get('user_id')
    if user_id:
        connected_users[user_id] = request.sid
        print(f'User {user_id} connected as {request.sid}')

@socketio.on('disconnect')
def on_disconnect():
    # вычистим запись
    for u, sid in list(connected_users.items()):
        if sid == request.sid:
            connected_users.pop(u)
            print(f'User {u} disconnected')
            break

@socketio.on('register')
def on_register(data):
    # альтернативный путь регистрации
    user_id = data.get('user_id')
    if user_id:
        connected_users[user_id] = request.sid

@socketio.on('call-user')
def on_call_user(data):
    target = data.get('to')
    offer = data.get('offer')
    sid = connected_users.get(target)
    if sid:
        emit('call-made', {'from': session['user_id'], 'offer': offer}, room=sid)
    else:
        print(f'Target {target} not connected')

@socketio.on('make-answer')
def on_make_answer(data):
    target = data.get('to')
    answer = data.get('answer')
    sid = connected_users.get(target)
    if sid:
        emit('answer-made', {'from': session['user_id'], 'answer': answer}, room=sid)

@socketio.on('ice-candidate')
def on_ice_candidate(data):
    target = data.get('to')
    candidate = data.get('candidate')
    sid = connected_users.get(target)
    if sid:
        emit('ice-candidate', {'from': session['user_id'], 'candidate': candidate}, room=sid)
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
            cursor.execute("INSERT INTO users (name, phone, password) VALUES (%s, %s, %s)", (name, phone, password))
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
    return render_template('chat.html', users=users, current_user=session['user_name'], current_user_id=session['user_id'])

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
    cursor.execute("INSERT INTO messages (sender_id, receiver_id, message) VALUES (%s, %s, %s)", (from_user, to_user, message))
    conn.commit()
    msg_id = cursor.lastrowid
    conn.close()
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
    cursor.execute("SELECT sender_id, message, timestamp FROM messages WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s) ORDER BY timestamp", (session['user_id'], user_id, user_id, session['user_id']))
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

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080)
