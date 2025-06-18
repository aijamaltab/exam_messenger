from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

users = {}  # sid -> {"room": ..., "username": ...}

@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("join")
def on_join(data):
    room = data.get("room")
    username = data.get("username", "Аноним")
    users[request.sid] = {"room": room, "username": username}
    join_room(room)
    emit("joined", {"room": room}, room=request.sid)
    print(f"{username} joined room {room}")

@socketio.on("signal")
def on_signal(data):
    room = users.get(request.sid, {}).get("room")
    if room:
        emit("signal", data["data"], room=room, include_self=False)

@socketio.on("chat")
def on_chat(data):
    room = users.get(request.sid, {}).get("room")
    username = users.get(request.sid, {}).get("username", "Аноним")
    message = data.get("message", "")
    if room and message:
        emit("chat", {"username": username, "message": message}, room=room, include_self=False)

@socketio.on("disconnect")
def on_disconnect():
    user = users.pop(request.sid, None)
    if user:
        print(f"{user['username']} disconnected from room {user['room']}")

if __name__ == "__main__":
    socketio.run(app, debug=True)
