const socket = io();
const chat = document.getElementById("chat");

function sendMessage() {
  const sender = document.getElementById("sender").value || "Anonymous";
  const message = document.getElementById("message").value;
  if (!message) return;

  socket.emit("send_message", { sender, message });
  document.getElementById("message").value = "";
}

socket.on("receive_message", function(data) {
  const msgDiv = document.createElement("div");
  msgDiv.classList.add("message");
  msgDiv.classList.add(data.sender === document.getElementById("sender").value ? "from-you" : "from-other");
  msgDiv.innerHTML = `<strong>${data.sender}</strong>: ${data.message}`;
  chat.appendChild(msgDiv);
  chat.scrollTop = chat.scrollHeight;


document.addEventListener('DOMContentLoaded', () => {
  let ua, session;

  // 1) Получаем SIP-конфиг с бэкенда
  fetch('/sip-config')
    .then(r => {
      if (!r.ok) throw new Error('Unauthorized or config error');
      return r.json();
    })
    .then(cfg => {
      // 2) Инициализируем JsSIP
      const socket = new JsSIP.WebSocketInterface(cfg.wsServers[0]);
      ua = new JsSIP.UA({
        sockets:       [ socket ],
        uri:           cfg.uri,               // например "1001@sip.zadarma.com"
        authorizationUser: cfg.authorizationUser,
        password:      cfg.password,
        session_timers: false
      });

      ua.on('registered', () =>
        console.log('SIP registered OK')
      );

      ua.on('registrationFailed', e =>
        console.error('Registration failed:', e.cause)
      );

      ua.on('newRTCSession', data => {
        session = data.session;

        // когда приходит или устанавливается соединение – подцепляем поток
        session.connection.addEventListener('addstream', ev => {
          document.getElementById('remoteAudio').srcObject = ev.stream;
        });

        // включаем/выключаем кнопки
        session.on('connecting', () => {
          document.getElementById('call-btn').disabled = true;
          document.getElementById('hangup-btn').disabled = false;
        });
        session.on('ended',   () => resetButtons());
        session.on('failed',  () => resetButtons());
      });

      ua.start();
    })
    .catch(console.error);

  // 4) Офферы to call / hangup
  document.getElementById('call-btn').addEventListener('click', () => {
    const target = document.getElementById('phone-input').value;
    if (!ua) return alert('SIP not ready');
    ua.call(target, {
      mediaConstraints: { audio: true, video: false }
    });
  });

  document.getElementById('hangup-btn').addEventListener('click', () => {
    if (session) session.terminate();
  });

  function resetButtons() {
    document.getElementById('call-btn').disabled = false;
    document.getElementById('hangup-btn').disabled = true;
  }
});

});
