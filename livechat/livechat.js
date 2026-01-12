const state = {
  mode: "none",
  streamId: null,
  liveStreamId: null,
  cursor: null,
  events: [],
  polling: null,
  status: "",
};

const elements = {
  modePill: document.getElementById("mode-pill"),
  streamList: document.getElementById("stream-list"),
  streamSearch: document.getElementById("stream-search"),
  refreshStreams: document.getElementById("refresh-streams"),
  clearReplay: document.getElementById("clear-replay"),
  chatLog: document.getElementById("chat-log"),
  statusLabel: document.getElementById("status-label"),
  loadMore: document.getElementById("load-more"),
  resetReplay: document.getElementById("reset-replay"),
  syntheticForm: document.getElementById("synthetic-form"),
  syntheticStatus: document.getElementById("synthetic-status"),
};

function setStatus(message, isError = false) {
  state.status = message;
  elements.statusLabel.textContent = message || "";
  elements.statusLabel.classList.toggle("error", isError);
}

function updateMode(mode, streamId, liveStreamId) {
  state.mode = mode || "none";
  state.streamId = streamId || null;
  state.liveStreamId = liveStreamId || null;
  elements.modePill.textContent = state.mode;
}

function getPlatformLabel(event) {
  return (event.source_platform || "unknown").toUpperCase();
}

function renderEvents() {
  elements.chatLog.innerHTML = "";
  if (!state.events.length) {
    elements.chatLog.innerHTML = `<div class="empty-state">No chat events available.</div>`;
    return;
  }

  state.events.forEach((event) => {
    const wrapper = document.createElement("div");
    wrapper.className = "chat-message";

    const avatar = document.createElement("img");
    avatar.className = "avatar";
    avatar.src = event.author.avatar_url || "../services/chat_replay/static/assets/icons/ui/profile.svg";
    avatar.alt = `${event.author.display_name} avatar`;

    const body = document.createElement("div");

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.innerHTML = `
      <strong>${event.author.display_name}</strong>
      <span class="platform">${getPlatformLabel(event)}</span>
      <span>${new Date(event.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
    `;

    const flags = document.createElement("div");
    flags.className = "flags";
    const flagLabels = [];
    if (event.flags?.is_synthetic) flagLabels.push("synthetic");
    if (event.flags?.is_system) flagLabels.push("system");
    if (event.flags?.is_highlighted) flagLabels.push("highlighted");
    flags.textContent = flagLabels.length ? flagLabels.join(" • ") : "";

    const text = document.createElement("div");
    text.className = "text";
    text.textContent = event.content.text;

    body.appendChild(meta);
    if (flags.textContent) {
      body.appendChild(flags);
    }
    body.appendChild(text);

    wrapper.appendChild(avatar);
    wrapper.appendChild(body);

    elements.chatLog.appendChild(wrapper);
  });
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
}

async function fetchStreams() {
  try {
    const response = await fetch("/api/streams");
    const data = await response.json();
    updateMode(
      data.active_context?.mode,
      data.active_context?.stream_id,
      data.active_context?.live_stream_id
    );
    renderStreamList(data.streams || []);
  } catch (error) {
    setStatus("Failed to load streams", true);
  }
}

function renderStreamList(streams) {
  const filter = elements.streamSearch.value.toLowerCase();
  elements.streamList.innerHTML = "";
  const filtered = streams.filter((stream) => {
    const label = `${stream.stream_id || ""} ${stream.title || ""}`.toLowerCase();
    return label.includes(filter);
  });

  if (!filtered.length) {
    elements.streamList.innerHTML = `<div class="empty-state">No streams with chat yet.</div>`;
    return;
  }

  filtered.forEach((stream) => {
    const card = document.createElement("div");
    card.className = "stream-card";
    if (stream.stream_id === state.streamId) {
      card.classList.add("active");
    }
    card.innerHTML = `
      <div class="title">${stream.title || stream.stream_id}</div>
      <div class="meta">${stream.stream_id}</div>
      <div class="meta">Platforms: ${(stream.platforms_active || []).join(", ") || "—"}</div>
    `;
    card.addEventListener("click", () => selectReplay(stream.stream_id));
    elements.streamList.appendChild(card);
  });
}

async function selectReplay(streamId) {
  try {
    const response = await fetch("/api/replay/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stream_id: streamId }),
    });
    const data = await response.json();
    updateMode(data.context?.mode, data.context?.stream_id, data.context?.live_stream_id);
    state.cursor = null;
    await loadReplayPage(true);
  } catch (error) {
    setStatus("Failed to select replay", true);
  }
}

async function clearReplay() {
  try {
    const response = await fetch("/api/replay/clear", { method: "POST" });
    const data = await response.json();
    updateMode(data.context?.mode, data.context?.stream_id, data.context?.live_stream_id);
    state.cursor = null;
    state.events = [];
    renderEvents();
    if (state.mode === "live") {
      startLivePolling();
    } else {
      stopLivePolling();
    }
  } catch (error) {
    setStatus("Failed to clear replay", true);
  }
}

async function loadReplayPage(reset = false) {
  if (!state.streamId) {
    renderEvents();
    return;
  }
  try {
    const url = new URL("/api/chat/events", window.location.origin);
    url.searchParams.set("stream_id", state.streamId);
    url.searchParams.set("limit", "50");
    if (!reset && state.cursor) {
      url.searchParams.set("cursor", state.cursor);
    }

    const response = await fetch(url.toString());
    const data = await response.json();
    updateMode(data.context?.mode, data.context?.stream_id, data.context?.live_stream_id);
    state.cursor = data.next_cursor || state.cursor;
    if (reset) {
      state.events = data.events || [];
    } else {
      state.events = [...state.events, ...(data.events || [])];
    }
    renderEvents();
  } catch (error) {
    setStatus("Failed to load replay", true);
  }
}

async function pollLive() {
  if (!state.streamId && state.liveStreamId) {
    state.streamId = state.liveStreamId;
  }
  if (!state.streamId) {
    setStatus("No active live stream", true);
    return;
  }
  try {
    const url = new URL("/api/chat/tail", window.location.origin);
    url.searchParams.set("stream_id", state.streamId);
    url.searchParams.set("limit", "60");
    const response = await fetch(url.toString());
    const data = await response.json();
    updateMode(data.context?.mode, data.context?.stream_id, data.context?.live_stream_id);
    state.events = data.events || [];
    renderEvents();
  } catch (error) {
    setStatus("Live polling failed", true);
  }
}

function startLivePolling() {
  stopLivePolling();
  pollLive();
  state.polling = setInterval(pollLive, 2500);
}

function stopLivePolling() {
  if (state.polling) {
    clearInterval(state.polling);
    state.polling = null;
  }
}

async function sendSynthetic(formData) {
  const payload = {
    stream_id: formData.get("stream_id"),
    author_source: formData.get("author_source"),
    author_id: formData.get("author_id"),
    display_name: formData.get("display_name"),
    avatar_url: formData.get("avatar_url"),
    text: formData.get("text"),
  };

  const token = formData.get("token");
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch("/api/chat/synthetic", {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Failed to send synthetic message");
  }
  return data.event;
}

elements.streamSearch.addEventListener("input", fetchStreams);
elements.refreshStreams.addEventListener("click", fetchStreams);
elements.clearReplay.addEventListener("click", clearReplay);
elements.loadMore.addEventListener("click", () => loadReplayPage(false));
elements.resetReplay.addEventListener("click", () => loadReplayPage(true));

elements.syntheticForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(elements.syntheticForm);
  try {
    const eventPayload = await sendSynthetic(formData);
    elements.syntheticStatus.textContent = "Synthetic message queued.";
    elements.syntheticStatus.classList.remove("error");
    elements.syntheticForm.reset();
    if (state.mode === "live") {
      state.events = [...state.events, eventPayload];
      renderEvents();
    }
  } catch (error) {
    elements.syntheticStatus.textContent = error.message;
    elements.syntheticStatus.classList.add("error");
  }
});

(async function init() {
  await fetchStreams();
  if (state.mode === "replay") {
    await loadReplayPage(true);
  } else if (state.mode === "live") {
    startLivePolling();
  } else {
    renderEvents();
  }
})();
