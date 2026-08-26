/* distract-yt — YouTube-style distraction-free library.
   Home = sections built ONLY from your allowlist. No recommendations ever.
   Search exists only inside the Add-content modal. */

const API = {
  async get(path) {
    const r = await fetch(path);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || r.statusText);
    return data;
  },
  async send(method, path, body) {
    const r = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || r.statusText);
    return data;
  },
  add(type, url) {
    const plural = { video: "videos", channel: "channels", playlist: "playlists" };
    return this.send("POST", `/api/${plural[type] || type}`, { url });
  },
  del(type, id) { return this.send("DELETE", `/api/${type}/${id}`); },
  importContent(type, id) { return this.send("POST", `/api/import/${type}/${id}`); },
  clearVideos() { return this.send("DELETE", "/api/videos"); },
};

const state = {
  tab: "home",
  videos: [],
  channels: [],
  playlists: [],
  modalType: "video",
  activeChannel: null,
  activePlaylist: null,
  homeQuery: "",
};

const $ = (sel) => document.querySelector(sel);

const fmtDur = (sec) => {
  if (!sec && sec !== 0) return "";
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  const mm = h ? String(m).padStart(2, "0") : String(m);
  const ss = String(s).padStart(2, "0");
  return (h ? h + ":" : "") + mm + ":" + ss;
};
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function setBadge(cls, text) { const b = $("#conn-badge"); b.className = "badge " + cls; b.textContent = text; }
function whoami() { setBadge("ok", "connected"); }

/* ---------- card builders ---------- */
function videoCard(v, opts = {}) {
  const dur = v.duration_sec ? `<span class="duration">${fmtDur(v.duration_sec)}</span>` : "";
  const sub = opts.hideChannel ? (v.source || "") : (v.channel_name || v.source || "");
  let inner = `
    <div class="thumb">
      <img src="${esc(v.thumbnail_url || "")}" alt="" loading="lazy" />
      ${dur}
    </div>
    <div class="meta">
      <h3>${esc(v.title)}</h3>
      <div class="sub">${esc(sub)}</div>
    </div>`;
  if (opts.actions) {
    inner += `<div class="actions">
      <a class="btn primary small" href="/watch/${esc(v.id)}">Watch</a>
      <button class="btn small" data-del="videos" data-id="${esc(v.id)}">Remove</button>
    </div>`;
  }
  return `<div class="card" data-link="/watch/${esc(v.id)}" role="link" tabindex="0">${inner}</div>`;
}

function channelCard(c) {
  return `<div class="card" data-open-channel="${esc(c.id)}" role="link" tabindex="0">
    <div class="thumb" style="display:flex;align-items:center;justify-content:center;background:var(--panel)">
      <img src="${esc(c.thumbnail_url || "")}" alt="" style="width:84px;height:84px;border-radius:50%;object-fit:cover" />
    </div>
    <div class="meta" style="text-align:center">
      <h3>${esc(c.title)}</h3>
      <div class="sub">${c.handle ? "@" + esc(c.handle) : "channel"} · ${c.video_count} videos</div>
    </div>
  </div>`;
}

function playlistCard(p) {
  return `<div class="card playlist-card" data-open-playlist="${esc(p.id)}" role="link" tabindex="0">
    <div class="thumb"><img src="${esc(p.thumbnail_url || "")}" alt="" loading="lazy" /></div>
    <div class="meta">
      <h3>${esc(p.title)}</h3>
      <div class="sub">${p.item_count} videos in library</div>
    </div>
    <div class="actions">
      <button class="btn small" data-act="import-playlist" data-id="${esc(p.id)}">Import videos</button>
      <button class="btn small" data-del="playlists" data-id="${esc(p.id)}">Remove</button>
    </div>
  </div>`;
}

function sectionBlock(title, count, cards) {
  return `<div class="section">
    <div class="section-head"><h2>${title}</h2><span class="count">${count}</span></div>
    <div class="hrow">${cards}</div>
  </div>`;
}
/* ---------------- views ---------------- */
function renderHome() {
  const main = $("#app");
  if (!state.channels.length && !state.videos.length && !state.playlists.length) {
    main.innerHTML = `<p class="placeholder">Your library is empty.
      Click <b>+ Add</b> to add your first channel, video or collection.</p>`;
    return;
  }

  const q = (state.homeQuery || "").toString().trim().toLowerCase();
  let html = `
    <div class="home-search">
      <span class="hs-ico">🔍</span>
      <input id="home-search" type="search" placeholder="Search playlists in your library…" autocomplete="off" value="${esc(state.homeQuery || "")}" />
    </div>
    <div id="home-search-results" class="search-results" ${q ? "" : "hidden"}></div>`;

  // channels strip — click a chip to enter that channel
  if (state.channels.length) {
    const chips = state.channels.map((c) => `
      <button class="chan-chip" data-open-channel="${esc(c.id)}">
        <img src="${esc(c.thumbnail_url || "")}" alt="" />
        <span>${esc(c.title)}</span>
      </button>`).join("");
    html += `<div class="section">
      <div class="section-head"><h2>Your channels</h2><span class="count">${state.channels.length}</span></div>
      <div class="hrow">${chips}</div>
    </div>`;
  }

  // one section per playlist (auto-created when a playlist is added)
  state.playlists.forEach((p) => {
    const vids = (p.video_ids || [])
      .map((vid) => state.videos.find((v) => v.id === vid))
      .filter(Boolean);
    if (!vids.length) return;
    const cards = vids.slice(0, 12).map((v) => videoCard(v, { hideChannel: true })).join("");
    html += `<div class="section">
      <div class="section-head">
        <button class="section-title" data-open-playlist="${esc(p.id)}">📋 ${esc(p.title)}</button>
        <span class="count">${vids.length} videos</span>
      </div>
      <div class="hrow">${cards}</div>
    </div>`;
  });

  // one section per channel (auto-created when a channel is added)
  const byChannel = {};
  state.videos.forEach((v) => { if (v.channel_id) (byChannel[v.channel_id] = byChannel[v.channel_id] || []).push(v); });
  Object.entries(byChannel).forEach(([cid, vids]) => {
    const ch = state.channels.find((c) => c.id === cid);
    const title = ch ? `▶ ${ch.title}` : "▶ Channel";
    const cards = vids.slice(0, 12).map((v) => videoCard(v, { hideChannel: true })).join("");
    html += sectionBlock(title, vids.length + " videos", cards);
  });

  // latest videos grid
  if (state.videos.length) {
    html += `<div class="section">
      <div class="section-head"><h2>Latest videos</h2><span class="count">${state.videos.length}</span></div>
      <div class="grid">${state.videos.slice(0, 24).map((v) => videoCard(v)).join("")}</div>
    </div>`;
  }

  main.innerHTML = html;
  if (q) filterLibraryPlaylists();
}

function filterLibraryPlaylists() {
  const input = document.querySelector("#home-search");
  const box = document.querySelector("#home-search-results");
  if (!input || !box) return;
  const q = input.value.trim().toLowerCase();
  state.homeQuery = input.value;
  if (!q) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  const matches = state.playlists.filter((p) => (p.title || "").toLowerCase().includes(q));
  box.hidden = false;
  const heading = `<div class="page-title">Playlist search <span class="count">${matches.length}</span></div>`;
  if (!matches.length) {
    box.innerHTML = heading + `<p class="placeholder">No playlists in your library match “${esc(q)}”.</p>`;
    return;
  }
  box.innerHTML = heading + `<div class="grid">${matches.map(playlistCard).join("")}</div>`;
}

function renderVideos() {
  const main = $("#app");
  if (!state.videos.length) {
    main.innerHTML = `<p class="placeholder">No videos yet. Add one, import uploads, or import a collection.</p>`;
    return;
  }
  main.innerHTML = `
    <div class="page-title">Videos <span class="count">${state.videos.length}</span>
      <button id="btn-clear-videos" class="btn small danger">Clear all</button>
    </div>
    <div class="grid">${state.videos.map((v) => videoCard(v, { actions: true })).join("")}</div>`;
}

function renderChannels() {
  const main = $("#app");
  if (!state.channels.length) {
    main.innerHTML = `<p class="placeholder">No channels yet. Add one from the <b>+ Add</b> menu — a section for it
      is created automatically.</p>`;
    return;
  }
  main.innerHTML = `
    <div class="page-title">Channels <span class="count">${state.channels.length}</span></div>
    <div class="grid">${state.channels.map(channelCard).join("")}</div>`;
}

function renderPlaylists() {
  const main = $("#app");
  if (!state.playlists.length) {
    main.innerHTML = `<p class="placeholder">No collections yet. Add a YouTube playlist to keep a focused set.</p>`;
    return;
  }
  main.innerHTML = `
    <div class="page-title">Collections <span class="count">${state.playlists.length}</span></div>
    <div class="grid">${state.playlists.map(playlistCard).join("")}</div>`;
}

function renderPlaylistDetail() {
  const main = $("#app");
  const pl = state.activePlaylist;
  if (!pl) { state.tab = "home"; return render(); }
  const vids = (pl.video_ids || [])
    .map((vid) => state.videos.find((v) => v.id === vid))
    .filter(Boolean);
  const meta = `${vids.length} videos in library${pl.channel_title ? " · " + esc(pl.channel_title) : ""}`;
  main.innerHTML = `
    <a class="back-link" data-tab-nav="playlists">← Back to collections</a>
    <div class="chan-header">
      <img src="${esc(pl.thumbnail_url || "")}" alt="" />
      <div>
        <h1>${esc(pl.title)}</h1>
        <div class="sub">${meta}</div>
        <div class="actions">
          <button class="btn small" data-act="import-playlist" data-id="${esc(pl.id)}">Import videos</button>
          <button class="btn small danger" data-del="playlists" data-id="${esc(pl.id)}">Remove</button>
        </div>
      </div>
    </div>
    ${vids.length
      ? `<div class="page-title">Videos in this playlist <span class="count">${vids.length}</span></div>
         <div class="grid">${vids.map((v) => videoCard(v, { actions: true })).join("")}</div>`
      : `<p class="placeholder">No videos in this playlist yet. Click <b>Import videos</b> to pull them into your library.</p>`}`;
}

function renderChannelDetail() {
  const main = $("#app");
  const ch = state.activeChannel;
  if (!ch) { state.tab = "home"; return render(); }
  const vids = state.videos.filter((v) => v.channel_id === ch.id);
  const playlistsHtml = `
    <div class="page-title">Playlists from ${esc(ch.title)}</div>
    <div id="channel-playlists" class="playlists">
      <p class="placeholder">Loading playlists…</p>
    </div>`;
  const videosHtml = vids.length
    ? `<div class="page-title">All videos from ${esc(ch.title)} <span class="count">${vids.length}</span></div>
       <div class="grid">${vids.map((v) => videoCard(v, { actions: true })).join("")}</div>`
    : `<div class="page-title">All videos from ${esc(ch.title)}</div>
       <p class="placeholder">No videos for this channel yet. Click <b>Import uploads</b> to pull in its recent uploads.</p>`;
  main.innerHTML = `
    <a class="back-link" data-tab-nav="channels">← Back to channels</a>
    <div class="chan-header">
      <img src="${esc(ch.thumbnail_url || "")}" alt="" />
      <div>
        <h1>${esc(ch.title)}</h1>
        <div class="sub">${ch.handle ? "@" + esc(ch.handle) : "channel"} · ${vids.length} videos in library</div>
        <div class="actions">
          <button class="btn small" data-act="import-channel" data-id="${esc(ch.id)}">Import uploads</button>
          <button class="btn small danger" data-del="channels" data-id="${esc(ch.id)}">Remove channel</button>
        </div>
      </div>
    </div>
    ${playlistsHtml}
    ${videosHtml}`;
  loadChannelPlaylists(ch.id);
}

async function loadChannelPlaylists(chId) {
  const box = document.querySelector("#channel-playlists");
  if (!box) return;
  try {
    const rows = await API.get(`/api/channels/${encodeURIComponent(chId)}/playlists`);
    if (!rows || !rows.length) {
      box.innerHTML = `<p class="placeholder">No public playlists found for this channel.</p>`;
      return;
    }
    box.innerHTML = rows.map((p) => {
      const added = p.in_library;
      const btn = added
        ? `<span class="added-badge" title="This playlist is already in your library">✓ In library</span>`
        : `<button class="btn small primary" data-act="add-channel-playlist" data-id="${esc(p.id)}" data-title="${esc(p.title)}">Add</button>`;
      const count = typeof p.item_count === "number" ? `${p.item_count} videos` : "playlist";
      const thumb = p.thumbnail_url
        ? `<img src="${esc(p.thumbnail_url)}" alt="" loading="lazy" />`
        : `<div class="pl-thumb ph">▤</div>`;
      return `<div class="playlist-row">
        ${thumb}
        <div class="pl-meta">
          <h4>${esc(p.title)}</h4>
          <div class="sub">${count}</div>
        </div>
        <div class="pl-act">${btn}</div>
      </div>`;
    }).join("");
  } catch (err) {
    box.innerHTML = `<p class="placeholder" style="color:var(--muted)">Could not load playlists: ${esc(err.message)}</p>`;
  }
}

function render() {
  switch (state.tab) {
    case "videos": renderVideos(); break;
    case "channels": renderChannels(); break;
    case "playlists": renderPlaylists(); break;
    case "channel": renderChannelDetail(); break;
    case "playlist": renderPlaylistDetail(); break;
    default: renderHome();
  }
}

/* ---------------- data ---------------- */
async function loadAll() {
  try {
    const [videos, channels, playlists] = await Promise.all([
      API.get("/api/videos"),
      API.get("/api/channels"),
      API.get("/api/playlists"),
    ]);
    state.videos = videos;
    state.channels = channels;
    state.playlists = playlists;
    if (state.tab === "channel" && state.activeChannel) {
      const fresh = channels.find((c) => c.id === state.activeChannel.id);
      if (!fresh) { state.tab = "channels"; state.activeChannel = null; }
      else state.activeChannel = fresh;
    }
    if (state.tab === "playlist" && state.activePlaylist) {
      const fresh = playlists.find((p) => p.id === state.activePlaylist.id);
      if (!fresh) { state.tab = "home"; state.activePlaylist = null; }
      else state.activePlaylist = fresh;
    }
    if (state.tab !== "home") { state.homeQuery = ""; }
    whoami();
    render();
  } catch (e) {
    $("#app").innerHTML = `<p class="placeholder">Could not load library: ${esc(e.message)}</p>`;
    setBadge("bad", "API error");
  }
}
/* ---------------- events ---------------- */
function setTab(tab) {
  state.tab = tab;
  state.activeChannel = null;
  state.activePlaylist = null;
  document.body.classList.remove("menu-open");
  document.querySelectorAll(".side-item").forEach((x) =>
    x.classList.toggle("active", x.dataset.tab === tab));
  render();
  if (tab === "home") window.history.replaceState(null, "", "/");
}

function bindStaticEvents() {
  document.querySelectorAll(".side-item").forEach((b) =>
    b.addEventListener("click", () => setTab(b.dataset.tab)));

  const drawer = $("#sidebar");
  const setDrawer = (open) => document.body.classList.toggle("menu-open", open);
  $(".nav-toggle").addEventListener("click", (e) => {
    e.stopPropagation();
    setDrawer(!document.body.classList.contains("menu-open"));
  });
  // close when clicking content outside the drawer
  $("#app").addEventListener("click", (e) => {
    if (document.body.classList.contains("menu-open") && !e.target.closest("#sidebar")) setDrawer(false);
  });
  // close with Escape
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.body.classList.contains("menu-open")) setDrawer(false);
  });

  $("#btn-add").addEventListener("click", () => {
    $("#modal").classList.remove("hidden");
    $("#add-input").value = "";
    $("#search-results").innerHTML = "";
    $("#add-input").focus();
  });
  $("#modal-close").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });

  $("#btn-clear-all").addEventListener("click", confirmClearAll);

  $("#btn-logout").addEventListener("click", () => {
    if (!confirm("Sign out of distract-yt?")) return;
    API.send("POST", "/api/auth/logout")
      .then(() => { window.location.href = "/login"; })
      .catch(() => { window.location.href = "/login"; });
  });

  document.querySelectorAll(".add-tab").forEach((b) =>
    b.addEventListener("click", () => {
      document.querySelectorAll(".add-tab").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      state.modalType = b.dataset.type;
      const holder = $("#add-input");
      holder.placeholder = state.modalType === "url"
        ? "Paste a YouTube URL (video, channel or playlist)"
        : `Search YouTube for a ${state.modalType}…`;
      $("#search-results").innerHTML = "";
    })
  );

  $("#add-search").addEventListener("click", doSearch);
  $("#add-input").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });

  $("#search-results").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-add-id]");
    if (!b) return;
    b.disabled = true;
    b.textContent = "Adding…";
    try {
      await API.add(b.dataset.addType, b.dataset.addId);
      closeModal();
      await loadAll();
    } catch (err) {
      b.textContent = "Error";
      b.disabled = false;
      alert(err.message);
    }
  });

  $("#app").addEventListener("click", onMainClick);
  $("#app").addEventListener("input", (e) => {
    if (e.target && e.target.id === "home-search") filterLibraryPlaylists();
  });
}

async function confirmClearAll() {
  const total = state.videos.length;
  if (!total) return;
  if (!confirm(`Clear ALL ${total} videos from your library?\nChannels and collections stay — you can re-import any time.`)) return;
  try {
    const res = await API.clearVideos();
    await loadAll();
    alert(`Cleared ${res.deleted} videos.`);
  } catch (err) {
    alert(err.message);
  }
}
function onMainClick(e) {
  const chip = e.target.closest("[data-open-channel]");
  if (chip) {
    const id = chip.dataset.openChannel;
    const ch = state.channels.find((c) => c.id === id);
    if (ch) {
      state.tab = "channel";
      state.activeChannel = ch;
      document.querySelectorAll(".side-item").forEach((x) => x.classList.remove("active"));
      render();
    }
    return;
  }
  const link = e.target.closest("[data-link]");
  if (link) { window.location.href = link.dataset.link; return; }
  const back = e.target.closest("[data-tab-nav]");
  if (back) { setTab(back.dataset.tabNav); return; }
  const delBtn = e.target.closest("[data-del]");
  if (delBtn) {
    e.preventDefault();
    if (!confirm("Remove this from your library?")) return;
    API.del(delBtn.dataset.del, delBtn.dataset.id).then(loadAll).catch((err) => alert(err.message));
    return;
  }
  const imp = e.target.closest("[data-act='import-channel'], [data-act='import-playlist']");
  if (imp) {
    const kind = imp.dataset.act === "import-channel" ? "channel" : "playlist";
    imp.textContent = "Importing…";
    imp.disabled = true;
    API.importContent(kind, imp.dataset.id)
      .then(async (res) => {
        imp.textContent = "✓ " + res.added + " added";
        await loadAll();
      })
      .catch((err) => { imp.textContent = "Error"; imp.disabled = false; alert(err.message); });
    return;
  }
  const addPl = e.target.closest("[data-act='add-channel-playlist']");
  if (addPl) {
    const title = addPl.dataset.title || "this playlist";
    if (!confirm(`Add "${title}" to your library? You can import its videos afterwards.`)) return;
    addPl.disabled = true;
    addPl.textContent = "Adding…";
    API.add("playlist", addPl.dataset.id)
      .then(async () => {
        addPl.textContent = "✓ In library";
        await loadAll();
      })
      .catch((err) => { addPl.textContent = "Error"; addPl.disabled = false; alert(err.message); });
    return;
  }
  const openPl = e.target.closest("[data-open-playlist]");
  if (openPl) {
    const id = openPl.dataset.openPlaylist;
    const pl = state.playlists.find((p) => p.id === id);
    if (pl) {
      state.tab = "playlist";
      state.activePlaylist = pl;
      document.querySelectorAll(".side-item").forEach((x) => x.classList.remove("active"));
      render();
    }
    return;
  }
  if (e.target.id === "btn-clear-videos") { confirmClearAll(); }
}

/* ---------------- add-content search ---------------- */
function guessFromUrl(q) {
  if (/^(PL|UU|FL|OLAK5uy_)/.test(q) && !q.includes("/")) return { type: "playlists", id: q };
  if (/youtube\.com\/playlist/.test(q) || /[?&]list=/.test(q)) {
    const m = q.match(/[?&]list=([^&\s]+)/);
    return { type: "playlists", id: m && m[1] };
  }
  if (/youtu\.be\/([\w-]{11})/.test(q)) return { type: "videos", id: q.match(/youtu\.be\/([\w-]{11})/)[1] };
  if (/[?&]v=([\w-]{11})/.test(q)) return { type: "videos", id: q.match(/[?&]v=([\w-]{11})/)[1] };
  if (/youtube\.com\/(@|channel|c|user)/.test(q)) return { type: "channels", id: q };
  if (/^UC[\w-]{22}$/.test(q)) return { type: "channels", id: q };
  if (/^[\w-]{11}$/.test(q)) return { type: "videos", id: q };
  return null;
}

async function doSearch() {
  const q = $("#add-input").value.trim();
  if (!q) return;
  const box = $("#search-results");

  if (state.modalType === "url") {
    const guess = guessFromUrl(q);
    if (!guess) {
      box.innerHTML = `<div class="msg" style="color:var(--muted)">Couldn't understand that URL.</div>`;
      return;
    }
    try {
      await API.add(guess.type, guess.id);
      closeModal();
      await loadAll();
    } catch (err) {
      box.innerHTML = `<div class="msg" style="color:#ff8080">${esc(err.message)}</div>`;
    }
    return;
  }

  box.innerHTML = `<div class="msg">Searching…</div>`;
  try {
    const rows = await API.get(`/api/search?q=${encodeURIComponent(q)}&type=${state.modalType}`);
    if (!rows || !rows.length) {
      box.innerHTML = `<div class="msg">No ${state.modalType}s found for “${esc(q)}”.</div>`;
      return;
    }
    box.innerHTML = rows.map((r) => {
      const cls = state.modalType === "channel" ? "result channel" : "result";
      const sub = state.modalType === "channel" ? "channel" : (r.channel_name || "");
      return `<div class="${cls}">
        <img src="${esc(r.thumbnail_url || "")}" alt="" loading="lazy" />
        <div class="r-meta">
          <h4>${esc(r.title)}</h4>
          <div class="r-sub">${esc(sub)}</div>
        </div>
        <button class="btn small" data-add-id="${esc(r.id)}" data-add-type="${state.modalType}">
          ${state.modalType === "channel" ? "Allow" : "Add"}
        </button>
      </div>`;
    }).join("");
  } catch (err) {
    box.innerHTML = `<div class="msg" style="color:#ff8080">${esc(err.message)}</div>`;
  }
}

function closeModal() { $("#modal").classList.add("hidden"); }

/* ---------------- init ---------------- */
function init() {
  const params = new URLSearchParams(location.search);
  const ch = params.get("ch");
  bindStaticEvents();
  API.get("/api/auth/me")
    .then(() =>
      loadAll().then(() => {
        if (ch) {
          const found = state.channels.find((c) => c.id === ch);
          if (found) {
            state.tab = "channel";
            state.activeChannel = found;
            document.querySelectorAll(".side-item").forEach((x) => x.classList.remove("active"));
            render();
          }
        }
      })
    )
    .catch(() => { window.location.href = "/login"; });
}

init();