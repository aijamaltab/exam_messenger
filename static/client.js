// Получаем уникальный ID сокета, чтобы не обрабатывать собственные сигналы
let socket = io();
let myId = null;
socket.on("connect", () => {
  myId = socket.id;
});

let room = null;
let username = null;
let pc = null;

const localVideo = document.getElementById("localVideo");
const remoteVideo = document.getElementById("remoteVideo");
const ringtone = document.getElementById("ringtone");

const config = {
  iceServers: [
    { urls: "stun:stun.l.google.com:19302" },
    // при необходимости можно добавить TURN:
    // {
    //   urls: "turn:turn.example.com:3478",
    //   username: "user",
    //   credential: "pass"
    // }
  ],
};

async function joinCall() {
  room = document.getElementById("roomInput").value.trim();
  username = document.getElementById("usernameInput").value.trim() || "Аноним";

  if (!room) return alert("Введите комнату");
  if (!username) return alert("Введите имя");

  socket.emit("join", { room, username });
}

socket.on("joined", async () => {
  await setupMedia();
  addChat("Система", `Вы вошли в комнату ${room} как ${username}`);
});

socket.on("signal", async ({ room: incomingRoom, from, data: payload }) => {
  // Игнорируем сигналы из других комнат и свои же
  if (incomingRoom !== room || from === myId) return;

  // Если ещё нет PeerConnection — создаём новый
  if (!pc) {
    pc = await createPeerConnection();
  }

  if (payload.type === "offer") {
    playRingtone();
    await pc.setRemoteDescription(new RTCSessionDescription(payload));
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    socket.emit("signal", { room, from: myId, data: pc.localDescription });
    stopRingtone();

  } else if (payload.type === "answer") {
    stopRingtone();
    await pc.setRemoteDescription(new RTCSessionDescription(payload));

  } else if (payload.candidate) {
    try {
      await pc.addIceCandidate(new RTCIceCandidate(payload));
    } catch (e) {
      console.error("Ошибка при добавлении ICE-кандидата:", e);
    }
  }
});

async function setupMedia() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
  localVideo.srcObject = stream;
}

async function startCall() {
  if (!room) return alert("Сначала войдите в комнату");
  if (!pc) pc = await createPeerConnection();

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  socket.emit("signal", { room, from: myId, data: offer });
  playRingtone();
}

async function createPeerConnection() {
  // Закрываем старое соединение, если есть
  if (pc) {
    pc.close();
    pc = null;
  }

  pc = new RTCPeerConnection(config);

  // Логируем все ключевые состояния
  pc.onicegatheringstatechange = () =>
    console.log("ICE gathering state:", pc.iceGatheringState);
  pc.oniceconnectionstatechange = () =>
    console.log("ICE connection state:", pc.iceConnectionState);
  pc.onsignalingstatechange = () =>
    console.log("Signaling state:", pc.signalingState);
  pc.onconnectionstatechange = () =>
    console.log("PeerConnection state:", pc.connectionState);

  // Отправка ICE-кандидатов
  pc.onicecandidate = (e) => {
    if (e.candidate) {
      socket.emit("signal", { room, from: myId, data: e.candidate });
      console.log("Sent ICE candidate:", e.candidate);
    }
  };

  // Приём медиапотока
  pc.ontrack = (e) => {
    console.log("Received remote track");
    remoteVideo.srcObject = e.streams[0];
  };

  // Добавляем локальные треки
  const stream = localVideo.srcObject;
  stream.getTracks().forEach((track) => {
    pc.addTrack(track, stream);
    console.log("Added local track:", track.kind);
  });

  return pc;
}

// ---- Чат ----

function sendMessage() {
  const input = document.getElementById("chatInput");
  const message = input.value.trim();
  if (message && room) {
    socket.emit("chat", { room, username, message });
    addChat("Вы", message);
    input.value = "";
  }
}

function addChat(sender, message) {
  const chatBox = document.getElementById("chatBox");
  const msg = document.createElement("div");
  msg.style.marginBottom = "5px";
  msg.innerHTML = `<strong>${sender}:</strong> ${message}`;
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

socket.on("chat", (data) => {
  addChat(data.username || "Собеседник", data.message);
});

// ---- Звонок ----

function playRingtone() {
  ringtone.play().catch((e) => console.log("Ошибка воспроизведения звонка", e));
}

function stopRingtone() {
  ringtone.pause();
  ringtone.currentTime = 0;
}
