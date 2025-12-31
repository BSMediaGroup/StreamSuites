// Placeholder mock data for unified chat replay surfaces.
// This file is intentionally static and will be replaced by runtime-fed data in future stages.

const chatMessages = [
  {
    message_id: "yt-001",
    platform: "youtube",
    author: { display_name: "PixelPilot", color: "#e91e63", badges: ["member", "mod"] },
    message: { text: "Welcome to the replay scaffold!", emotes: [":wave:"] },
    timestamp: { unix: 1700000001, iso: "2023-11-14T00:00:01Z" },
    metadata: { is_mod: true, is_member: true, is_superchat: false, raw: {} }
  },
  {
    message_id: "tw-002",
    platform: "twitch",
    author: { display_name: "CodeCrafter", color: "#9146ff", badges: ["vip"] },
    message: { text: "Bits of joy coming soon ⟠ placeholder only", emotes: ["Kappa"] },
    timestamp: { unix: 1700000005, iso: "2023-11-14T00:00:05Z" },
    metadata: { is_mod: false, is_member: false, is_superchat: false, raw: {} }
  },
  {
    message_id: "rm-003",
    platform: "rumble",
    author: { display_name: "SignalSeeker", color: "#3ddc84", badges: ["founder"] },
    message: { text: "Rumble replay placeholder — no live ingestion yet", emotes: [] },
    timestamp: { unix: 1700000010, iso: "2023-11-14T00:00:10Z" },
    metadata: { is_mod: false, is_member: true, is_superchat: false, raw: {} }
  },
  {
    message_id: "kc-004",
    platform: "kick",
    author: { display_name: "NightRunner", color: "#00e701", badges: ["subscriber"] },
    message: { text: "Kick chat placeholder activated", emotes: [":rocket:"] },
    timestamp: { unix: 1700000016, iso: "2023-11-14T00:00:16Z" },
    metadata: { is_mod: false, is_member: true, is_superchat: false, raw: {} }
  },
  {
    message_id: "un-005",
    platform: "unknown",
    author: { display_name: "MysteryUser", color: "#9e9e9e", badges: [] },
    message: { text: "Generic source to validate neutral pathways", emotes: [] },
    timestamp: { unix: 1700000021, iso: "2023-11-14T00:00:21Z" },
    metadata: { is_mod: false, is_member: false, is_superchat: false, raw: {} }
  }
];

function renderChatLog(target, entries) {
  target.innerHTML = "";
  entries.forEach((entry) => {
    const wrapper = document.createElement("article");
    wrapper.className = target.dataset.overlay === "true" ? "overlay-entry" : "chat-entry";

    if (target.dataset.overlay === "true") {
      wrapper.innerHTML = `
        <div class="meta">
          <span class="author" style="color:${entry.author.color || '#e5ecf5'}">${entry.author.display_name}</span>
          <span class="badges">${(entry.author.badges || [])
            .map((badge) => `<span class="badge">${badge}</span>`) 
            .join("")}</span>
          <span class="platform">${entry.platform}</span>
        </div>
        <div class="message">${entry.message.text}</div>
      `;
    } else {
      wrapper.innerHTML = `
        <span class="timestamp">${new Date(entry.timestamp.unix * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        <div class="meta">
          <span class="author" style="color:${entry.author.color || '#e5ecf5'}">${entry.author.display_name}</span>
          <span class="badges">${(entry.author.badges || [])
            .map((badge) => `<span class="badge">${badge}</span>`) 
            .join("")}</span>
          <span class="platform">${entry.platform}</span>
        </div>
        <div class="message">${entry.message.text}</div>
      `;
    }

    target.appendChild(wrapper);
  });
}
