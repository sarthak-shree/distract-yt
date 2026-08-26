/* Custom distraction-free player.
   Drives the YouTube IFrame API but hides YouTube's chrome (controls:0, fs:0)
   and provides our own controls: play/pause, seek, time, volume, speed, fullscreen.
   The right-hand queue is built ONLY from videos already in your library. */

(function () {
  "use strict";

  var VIDEO_ID = (location.pathname.slice("/watch/".length).split("/")[0] || "").trim();

  // Gate the watch page behind authentication.
  fetch("/api/auth/me").then(function (r) {
    if (!r.ok) window.location.href = "/login";
  }).catch(function () { window.location.href = "/login"; });

  var player = null;
  var queue = [];
  var isPlaying = false;
  var raf = null;
  var seeking = false;
  var videoMeta = null;

  var $ = function (id) { return document.getElementById(id); };
  var shell = $("shell");
  var controlsEl = $("cp-controls");
  var playBtn = $("cp-play");
  var seekEl = $("cp-seek");
  var curEl = $("cp-cur");
  var durEl = $("cp-dur");
  var muteBtn = $("cp-mute");
  var volEl = $("cp-vol");
  var rateEl = $("cp-rate");
  var fsBtn = $("cp-fs");
  var endedEl = $("cp-ended");
  var hintEl = $("cp-hint");
  var replayBtn = $("cp-replay");
  var queueEl = $("queue");

  function fmt(s) {
    if (!isFinite(s) || s < 0) s = 0;
    s = Math.round(s);
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    var mm = h ? String(m).padStart(2, "0") : String(m);
    var ss = String(sec).padStart(2, "0");
    return (h ? h + ":" : "") + mm + ":" + ss;
  }

  function updatePlayBtn() { playBtn.textContent = isPlaying ? "⏸" : "▶"; }

  function showControls() { controlsEl.classList.add("show"); }
  function hideControls() { controlsEl.classList.remove("show"); }

  function startLoop() {
    cancelAnimationFrame(raf);
    function tick() {
      if (!player || !player.getCurrentTime) return;
      var cur = player.getCurrentTime() || 0;
      var dur = player.getDuration() || 0;
      if (!seeking) seekEl.value = dur ? (cur / dur) * 1000 : 0;
      curEl.textContent = fmt(cur);
      durEl.textContent = fmt(dur);
      if (isPlaying) raf = requestAnimationFrame(tick);
    }
    tick();
    raf = requestAnimationFrame(tick);
  }
  function stopLoop() { cancelAnimationFrame(raf); }

  function onPlayerReady() {
    volEl.value = player.getVolume ? player.getVolume() : 100;
    durEl.textContent = fmt(player.getDuration ? player.getDuration() : 0);
    startLoop();
    loadMetaAndQueue();
  }

  function onStateChange(e) {
    if (e.data === YT.PlayerState.PLAYING) {
      isPlaying = true; updatePlayBtn(); hideControls(); endedEl.classList.remove("show");
      startLoop();
    } else if (e.data === YT.PlayerState.PAUSED) {
      isPlaying = false; updatePlayBtn(); showControls(); stopLoop();
    } else if (e.data === YT.PlayerState.ENDED) {
      isPlaying = false; updatePlayBtn(); stopLoop(); endedEl.classList.add("show");
      seekEl.value = 1000;
    } else if (e.data === YT.PlayerState.BUFFERING) {
      if (isPlaying) startLoop();
    }
  }

  window.onYouTubeIframeAPIReady = function () {
    player = new YT.Player("player", {
      videoId: VIDEO_ID,
      width: "100%",
      height: "100%",
      playerVars: {
        controls: 0,          // our controls
        fs: 0,                // our fullscreen
        rel: 0,               // no related videos
        iv_load_policy: 3,    // no annotations
        modestbranding: 1,
        playsinline: 1,
        disablekb: 1,
        autoplay: 1,
        origin: location.origin
      },
      events: { onReady: onPlayerReady, onStateChange: onStateChange }
    });
  };

  /* ---------- queue from library ---------- */
  function loadMetaAndQueue() {
    fetch("/api/videos/" + encodeURIComponent(VIDEO_ID))
      .then(function (r) { return r.ok ? r.json() : Promise.reject(new Error("not in library")); })
      .then(function (meta) {
        videoMeta = meta;
        $("video-title").textContent = meta.title || VIDEO_ID;
        var chLink = $("video-channel");
        if (meta.channel_id) {
          chLink.href = "/?ch=" + encodeURIComponent(meta.channel_id);
          chLink.textContent = meta.channel_name || "channel";
        } else {
          chLink.style.display = "none";
        }
        document.title = meta.title + " · distract-yt";
        if (meta.channel_id) return loadQueue(meta.channel_id);
        else { $("queue-title").textContent = "No channel in library"; queueEl.innerHTML = ""; }
      })
      .catch(function () {
        $("video-title").textContent = "Video not in your library";
        $("video-channel").style.display = "none";
      });
  }

  function loadQueue(channelId) {
    fetch("/api/videos?channel_id=" + encodeURIComponent(channelId))
      .then(function (r) { return r.json(); })
      .then(function (vids) {
        queue = (vids || []).filter(function (v) { return v.id !== VIDEO_ID; }).slice(0, 12);
        renderQueue();
      })
      .catch(function () { queueEl.innerHTML = '<p class="queue-empty">Could not load queue.</p>'; });
  }

  function renderQueue() {
    if (!queue.length) {
      queueEl.innerHTML = '<p class="queue-empty">Only this video from this channel is in your library.</p>';
      return;
    }
    queueEl.innerHTML = queue.map(function (v, i) {
      var dur = v.duration_sec ? fmt(v.duration_sec) : "";
      return '<div class="queue-item" data-qi="' + i + '">' +
        '<img src="' + (v.thumbnail_url ? escAttr(v.thumbnail_url) : "") + '" alt="" loading="lazy" />' +
        '<div class="qi-meta"><h4>' + escHtml(v.title) + "</h4>" +
        '<div class="qi-sub">' + (dur ? dur + " · " : "") + (escHtml(v.channel_name) || "") + "</div></div></div>";
    }).join("");
  }

  queueEl.addEventListener("click", function (e) {
    var item = e.target.closest("[data-qi]");
    if (!item) return;
    var v = queue[+item.dataset.qi];
    if (!v || !player) return;
    endedEl.classList.remove("show");
    player.loadVideoById(v.id);
    player.playVideo();
    history.replaceState(null, "", "/watch/" + v.id);
    VIDEO_ID = v.id;
    $("video-title").textContent = v.title;
    document.title = v.title + " · distract-yt";
    renderQueue();
  });

  /* ---------- controls ---------- */
  playBtn.addEventListener("click", function () {
    if (!player) return;
    if (isPlaying) { player.pauseVideo(); } else { player.playVideo(); isPlaying = true; endedEl.classList.remove("show"); }
    updatePlayBtn();
  });

  replayBtn.addEventListener("click", function () {
    if (!player) return;
    endedEl.classList.remove("show");
    player.seekTo(0, true);
    player.playVideo();
  });

  seekEl.addEventListener("input", function () {
    seeking = true;
    var dur = player && player.getDuration ? player.getDuration() : 0;
    hintEl.textContent = fmt((seekEl.value / 1000) * dur);
    hintEl.classList.add("show");
  });
  seekEl.addEventListener("change", function () {
    var dur = player && player.getDuration ? player.getDuration() : 0;
    player.seekTo((seekEl.value / 1000) * dur, true);
    seeking = false;
    hintEl.classList.remove("show");
    if (!isPlaying) startLoop();
  });

  muteBtn.addEventListener("click", function () {
    if (!player) return;
    if (player.isMuted()) { player.unMute(); muteBtn.textContent = volEl.value == 0 ? "🔇" : "🔊"; }
    else { player.mute(); muteBtn.textContent = "🔇"; }
  });
  volEl.addEventListener("input", function () {
    if (!player) return;
    player.setVolume(+volEl.value);
    muteBtn.textContent = volEl.value == 0 ? "🔇" : "🔊";
  });

  rateEl.addEventListener("change", function () {
    if (player && player.setPlaybackRate) player.setPlaybackRate(parseFloat(rateEl.value));
  });

  fsBtn.addEventListener("click", function () {
    if (!document.fullscreenElement) {
      if (shell.requestFullscreen) shell.requestFullscreen();
    } else if (document.exitFullscreen) {
      document.exitFullscreen();
    }
  });
  document.addEventListener("fullscreenchange", function () {
    fsBtn.textContent = document.fullscreenElement ? "🗗" : "⛶";
  });

  shell.addEventListener("click", function (e) {
    if (e.target.closest(".cp-controls") || e.target.closest(".cp-ended")) return;
    if (!player) return;
    if (isPlaying) { player.pauseVideo(); } else { player.playVideo(); isPlaying = true; }
    updatePlayBtn();
  });

  /* ---------- helpers ---------- */
  function escHtml(s) { return String(s ?? "").replace(/[&<>"']/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]); }); }
  function escAttr(s) { return String(s ?? "").replace(/"/g, "&quot;"); }
})();