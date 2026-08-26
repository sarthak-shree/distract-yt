/* distract-yt authentication page.
   Real auth: register / login against the Flask API, stored hashed server-side.
   Uses the animated folder-style form (folding fields) and blob submit button. */

(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var form = $("auth-form");
  var mode = "login"; // "login" | "register"
  var msgEl = $("auth-msg");
  var submitLabel = $("auth-submit-label");
  var confirmField = $("confirm-field");

  function setMsg(text, ok) {
    if (!text) { msgEl.hidden = true; msgEl.textContent = ""; return; }
    msgEl.textContent = text;
    msgEl.hidden = false;
    msgEl.className = "auth-msg" + (ok ? " ok" : " err");
  }

  function setButtonBusy(btn, busy) {
    btn.disabled = busy;
    submitLabel.textContent = busy
      ? (mode === "register" ? "Creating…" : "Signing in…")
      : (mode === "register" ? "Create account" : "Log in");
  }

  function setMode(next) {
    mode = next;
    document.querySelectorAll(".auth-tab").forEach(function (t) {
      t.classList.toggle("active", t.dataset.mode === mode);
    });
    var isRegister = mode === "register";
    confirmField.classList.toggle("hidden", !isRegister);
    // resume the confirm field entrance animation by re-triggering it
    confirmField.classList.remove("fold");
    void confirmField.offsetWidth;
    confirmField.classList.add("fold");
    setMsg("");
  }

  document.querySelectorAll(".auth-tab").forEach(function (t) {
    t.addEventListener("click", function () { setMode(t.dataset.mode); });
  });

  function clean(s) { return String(s == null ? "" : s).trim(); }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var username = clean($("auth-username").value);
    var password = $("auth-password").value || "";
    var confirm = $("auth-confirm").value || "";

    if (!username || !password) { setMsg("Enter a username and password."); return; }
    if (mode === "register") {
      if (password.length < 6) { setMsg("Password must be at least 6 characters."); return; }
      if (password !== confirm) { setMsg("Passwords do not match."); return; }
    }

    var button = $("auth-submit");
    setButtonBusy(button, true);
    setMsg("");

    var path = "/api/auth/" + mode;
    fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username, password: password }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        if (res.ok) {
          window.location.href = "/";
        } else {
          setMsg(res.data.error || "Something went wrong.");
          setButtonBusy(button, false);
        }
      })
      .catch(function () {
        setMsg("Network error — is the server running?");
        setButtonBusy(button, false);
      });
  });

  // Start on login unless ?mode=register was passed.
  var params = new URLSearchParams(location.search);
  if (params.get("mode") === "register") setMode("register");

  // subtle entrance stagger for the fields
  document.querySelectorAll(".auth-field").forEach(function (f, i) {
    f.style.animationDelay = (0.05 * i) + "s";
  });
})();