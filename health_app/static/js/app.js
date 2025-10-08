// static/js/app.js
(() => {
  // ------- Helpers -------
  const $  = (sel, root=document) => root.querySelector(sel);
  const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));
  const on = (el, ev, fn) => el && el.addEventListener(ev, fn);

  const I18n = window.I18n || null;
  const tr = (key, vars) => (I18n ? I18n.t(key, vars) : key);

  const STORAGE_KEY = "access_token";

  const getToken   = () => localStorage.getItem(STORAGE_KEY) || "";
  const setToken   = (t) => localStorage.setItem(STORAGE_KEY, t || "");
  const clearToken = () => {
    localStorage.removeItem(STORAGE_KEY);
    preferencesLoaded = false;
  };

  let preferencesLoaded = false;

  async function loadPreferenceLanguage() {
    if (!I18n || preferencesLoaded) {
      return;
    }
    const res = await apiFetch("/profile/preferences/");
    if (res.ok) {
      const lang = res.data?.data?.language;
      if (lang) {
        I18n.setLanguage(lang);
      }
    }
    preferencesLoaded = true;
  }

  // fetch mit JSON & JWT
  async function apiFetch(url, { method="GET", headers={}, body, json=true, responseType } = {}) {
    const spinner = document.getElementById("spinner");
    const token = getToken();
    const expect = responseType || (json === false ? "json" : "json");
    const defaultAccept = expect === "text" ? "text/plain" : expect === "blob" ? "application/octet-stream" : "application/json";
    const finalHeaders = Object.assign({ "Accept": defaultAccept }, headers);
    if (json && !finalHeaders["Content-Type"]) finalHeaders["Content-Type"] = "application/json";
    if (token) finalHeaders["Authorization"] = `Bearer ${token}`;

    if (spinner) spinner.classList.remove("hidden");
    let resp;
    try {
      resp = await fetch(url, {
        method,
        headers: finalHeaders,
        body: json && body && typeof body !== "string" ? JSON.stringify(body) : body
      });
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err || "");
      console.error("[app] Network request failed", detail);
      toast(
        tr("common.network_error.message"),
        "error",
        tr("common.network_error.title")
      );
      return { ok: false, status: 0, data: { error: "network-error", detail } };
    } finally {
      if (spinner) spinner.classList.add("hidden");
    }

    // 401: nicht eingeloggt
    if (resp.status === 401) {
      // Hinweis zeigen, aber nicht sofort umleiten
      showHintIfExists(true);
    }

    let data = null;
    try {
      if (expect === "text") {
        data = await resp.text();
      } else if (expect === "blob") {
        data = await resp.blob();
      } else if (expect === "none") {
        data = null;
      } else {
        data = await resp.json();
      }
    } catch { /* best effort */ }

    return { ok: resp.ok, status: resp.status, data, response: resp };
  }

  function setBadge(text, cls="badge") {
    const b = $("#authBadge");
    if (!b) return;
    b.className = `badge ${cls}`;
    b.textContent = text;
    if (I18n) I18n.apply();
  }

  function updateNavForAuth() {
    const token = getToken();
    const has = !!token;

    // Badge + Buttons
    setBadge(
      has ? tr("nav.badge_auth") : tr("nav.badge_guest"),
      has ? "badge success" : "badge"
    );
    const navLogin    = $("#navLogin");
    const navRegister = $("#navRegister");
    const navLogout   = $("#navLogout");

    if (navLogin)    navLogin.classList.toggle("hidden",  has);
    if (navRegister) navRegister.classList.toggle("hidden", has);
    if (navLogout)   navLogout.classList.toggle("hidden", !has);

    // Hinweise aus-/einblenden
    showHintIfExists(!has);
    if (has && !preferencesLoaded) {
      loadPreferenceLanguage();
    }

    if (window.__updateExports) {
      try {
        window.__updateExports(has);
      } catch (err) {
        console.warn("export state update failed", err);
      }
    }
  }

  function showHintIfExists(needLogin) {
    // Support both template IDs: chat_hint/chatHint and di_hint/drugHint
    const chatHint = document.getElementById("chat_hint") || document.getElementById("chatHint");
    const diHint   = document.getElementById("di_hint")   || document.getElementById("drugHint");
    if (chatHint) chatHint.style.display = needLogin ? "" : "none";
    if (diHint)   diHint.style.display   = needLogin ? "" : "none";
  }

  function toast(msg, type="info", title) {
    // Console fallback
    console[type === "error" ? "error" : "log"]("[app]", msg);
    const host = document.getElementById("toasts");
    if (!host) return;
    const node = document.createElement("div");
    node.className = `toast ${type}`;
    node.innerHTML = `
      <div class="body">
        ${title ? `<div class="title">${title}</div>` : ""}
        <div class="text"></div>
      </div>
      <button class="close" aria-label="${tr("common.close")}">×</button>
    `;
    if (type === "error") {
      node.setAttribute("role", "alert");
    }
    node.setAttribute("aria-live", type === "error" ? "assertive" : "polite");
    node.querySelector(".text").textContent = String(msg || "");
    host.appendChild(node);
    const closer = node.querySelector(".close");
    on(closer, "click", () => node.remove());
    setTimeout(() => node.remove(), 4000);
  }

  // ------- Theme Toggle -------
  (function initTheme(){
    const btn = $("#themeToggle");
    if (!btn) return;
    const root = document.documentElement;
    const get = () => (root.dataset.theme || "light");
    const set = (v) => { root.dataset.theme = v; try{ localStorage.setItem("theme", v);}catch(e){} };
    on(btn, "click", (e) => {
      e.preventDefault();
      set(get() === "dark" ? "light" : "dark");
      btn.textContent = get() === "dark" ? "🌙" : "🌓";
    });
    // initial icon
    btn.textContent = (get() === "dark" ? "🌙" : "🌓");
  })();

  // ------- Logout Button -------
  on($("#navLogout"), "click", (e) => {
    e.preventDefault();
    clearToken();
    updateNavForAuth();
    toast(tr("common.logout_success"));
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
          <div class="meta">${role === "user" ? tr("chat.user_label") : tr("chat.assistant_label")}</div>
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
        const msg = res?.data?.error || res?.data?.msg || tr("common.error_code", { status: res.status });
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
      msgEl.textContent = tr("symptom.loading");

      const payload = {
        symptoms: (symptomsEl.value || "").trim(),
        onset: onsetEl.value || "unknown"
      };

      const res = await apiFetch("/health-check/", { method: "POST", body: payload });
      if (!res.ok) {
        msgEl.textContent = res?.data?.msg || res?.data?.error || tr("common.error_code", { status: res.status });
        viewEl.classList.add("hidden");
        return;
      }

      msgEl.textContent = "";
      const data = res.data?.data || {};
      const sum  = data.summary || {};
      const diags = data.diagnoses || [];

      sumEl.innerHTML = `
        <div><strong>${tr("symptom.summary.risk")}:</strong> ${sum.risk_level || "-"}</div>
        <div><strong>${tr("symptom.summary.urgency")}:</strong> ${sum.urgency || "-"}</div>
      `;

      listEl.innerHTML = diags.map(d =>
        `<div class="row">
           <div class="name">${d.condition}</div>
           <div class="meta">p=${(d.probability ?? 0).toFixed(2)}, triage=${d.triage}</div>
         </div>`
      ).join("") || `<div class="muted">${tr("symptom.no_diagnosis")}</div>`;

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
           <button class="pill-x" data-i="${i}" title="${tr("drug.remove")}">×</button>
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
      if (drugs.length === 0) { toast(tr("drug.need_entry")); return; }

      const payload = {
        drugs,
        allergies: (allergiesEl.value || "").split(",").map(s => s.trim()).filter(Boolean),
        conditions: (conditionsEl.value || "").split(",").map(s => s.trim()).filter(Boolean)
      };

      const res = await apiFetch("/drug-check/", { method: "POST", body: payload });
      if (!res.ok) {
        sumEl.textContent = res?.data?.msg || res?.data?.error || tr("common.error_code", { status: res.status });
        viewEl.classList.remove("hidden");
        itemsEl.innerHTML = "";
        return;
      }

      const data = res.data?.data || {};
      const s    = data.summary || {};
      sumEl.innerHTML = `
        <div><strong>${tr("drug.summary.safe")}:</strong> ${s.safe_to_proceed ? tr("common.yes") : tr("common.no")}</div>
        <div><strong>${tr("drug.summary.moderate")}:</strong> ${s.moderate_issue_count ?? 0} •
             <strong>${tr("drug.summary.severe")}:</strong> ${s.major_issue_count ?? 0}</div>`;

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
        block(tr("drug.sections.overdose"), data.overdose_alerts, a =>
          `<div class="row">• ${a.drug}: ${a.dosage} (max ${a.max_daily_dose})</div>`),
        block(tr("drug.sections.interactions"), data.interactions, i =>
          `<div class="row">• ${i.drug1} × ${i.drug2} — ${i.severity}: ${i.description || ""}</div>`),
        block(tr("drug.sections.contraindications"), data.contraindications, c =>
          `<div class="row">• ${c.drug} bei ${c.condition}${c.notes ? " — " + c.notes : ""}</div>`)
      ].join("");

      if (!itemsEl.innerHTML.trim()) {
        itemsEl.innerHTML = `<div class="muted">${tr("drug.sections.none_found")}</div>`;
      }

      viewEl.classList.remove("hidden");
    });
  })();

  // ------- Recent Health History (Dashboard) -------
  (function initHealthHistory(){
    const list = document.getElementById("hh_list");
    const wrap = document.getElementById("hh_wrap");
    const hint = document.getElementById("hh_hint");
    if (!list || !wrap || !hint) return;
    const token = getToken();
    if (!token) {
      hint.style.display = "";
      hint.textContent = tr("history.prompt_login");
      return;
    }
    hint.style.display = "";
    hint.textContent = tr("history.empty");
    (async () => {
      const res = await apiFetch("/profile/health-history/?page=1&per_page=5");
      if (!res.ok) {
        if (res.status === 401) {
          hint.style.display = "";
          hint.textContent = tr("history.need_reauth");
        }
        return;
      }
      const entries = (res.data && res.data.data && res.data.data.entries) || [];
      list.innerHTML = entries.map(e => {
        const risks = e.risk_evaluation ? `${e.risk_evaluation.risk_level} / ${e.risk_evaluation.urgency}` : "-";
        const dd = (e.diagnoses || []).slice(0,3).map(d => `${d.condition} (p=${(d.probability??0).toFixed(2)})`).join("; ") || "–";
        return `
          <div class="result mt-2">
            <div><strong>${new Date(e.entered_at).toLocaleString()}</strong></div>
            <div class="muted">${e.symptoms}</div>
            <div class="mt-2"><strong>${tr("symptom.summary.risk")}:</strong> ${risks}</div>
            <div class="mt-1"><strong>${tr("sections.result")}:</strong> ${dd}</div>
          </div>`;
      }).join("");
      if (entries.length){
        wrap.classList.remove("hidden");
        hint.style.display = "none";
      } else {
        hint.style.display = "";
        hint.textContent = tr("history.empty");
      }
    })();
  })();

  // ------- Data Exports -------
  (function initExports(){
    const card = document.getElementById("exportsCard");
    if (!card) return;

    const statusEl = document.getElementById("exportStatus");
    const buttons = {
      chatJson: document.getElementById("exportChatJson"),
      chatText: document.getElementById("exportChatText"),
      auditCsv: document.getElementById("exportAuditCsv"),
    };
    const anonymizeToggle = document.getElementById("exportAnonymize");

    function setStatus(key, tone = "info") {
      if (!statusEl) return;
      statusEl.textContent = key ? tr(key) : "";
      statusEl.dataset.tone = tone;
    }

    const anonymizeParam = () => (anonymizeToggle && anonymizeToggle.checked ? "anonymize=true" : "");

    function withParam(url, param) {
      if (!param) return url;
      return url.includes("?") ? `${url}&${param}` : `${url}?${param}`;
    }

    function download(filename, blob) {
      const link = document.createElement("a");
      const url = URL.createObjectURL(blob);
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      requestAnimationFrame(() => {
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      });
    }

    function handleError(res) {
      if (res.status === 401) {
        setStatus("exports.status.require_login", "warning");
        toast(tr("exports.status.require_login"), "warning");
        return;
      }
      if (res.status === 403) {
        setStatus("exports.status.forbidden", "warning");
        toast(tr("exports.status.forbidden"), "warning");
        return;
      }
      setStatus("exports.status.error", "danger");
      toast(tr("exports.status.error"), "error");
    }

    async function exportChatJson() {
      setStatus("exports.status.loading", "info");
      const query = anonymizeParam();
      const url = withParam("/chat/export?format=json", query);
      const res = await apiFetch(url, { responseType: "json" });
      if (!res.ok) {
        handleError(res);
        return;
      }
      if (!res.data?.success) {
        setStatus("exports.status.error", "danger");
        toast(tr("exports.status.error"), "error");
        return;
      }
      const payload = res.data.data;
      const sessionId = payload?.session_id || "latest";
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      download(`chat-export-${sessionId}.json`, blob);
      setStatus("exports.status.success_chat_json", "success");
    }

    async function exportChatText() {
      setStatus("exports.status.loading", "info");
      const query = anonymizeParam();
      const url = withParam("/chat/export?format=txt", query);
      const res = await apiFetch(url, { responseType: "text" });
      if (!res.ok) {
        handleError(res);
        return;
      }
      if (typeof res.data !== "string" || !res.data.length) {
        setStatus("exports.status.error", "danger");
        toast(tr("exports.status.error"), "error");
        return;
      }
      const blob = new Blob([res.data], { type: "text/plain;charset=utf-8" });
      download("chat-export.txt", blob);
      setStatus("exports.status.success_chat_text", "success");
    }

    async function exportAuditCsv() {
      setStatus("exports.status.loading", "info");
      const param = anonymizeParam();
      const url = withParam("/support/audit-export?format=csv&pseudonymize=true", param);
      const res = await apiFetch(url, { responseType: "text" });
      if (!res.ok) {
        handleError(res);
        return;
      }
      if (typeof res.data !== "string") {
        setStatus("exports.status.error", "danger");
        toast(tr("exports.status.error"), "error");
        return;
      }
      const blob = new Blob([res.data], { type: "text/csv;charset=utf-8" });
      download("audit-export.csv", blob);
      setStatus("exports.status.success_audit", "success");
    }

    const handlers = {
      chatJson: exportChatJson,
      chatText: exportChatText,
      auditCsv: exportAuditCsv,
    };

    Object.entries(buttons).forEach(([key, btn]) => {
      if (!btn) return;
      on(btn, "click", (e) => {
        e.preventDefault();
        if (btn.disabled) return;
        handlers[key]();
      });
    });

    if (anonymizeToggle) {
      on(anonymizeToggle, "change", () => {
        if (getToken()) {
          setStatus("exports.status.idle", "info");
        }
      });
    }

    function setAvailability(isSignedIn) {
      const disabled = !isSignedIn;
      if (card) {
        card.classList.toggle("hidden", disabled);
      }
      Object.values(buttons).forEach((btn) => {
        if (!btn) return;
        btn.disabled = disabled;
        btn.setAttribute("aria-disabled", String(disabled));
      });
      if (anonymizeToggle) {
        anonymizeToggle.disabled = disabled;
      }
      if (disabled) {
        setStatus("", "info");
      } else {
        setStatus("exports.status.idle", "info");
      }
    }

    window.__updateExports = setAvailability;
    setAvailability(!!getToken());
  })();

  // ------- Initial UI sync -------
  updateNavForAuth();
})();
