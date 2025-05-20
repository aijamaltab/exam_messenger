import os
from flask import Flask, render_template, request, redirect, session, url_for, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import get_connection

from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_strong_secret_key'
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


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
        print(f"[LOG] Регистрация: name={name}, phone={phone}, password_hash={password}")

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, phone, password) VALUES (%s, %s, %s)",
                (name, phone, password)
            )
            conn.commit()
            cursor.close()
            conn.close()
            print("[LOG] Пользователь успешно зарегистрирован")
        except Exception as e:
            print("[ERROR] Ошибка при регистрации:", e)
            return 'Такой номер уже зарегистрирован или произошла другая ошибка'

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
def send():
    try:
        print("Получен запрос на отправку")
        print("Session user:", session.get('user_id'))
        data = request.get_json()
        print("Полученные данные:", data)

        from_user_id = session.get('user_id')
        to_user_id = data.get('to_user_id')
        message = data.get('message')  

        if not from_user_id or not to_user_id or not message:
            print("Ошибка: пустые данные")
            return jsonify({'error': 'Invalid data'}), 400

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (sender_id, receiver_id, message) VALUES (%s, %s, %s)",
            (from_user_id, to_user_id, message)
        )
        conn.commit()
        conn.close()

        return jsonify({'message': 'OK'}), 200
    except Exception as e:
        print("ОШИБКА НА СЕРВЕРЕ:", e)
        return jsonify({'error': 'Server error', 'details': str(e)}), 500


def serialize_message(msg, current_user_id):
    return {
        "id": msg.id,
        "message": msg.messages,
        "from_me": msg.from_user_id == current_user_id,
        "timestamp": msg.timestamp.strftime('%H:%M')  # формат только время, как в WhatsApp
    }

@app.route('/messages/<int:user_id>')
def get_messages(user_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sender_id, message, file_path, timestamp FROM messages
        WHERE (sender_id = %s AND receiver_id = %s)
           OR (sender_id = %s AND receiver_id = %s)
        ORDER BY timestamp
    """, (session['user_id'], user_id, user_id, session['user_id']))
    data = cursor.fetchall()
    conn.close()

    messages = []
    for sender_id, message, file_path, timestamp in data:
        messages.append({
            'from_me': sender_id == session['user_id'],
            'message': message,
            'file_path': file_path,
            'timestamp': timestamp.strftime('%H:%M')
        })

    return jsonify(messages)



@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
  
@app.route('/users')
def get_users():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401


    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone FROM users WHERE id != %s", (session['user_id'],))
    users = cursor.fetchall()
    conn.close()

    users_list = []
    for u in users:
        users_list.append({
            'id': u[0],
            'name': u[1],
            'phone': u[2]

        })
    return {'users': users_list}


