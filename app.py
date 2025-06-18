import os
from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
from datetime import datetime
from dotenv import load_dotenv
import mysql.connector
from urllib.parse import urlparse
from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
socketio = SocketIO(app, manage_session=False)



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

@app.route('/')
def home():
    return redirect('/chat') if 'user_id' in session else redirect('/login')


@socketio.on('connect')
def on_connect():
    user_id = session.get('user_id')
    if user_id:
        user_id = str(user_id)
        connected_users[user_id] = request.sid
        print(f'[connect] User {user_id} connected as {request.sid}')
    else:
        print('[connect] No user_id in session')
        return False  # reject connection


@socketio.on('disconnect')
def on_disconnect():
    for uid, sid in list(connected_users.items()):
        if sid == request.sid:
            connected_users.pop(uid, None)
            print(f'[disconnect] User {uid} disconnected (sid: {sid})')
            break


@socketio.on('register')
def on_register(data):
    print('→ [server] register:', data, '   all users map:', connected_users)
    try:
        user_id = str(data['user_id'])
        connected_users[user_id] = request.sid
        print(f'    mapped user {user_id} -> {request.sid}')
    except Exception as e:
        print(f'✖ Error in register: {e}')


@socketio.on('call-user')
def on_call_user(data):
    try:
        target = str(data.get('to'))
        offer = data.get('offer')
        print('→ [server] call-user:', data, ' map:', connected_users)

        sid = connected_users.get(target)
        if not sid:
            print(f'    Target {target} not connected!')
            return

        from_sid = request.sid
        from_user = next((uid for uid, s in connected_users.items() if s == from_sid), None)
        if from_user:
            emit('call-made', {
                'from': from_user,
                'offer': offer
            }, room=sid)
    except Exception as e:
        print(f'✖ Error in call-user: {e}')


@socketio.on('make-answer')
def on_make_answer(data):
    try:
        target = str(data.get('to'))
        answer = data.get('answer')

        sid = connected_users.get(target)
        if not sid:
            print(f'[make-answer] Target {target} not connected!')
            return

        from_user = session.get('user_id')
        if from_user:
            emit('answer-made', {'from': str(from_user), 'answer': answer}, room=sid)
    except Exception as e:
        print(f'✖ Error in make-answer: {e}')


@socketio.on('ice-candidate')
def on_ice_candidate(data):
    try:
        target = str(data.get('to'))
        candidate = data.get('candidate')

        sid = connected_users.get(target)
        if not sid:
            print(f'[ice-candidate] Target {target} not connected!')
            return

        from_user = session.get('user_id')
        if from_user:
            emit('ice-candidate', {'from': str(from_user), 'candidate': candidate}, room=sid)
    except Exception as e:
        print(f'✖ Error in ice-candidate: {e}')

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
    socketio.run(app, debug=True)
