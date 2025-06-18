// client.js

// 1. Инициализация Socket.IO с транспортом WebSocket
const socket = io({ transports: ['websocket'] });
let myId = null;
socket.on('connect', () => {
  myId = socket.id;
});

// 2. Основные переменные
let room = null;
let username = null;
let pc = null;

const localVideo = document.getElementById('localVideo');
const remoteVideo = document.getElementById('remoteVideo');
const ringtone = document.getElementById('ringtone');

// Настройки ICE: STUN + (при необходимости) TURN
const config = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    // { urls: 'turn:turn.example.com:3478', username: 'user', credential: 'pass' }
  ]
};

// 3. UI‑обработчики
document.getElementById('btnJoin').onclick = joinCall;
document.getElementById('btnCall').onclick = startCall;
document.getElementById('btnStop').onclick = stopCall;
document.getElementById('btnSend').onclick = sendMessage;

// 4. Вход в комнату
async function joinCall() {
  room = document.getElementById('roomInput').value.trim();
  username = document.getElementById('usernameInput').value.trim() || 'Аноним';
  if (!room) return alert('Введите комнату');
  if (!username) return alert('Введите имя');
  socket.emit('join', { room, username });
}

// 5. Обработка событий Socket.IO
socket.on('joined', async () => {
  await setupMedia();
  addChat('Система', `Вы вошли в комнату ${room} как ${username}`);
});

socket.on('signal', handleSignal);

socket.on('chat', ({ username: from, message }) => {
  addChat(from, message);
});

// 6. Настройка локальной аудио‑трека
async function setupMedia() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  localVideo.srcObject = stream;
}

// 7. Запуск звонка (офер)
async function startCall() {
  if (!room) return alert('Сначала войдите в комнату');
  if (!pc) pc = await createPeerConnection();

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  socket.emit('signal', { room, from: myId, data: offer });
  playRingtone();
}

// 8. Обработка входящих сигналов (offer/answer/candidate)
async function handleSignal({ room: r, from, data }) {
  if (r !== room || from === myId) return; // только чужие сигналы из нашей комнаты
  if (!pc) pc = await createPeerConnection();

  if (data.type === 'offer') {
    playRingtone();
    await pc.setRemoteDescription(data);
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    socket.emit('signal', { room, from: myId, data: answer });
    stopRingtone();

  } else if (data.type === 'answer') {
    stopRingtone();
    await pc.setRemoteDescription(data);

  } else if (data.candidate) {
    await pc.addIceCandidate(data).catch(console.error);
  }
}

// 9. Создание и настройка RTCPeerConnection
async function createPeerConnection() {
  if (pc) {
    pc.close();
    pc = null;
  }
  pc = new RTCPeerConnection(config);
  attachWebRTCLogs(pc);

  // ICE-кандидаты
  pc.onicecandidate = ({ candidate }) => {
    if (candidate) {
      socket.emit('signal', { room, from: myId, data: candidate });
    }
  };

  // Приём удалённого потока
  pc.ontrack = ({ streams }) => {
    remoteVideo.srcObject = streams[0];
  };

  // Добавляем локальный аудио‑трек
  const stream = localVideo.srcObject;
  stream.getTracks().forEach(track => pc.addTrack(track, stream));

  return pc;
}

// 10. Остановка звонка
function stopCall() {
  if (pc) {
    pc.close();
    pc = null;
  }
  stopRingtone();
  addChat('Система', 'Звонок остановлен');
}

// 11. Чат
function sendMessage() {
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg || !room) return;
  socket.emit('chat', { room, username, message: msg });
  addChat('Вы', msg);
  input.value = '';
}

function addChat(user, text) {
  const chatBox = document.getElementById('chatBox');
  const div = document.createElement('div');
  div.innerHTML = `<strong>${user}:</strong> ${text}`;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// 12. Рингтон
function playRingtone() {
  ringtone.play().catch(() => {});
}
function stopRingtone() {
  ringtone.pause();
  ringtone.currentTime = 0;
}

// 13. Логи WebRTC‑состояний
function attachWebRTCLogs(pc) {
  const events = [
    'icegatheringstatechange',
    'iceconnectionstatechange',
    'signalingstatechange',
    'connectionstatechange'
  ];
  events.forEach(evt => {
    pc.addEventListener(evt, () => {
      console.log(`WebRTC ${evt}:`, pc[evt.replace('statechange','State')]);
    });
  });
}
