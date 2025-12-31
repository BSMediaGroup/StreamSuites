// Placeholder mock data for unified chat replay and live surfaces.
// This file is intentionally static and will be replaced by runtime-fed data in future stages.

const chatMessages = [
  {
    message_id: "ss-001",
    platform: "youtube",
    author: {
      display_name: "Daniel Clancy",
      avatar_url: "../../../docs/assets/placeholders/daniel.svg",
      color: "#e91e63",
      badges: ["admin", "mod", "pro"],
    },
    message: { text: "StreamSuites scaffolding locked in — theme-safe and OBS-friendly.", emotes: [":wave:"] },
    timestamp: { unix: 1700000001, iso: "2023-11-14T00:00:01Z" },
    metadata: { is_mod: true, is_member: true, is_superchat: false, raw: {} },
  },
  {
    message_id: "tw-002",
    platform: "twitch",
    author: {
      display_name: "PixelPilot",
      avatar_url: "../../../docs/assets/placeholders/streamsuites.svg",
      color: "#9146ff",
      badges: ["vip", "pro"],
    },
    message: { text: "Welcome to the unified chat window prototype!", emotes: ["Kappa"] },
    timestamp: { unix: 1700000005, iso: "2023-11-14T00:00:05Z" },
    metadata: { is_mod: false, is_member: false, is_superchat: false, raw: {} },
  },
  {
    message_id: "rm-003",
    platform: "rumble",
    author: {
      display_name: "SignalSeeker",
      avatar_url: "../../../docs/assets/placeholders/daniel-badge.svg",
      color: "#3ddc84",
      badges: ["founder", "admin"],
    },
    message: { text: "Rumble replay placeholder — still mock-fed, still local.", emotes: [] },
    timestamp: { unix: 1700000010, iso: "2023-11-14T00:00:10Z" },
    metadata: { is_mod: false, is_member: true, is_superchat: false, raw: {} },
  },
  {
    message_id: "kc-004",
    platform: "kick",
    author: {
      display_name: "NightRunner",
      avatar_url: "../../../docs/assets/placeholders/hotdog.svg",
      color: "#00e701",
      badges: ["subscriber", "mod"],
    },
    message: { text: "Kick chat placeholder activated for layout QA.", emotes: [":rocket:"] },
    timestamp: { unix: 1700000016, iso: "2023-11-14T00:00:16Z" },
    metadata: { is_mod: true, is_member: true, is_superchat: false, raw: {} },
  },
  {
    message_id: "dc-005",
    platform: "discord",
    author: {
      display_name: "LatencyLab",
      avatar_url: null,
      color: "#7bd7ff",
      badges: ["admin"],
    },
    message: { text: "Discord bridge placeholder. Avatar intentionally missing to verify fallback.", emotes: [] },
    timestamp: { unix: 1700000021, iso: "2023-11-14T00:00:21Z" },
    metadata: { is_mod: false, is_member: false, is_superchat: false, raw: {} },
  },
  {
    message_id: "yt-006",
    platform: "youtube",
    author: {
      display_name: "VoyagerAI",
      avatar_url: "",
      color: "#ff7b7b",
      badges: ["member", "pro"],
    },
    message: { text: "Testing multi-badge display and badge ordering.", emotes: [] },
    timestamp: { unix: 1700000027, iso: "2023-11-14T00:00:27Z" },
    metadata: { is_mod: false, is_member: true, is_superchat: false, raw: {} },
  },
  {
    message_id: "yt-007",
    platform: "unknown",
    author: {
      display_name: "MysteryUser",
      avatar_url: "../../../docs/assets/icons/ui/profile.svg",
      color: null,
      badges: [],
    },
    message: { text: "Neutral source to validate top-right badge layout.", emotes: [] },
    timestamp: { unix: 1700000033, iso: "2023-11-14T00:00:33Z" },
    metadata: { is_mod: false, is_member: false, is_superchat: false, raw: {} },
  },
];

function renderBadgeRow(entry) {
  const badgePriority = {
    platform: 0,
    admin: 1,
    mod: 2,
    pro: 3,
  };

  const badgeRow = document.createElement("div");
  badgeRow.className = "badge-row";

  const badgeItems = [];
  const platformLabel = entry.platform || "platform";
  badgeItems.push({ type: "platform", label: platformLabel, className: "badge platform-badge" });

  (entry.author.badges || []).forEach((raw) => {
    const normalized = (raw || "").toLowerCase();
    badgeItems.push({
      type: normalized,
      label: raw,
      className: normalized === "admin" || normalized === "mod" || normalized === "pro" ? "badge role-badge" : "badge",
    });
  });

  badgeItems
    .sort((a, b) => {
      const priA = badgePriority[a.type] ?? 10;
      const priB = badgePriority[b.type] ?? 10;
      if (priA === priB) return a.label.localeCompare(b.label);
      return priA - priB;
    })
    .forEach((badge) => {
      const badgeEl = document.createElement("span");
      badgeEl.className = badge.className;
      badgeEl.dataset.badgeType = badge.type;
      badgeEl.textContent = badge.label;
      badgeRow.appendChild(badgeEl);
    });

  return badgeRow;
}

function renderChatLog(target, entries) {
  const defaultAvatarSrc = "../../../docs/assets/icons/ui/profile.svg";

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

    const author = document.createElement("span");
    author.className = "author";
    author.style.color = entry.author.color || "#e5ecf5";
    author.textContent = entry.author.display_name;
    metaLine.appendChild(author);

    const badgesInline = document.createElement("span");
    badgesInline.className = "badges-inline";
    (entry.author.badges || []).forEach((badge) => {
      const badgeEl = document.createElement("span");
      badgeEl.className = "badge subtle";
      badgeEl.textContent = badge;
      badgesInline.appendChild(badgeEl);
    });
    metaLine.appendChild(badgesInline);

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

    wrapper.appendChild(renderBadgeRow(entry));
    wrapper.appendChild(avatarShell);
    wrapper.appendChild(body);

    target.appendChild(wrapper);
  });
}
