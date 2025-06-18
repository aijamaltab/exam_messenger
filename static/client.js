let socket = io();
let room = null;
let username = null;
let pc = null;

const localVideo = document.getElementById("localVideo");
const remoteVideo = document.getElementById("remoteVideo");
const ringtone = document.getElementById("ringtone");

const config = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
};

async function joinCall() {
  room = document.getElementById("roomInput").value.trim();
  username = document.getElementById("usernameInput").value.trim() || "Аноним";

  if (!room) {
    alert("Введите комнату");
    return;
  }
  if (!username) {
    alert("Введите имя");
    return;
  }

  socket.emit("join", { room, username });
}

socket.on("joined", async () => {
  await setupMedia();
  addChat("Система", `Вы вошли в комнату ${room} как ${username}`);
});

socket.on("signal", async (data) => {
  if (!pc) await createPeerConnection();

  if (data.type === "offer") {
    playRingtone();
    await pc.setRemoteDescription(new RTCSessionDescription(data));
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    socket.emit("signal", { room, data: pc.localDescription });
    stopRingtone();
  } else if (data.type === "answer") {
    stopRingtone();
    if (pc.signalingState === "have-local-offer") {
      await pc.setRemoteDescription(new RTCSessionDescription(data));
    } else {
      console.warn("Нельзя установить remoteDescription answer — состояние:", pc.signalingState);
    }
  } else if (data.candidate) {
    await pc.addIceCandidate(new RTCIceCandidate(data));
  }
});



async function setupMedia() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
  localVideo.srcObject = stream;
}

async function startCall() {
  if (!room) {
    alert("Сначала войдите в комнату");
    return;
  }
  await createPeerConnection();
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  socket.emit("signal", { room, data: offer });
  playRingtone();
}

async function createPeerConnection() {
  pc = new RTCPeerConnection(config);

  pc.onicecandidate = (event) => {
    if (event.candidate) {
      socket.emit("signal", { room, data: event.candidate });
    }
  };

  pc.ontrack = (event) => {
    remoteVideo.srcObject = event.streams[0];
  };

  const stream = localVideo.srcObject;
  stream.getTracks().forEach((track) => {
    pc.addTrack(track, stream);
  });
}

// ---- Чат ----

function sendMessage() {
  const input = document.getElementById("chatInput");
  const message = input.value.trim();
  if (message && room) {
    socket.emit("chat", { room, message });
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
  ringtone.play().catch(e => console.log("Ошибка воспроизведения звонка", e));
}

function stopRingtone() {
  ringtone.pause();
  ringtone.currentTime = 0;
}
