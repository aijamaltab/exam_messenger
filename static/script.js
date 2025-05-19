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
});
