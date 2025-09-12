// static/js/app.js
(() => {
  // ------- Helpers -------
  const $  = (sel, root=document) => root.querySelector(sel);
  const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));
  const on = (el, ev, fn) => el && el.addEventListener(ev, fn);

  const STORAGE_KEY = "access_token";

  const getToken   = () => localStorage.getItem(STORAGE_KEY) || "";
  const setToken   = (t) => localStorage.setItem(STORAGE_KEY, t || "");
  const clearToken = () => localStorage.removeItem(STORAGE_KEY);

  // fetch mit JSON & JWT
  async function apiFetch(url, { method="GET", headers={}, body, json=true } = {}) {
    const token = getToken();
    const finalHeaders = Object.assign(
      { "Accept": "application/json" },
      headers
    );
    if (json) finalHeaders["Content-Type"] = "application/json";
    if (token) finalHeaders["Authorization"] = `Bearer ${token}`;

    const resp = await fetch(url, {
      method,
      headers: finalHeaders,
      body: json && body && typeof body !== "string" ? JSON.stringify(body) : body
    });

    // 401: nicht eingeloggt
    if (resp.status === 401) {
      // Hinweis zeigen, aber nicht sofort umleiten
      showHintIfExists(true);
    }

    let data = null;
    try { data = await resp.json(); } catch { /* best effort */ }

    return { ok: resp.ok, status: resp.status, data };
  }

  function setBadge(text, cls="badge") {
    const b = $("#authBadge");
    if (!b) return;
    b.className = `badge ${cls}`;
    b.textContent = text;
  }

  function updateNavForAuth() {
    const token = getToken();
    const has = !!token;

    // Badge + Buttons
    setBadge(has ? "Eingeloggt" : "Gast", has ? "badge success" : "badge");
    const navLogin    = $("#navLogin");
    const navRegister = $("#navRegister");
    const navLogout   = $("#navLogout");

    if (navLogin)    navLogin.classList.toggle("hidden",  has);
    if (navRegister) navRegister.classList.toggle("hidden", has);
    if (navLogout)   navLogout.classList.toggle("hidden", !has);

    // Hinweise aus-/einblenden
    showHintIfExists(!has);
  }

  function showHintIfExists(needLogin) {
    const chatHint = $("#chat_hint");
    const diHint   = $("#di_hint");
    if (chatHint) chatHint.style.display = needLogin ? "" : "none";
    if (diHint)   diHint.style.display   = needLogin ? "" : "none";
  }

  function toast(msg, type="info") {
    console[type === "error" ? "error" : "log"]("[app]", msg);
  }

  // ------- Logout Button -------
  on($("#navLogout"), "click", (e) => {
    e.preventDefault();
    clearToken();
    updateNavForAuth();
    toast("Abgemeldet");
    // optional: zur Login-Seite
    // window.location.href = "/login";
  });

  // ------- Chat (Diagnose-Assistent) -------
  (function initChat() {
    const logEl   = $("#chat_log");
    const inputEl = $("#chat_input");
    const sendBtn = $("#chat_send");

    if (!logEl || !inputEl || !sendBtn) return;

    function appendBubble(role, text) {
      const item = document.createElement("div");
      item.className = `chat-row ${role}`;
      item.innerHTML = `
        <div class="bubble">
          <div class="meta">${role === "user" ? "Du" : "Assistent"}</div>
          <div class="text"></div>
        </div>`;
      item.querySelector(".text").textContent = text;
      logEl.appendChild(item);
      logEl.scrollTop = logEl.scrollHeight;
    }

    async function sendChat() {
      const text = (inputEl.value || "").trim();
      if (!text) return;

      appendBubble("user", text);
      inputEl.value = "";
      sendBtn.disabled = true;

      const payload = { messages: [{ role: "user", content: text }] };
      const res = await apiFetch("/chat/", { method: "POST", body: payload });

      sendBtn.disabled = false;

      if (!res.ok) {
        const msg = res?.data?.error || res?.data?.msg || `Fehler (${res.status})`;
        appendBubble("assistant", `⚠️ ${msg}`);
        return;
      }
      const reply = res?.data?.message || "…";
      appendBubble("assistant", reply);
    }

    on(sendBtn, "click", (e) => { e.preventDefault(); sendChat(); });
    on(inputEl, "keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
    });
  })();

  // ------- Symptom Checker -------
  (function initSymptomChecker() {
    const form = $("#symptomForm");
    if (!form) return;

    const symptomsEl = $("#sc_symptoms");
    const onsetEl    = $("#sc_onset");
    const msgEl      = $("#sc_msg");
    const viewEl     = $("#sc_view");
    const sumEl      = $("#sc_summary");
    const listEl     = $("#sc_list");

    on(form, "submit", async (e) => {
      e.preventDefault();
      msgEl.textContent = "Wird geprüft …";

      const payload = {
        symptoms: (symptomsEl.value || "").trim(),
        onset: onsetEl.value || "unknown"
      };

      const res = await apiFetch("/health-check/", { method: "POST", body: payload });
      if (!res.ok) {
        msgEl.textContent = res?.data?.msg || res?.data?.error || `Fehler (${res.status})`;
        viewEl.classList.add("hidden");
        return;
      }

      msgEl.textContent = "";
      const data = res.data?.data || {};
      const sum  = data.summary || {};
      const diags = data.diagnoses || [];

      sumEl.innerHTML = `
        <div><strong>Risiko:</strong> ${sum.risk_level || "-"}</div>
        <div><strong>Dringlichkeit:</strong> ${sum.urgency || "-"}</div>
      `;

      listEl.innerHTML = diags.map(d =>
        `<div class="row">
           <div class="name">${d.condition}</div>
           <div class="meta">p=${(d.probability ?? 0).toFixed(2)}, triage=${d.triage}</div>
         </div>`
      ).join("") || `<div class="muted">Keine Vorschläge.</div>`;

      viewEl.classList.remove("hidden");
    });
  })();

  // ------- Drug Interactions -------
  (function initDrugInteractions() {
    const addBtn   = $("#di_add");
    const checkBtn = "#di_check";
    const listUl   = $("#di_list");
    const listWrap = $("#di_list_wrap");

    if (!addBtn || !listUl) return;

    const nameEl  = $("#di_name");
    const doseEl  = $("#di_dose");
    const routeEl = $("#di_route");

    const allergiesEl  = $("#di_allergies");
    const conditionsEl = $("#di_conditions");

    const viewEl   = $("#di_view");
    const sumEl    = $("#di_summary");
    const itemsEl  = $("#di_items");

    const drugs = [];

    function renderList() {
      listUl.innerHTML = drugs.map((d, i) =>
        `<li class="pill">
           <span>${d.name}${d.dose ? ` • ${d.dose}` : ""}${d.route ? ` • ${d.route}` : ""}</span>
           <button class="pill-x" data-i="${i}" title="entfernen">×</button>
         </li>`
      ).join("");
      listWrap.classList.toggle("hidden", drugs.length === 0);
      $$("#di_list .pill-x").forEach(btn => {
        on(btn, "click", () => {
          const idx = Number(btn.getAttribute("data-i"));
          drugs.splice(idx, 1);
          renderList();
        });
      });
    }

    on(addBtn, "click", (e) => {
      e.preventDefault();
      const name  = (nameEl.value || "").trim();
      const dose  = (doseEl.value || "").trim();
      const route = (routeEl.value || "").trim();
      if (!name) return;
      drugs.push({ name, dose, route });
      nameEl.value = ""; doseEl.value = ""; routeEl.value = "";
      renderList();
    });

    on($(checkBtn), "click", async (e) => {
      e.preventDefault();
      if (drugs.length === 0) { toast("Bitte mindestens eine Arznei eingeben."); return; }

      const payload = {
        drugs,
        allergies: (allergiesEl.value || "").split(",").map(s => s.trim()).filter(Boolean),
        conditions: (conditionsEl.value || "").split(",").map(s => s.trim()).filter(Boolean)
      };

      const res = await apiFetch("/drug-check/", { method: "POST", body: payload });
      if (!res.ok) {
        sumEl.textContent = res?.data?.msg || res?.data?.error || `Fehler (${res.status})`;
        viewEl.classList.remove("hidden");
        itemsEl.innerHTML = "";
        return;
      }

      const data = res.data?.data || {};
      const s    = data.summary || {};
      sumEl.innerHTML = `
        <div><strong>Sicher fortfahren:</strong> ${s.safe_to_proceed ? "Ja" : "Nein"}</div>
        <div><strong>Moderate:</strong> ${s.moderate_issue_count ?? 0} •
             <strong>Schwere:</strong> ${s.major_issue_count ?? 0}</div>`;

      function block(title, arr, render) {
        if (!arr || arr.length === 0) return "";
        return `
          <div class="block">
            <div class="block-title">${title}</div>
            <div class="block-body">
              ${arr.map(render).join("")}
            </div>
          </div>`;
      }

      itemsEl.innerHTML = [
        block("Überdosierungen", data.overdose_alerts, a =>
          `<div class="row">• ${a.drug}: ${a.dosage} (max ${a.max_daily_dose})</div>`),
        block("Interaktionen", data.interactions, i =>
          `<div class="row">• ${i.drug1} × ${i.drug2} — ${i.severity}: ${i.description || ""}</div>`),
        block("Kontraindikationen", data.contraindications, c =>
          `<div class="row">• ${c.drug} bei ${c.condition}${c.notes ? " — " + c.notes : ""}</div>`)
      ].join("");

      if (!itemsEl.innerHTML.trim()) {
        itemsEl.innerHTML = `<div class="muted">Keine Probleme gefunden.</div>`;
      }

      viewEl.classList.remove("hidden");
    });
  })();

  // ------- Initial UI sync -------
  updateNavForAuth();
})();
