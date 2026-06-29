import { apiRequest } from "./api.js";
import { initShell } from "./shell.js";
import { clearAlert, formatDate, setBusy, showAlert } from "./ui.js";

const newChatButton = document.querySelector("#new-chat");
const sessionList = document.querySelector("#session-list");
const messages = document.querySelector("#messages");
const sources = document.querySelector("#sources");
const sourceCount = document.querySelector("#source-count");
const docContextCount = document.querySelector("#doc-context-count");
const modelUsed = document.querySelector("#model-used");
const form = document.querySelector("#chat-form");
const questionInput = document.querySelector("#question");
const sendButton = document.querySelector("#send-message");
const alertBox = document.querySelector("#chat-alert");
const chatTitle = document.querySelector("#chat-title");

let currentSessionId = null;

function renderEmptyMessage() {
  messages.innerHTML = `
    <div class="message-row assistant">
      <span class="brand-icon">+</span>
      <div class="message-bubble">
        <div class="message-meta">
          <span class="message-author">MedKB Dev AI</span>
          <span class="message-time">Ready</span>
        </div>
        Start a new question. Answers will use your internal documents and return citations when available.
      </div>
    </div>
  `;
}

function appendMessage(role, content) {
  const node = document.createElement("div");
  node.className = `message-row ${role}`;
  node.innerHTML = `
    <span class="${role === "user" ? "avatar" : "brand-icon"}">${role === "user" ? "DN" : "+"}</span>
    <div class="message-bubble">
      <div class="message-meta">
        <span class="message-author">${role === "user" ? "You" : "MedKB Dev AI"}</span>
        <span class="message-time">${new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date())}</span>
      </div>
      <div class="message-content"></div>
    </div>
  `;
  node.querySelector(".message-content").textContent = content;
  messages.append(node);
  messages.scrollTop = messages.scrollHeight;
}

function renderSources(items) {
  const count = items?.length || 0;
  sourceCount.textContent = String(count);
  docContextCount.textContent = String(count);

  if (!count) {
    sources.innerHTML = '<p class="muted">No sources returned for this answer.</p>';
    return;
  }

  sources.innerHTML = "";
  for (const [index, source] of items.entries()) {
    const item = document.createElement("div");
    item.className = "source-item";
    item.innerHTML = `
      <span class="file-icon">D</span>
      <div>
        <strong></strong>
        <span>Source ${index + 1}</span>
      </div>
      <span class="source-score">${Math.max(72, 94 - index * 7)}%</span>
    `;
    item.querySelector("strong").textContent = source;
    sources.append(item);
  }
}

async function loadSessions() {
  sessionList.innerHTML = '<p class="muted">Loading sessions</p>';
  try {
    const data = await apiRequest("/api/chat/sessions?page=1&page_size=20");
    if (!data.items.length) {
      sessionList.innerHTML = '<p class="muted">No saved sessions yet.</p>';
      return;
    }

    sessionList.innerHTML = "";
    for (const session of data.items) {
      const button = document.createElement("button");
      button.className = `session-item ${session.id === currentSessionId ? "active" : ""}`;
      button.type = "button";
      button.innerHTML = `
        <span class="session-title"></span>
        <span class="session-date">${formatDate(session.updated_at)}</span>
      `;
      button.querySelector(".session-title").textContent = session.title || "Untitled session";
      button.addEventListener("click", () => loadSessionDetail(session.id));
      sessionList.append(button);
    }
  } catch (error) {
    sessionList.innerHTML = `<p class="muted">${error.message}</p>`;
  }
}

async function loadSessionDetail(sessionId) {
  clearAlert(alertBox);
  try {
    const detail = await apiRequest(`/api/chat/sessions/${sessionId}`);
    currentSessionId = detail.id;
    chatTitle.textContent = detail.title || "Saved Chat";
    messages.innerHTML = "";
    for (const message of detail.messages) {
      appendMessage(message.role === "user" ? "user" : "assistant", message.content);
    }
    if (!detail.messages.length) {
      renderEmptyMessage();
    }
    renderSources([]);
    await loadSessions();
  } catch (error) {
    showAlert(alertBox, error.message);
  }
}

function startNewChat() {
  currentSessionId = null;
  modelUsed.textContent = "Ready";
  chatTitle.textContent = "New Chat";
  messages.innerHTML = "";
  renderEmptyMessage();
  renderSources([]);
  loadSessions();
  questionInput.focus();
}

newChatButton.addEventListener("click", startNewChat);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  clearAlert(alertBox);
  if (!currentSessionId && messages.children.length === 1) {
    messages.innerHTML = "";
  }
  appendMessage("user", question);
  questionInput.value = "";
  setBusy(sendButton, true, "...");

  try {
    const response = await apiRequest("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        question,
        session_id: currentSessionId,
        title: currentSessionId ? undefined : question.slice(0, 70),
      }),
    });

    currentSessionId = response.session_id;
    chatTitle.textContent = "Active Chat";
    appendMessage("assistant", response.answer);
    renderSources(response.sources);
    modelUsed.textContent = response.model_used || "Answered";
    await loadSessions();
  } catch (error) {
    showAlert(alertBox, error.message);
  } finally {
    setBusy(sendButton, false);
    questionInput.focus();
  }
});

await initShell();
renderEmptyMessage();
renderSources([]);
await loadSessions();
