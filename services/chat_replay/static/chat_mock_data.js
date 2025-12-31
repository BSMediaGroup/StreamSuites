// Placeholder mock data for unified chat replay surfaces.
// This file is intentionally static and will be replaced by runtime-fed data in future stages.

const chatMessages = [
  {
    message_id: "yt-001",
    platform: "youtube",
    author: {
      display_name: "PixelPilot",
      avatar_url: "../../docs/assets/placeholders/streamsuites.png", // Placeholder avatar
      color: "#e91e63",
      badges: ["member", "mod"]
    },
    message: { text: "Welcome to the replay scaffold!", emotes: [":wave:"] },
    timestamp: { unix: 1700000001, iso: "2023-11-14T00:00:01Z" },
    metadata: { is_mod: true, is_member: true, is_superchat: false, raw: {} }
  },
  {
    message_id: "tw-002",
    platform: "twitch",
    author: {
      display_name: "CodeCrafter",
      avatar_url: null, // Exercise fallback avatar
      color: "#9146ff",
      badges: ["vip"]
    },
    message: { text: "Bits of joy coming soon ⟠ placeholder only", emotes: ["Kappa"] },
    timestamp: { unix: 1700000005, iso: "2023-11-14T00:00:05Z" },
    metadata: { is_mod: false, is_member: false, is_superchat: false, raw: {} }
  },
  {
    message_id: "rm-003",
    platform: "rumble",
    author: {
      display_name: "SignalSeeker",
      avatar_url: "../../docs/assets/placeholders/daniel.png", // Placeholder avatar
      color: "#3ddc84",
      badges: ["founder"]
    },
    message: { text: "Rumble replay placeholder — no live ingestion yet", emotes: [] },
    timestamp: { unix: 1700000010, iso: "2023-11-14T00:00:10Z" },
    metadata: { is_mod: false, is_member: true, is_superchat: false, raw: {} }
  },
  {
    message_id: "kc-004",
    platform: "kick",
    author: {
      display_name: "NightRunner",
      avatar_url: "../../docs/assets/placeholders/hotdog.png", // Placeholder avatar
      color: "#00e701",
      badges: ["subscriber"]
    },
    message: { text: "Kick chat placeholder activated", emotes: [":rocket:"] },
    timestamp: { unix: 1700000016, iso: "2023-11-14T00:00:16Z" },
    metadata: { is_mod: false, is_member: true, is_superchat: false, raw: {} }
  },
  {
    message_id: "un-005",
    platform: "unknown",
    author: {
      display_name: "MysteryUser",
      avatar_url: "", // Explicit empty string to verify fallback path
      color: null,
      badges: []
    },
    message: { text: "Generic source to validate neutral pathways", emotes: [] },
    timestamp: { unix: 1700000021, iso: "2023-11-14T00:00:21Z" },
    metadata: { is_mod: false, is_member: false, is_superchat: false, raw: {} }
  }
];

function renderChatLog(target, entries) {
  const defaultAvatarSrc = "../../docs/assets/icons/ui/profile.svg";

  target.innerHTML = "";
  entries.forEach((entry) => {
    const wrapper = document.createElement("article");
    const overlayMode = target.dataset.overlay === "true";
    wrapper.className = overlayMode ? "overlay-entry" : "chat-entry";

    const avatarShell = document.createElement("div");
    avatarShell.className = "avatar-shell";
    const avatarImg = document.createElement("img");
    avatarImg.className = "avatar";
    avatarImg.alt = `${entry.author.display_name || "Chatter"} avatar`;
    const preferredAvatar = entry.author.avatar_url && entry.author.avatar_url !== "" ? entry.author.avatar_url : defaultAvatarSrc;
    avatarImg.src = preferredAvatar;
    avatarImg.loading = "lazy";
    avatarImg.referrerPolicy = "no-referrer";
    if (preferredAvatar === defaultAvatarSrc) {
      avatarImg.dataset.fallbackApplied = "true";
      avatarImg.classList.add("is-fallback");
    }
    avatarImg.onerror = () => {
      if (avatarImg.dataset.fallbackApplied) return;
      avatarImg.dataset.fallbackApplied = "true";
      avatarImg.src = defaultAvatarSrc;
      avatarImg.classList.add("is-fallback");
      avatarImg.style.background = `radial-gradient(circle, rgba(255,255,255,0.06), transparent 62%)`;
    };
    avatarShell.appendChild(avatarImg);

    const body = document.createElement("div");
    body.className = "entry-body";

    const metaLine = document.createElement("div");
    metaLine.className = "meta-line";

    const platform = document.createElement("span");
    platform.className = "platform-badge";
    platform.textContent = entry.platform;
    metaLine.appendChild(platform);

    const author = document.createElement("span");
    author.className = "author";
    author.style.color = entry.author.color || "#e5ecf5";
    author.textContent = entry.author.display_name;
    metaLine.appendChild(author);

    const badges = document.createElement("span");
    badges.className = "badges";
    (entry.author.badges || []).forEach((badge) => {
      const badgeEl = document.createElement("span");
      badgeEl.className = "badge";
      badgeEl.textContent = badge;
      badges.appendChild(badgeEl);
    });
    metaLine.appendChild(badges);

    if (!overlayMode) {
      const timestamp = document.createElement("span");
      timestamp.className = "timestamp";
      timestamp.textContent = new Date(entry.timestamp.unix * 1000).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
      metaLine.appendChild(timestamp);
    }

    const message = document.createElement("div");
    message.className = "message";
    message.textContent = entry.message.text;

    body.appendChild(metaLine);
    body.appendChild(message);

    wrapper.appendChild(avatarShell);
    wrapper.appendChild(body);

    target.appendChild(wrapper);
  });
}
