// static/js/app.js
(() => {
  // ------- Helpers -------
  const $  = (sel, root=document) => root.querySelector(sel);
  const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));
  const on = (el, ev, fn) => el && el.addEventListener(ev, fn);

  const I18n = window.I18n || null;
  const tr = (key, vars) => (I18n ? I18n.t(key, vars) : key);

  function setNodeTextByKey(node, key) {
    if (!node) return;
    if (key) {
      node.dataset.i18nKey = key;
      node.textContent = tr(key);
    } else {
      delete node.dataset.i18nKey;
    }
  }

  function applyDatasetTranslations(root=document) {
    if (!root) return;
    const nodes = root.querySelectorAll("[data-i18n-key]");
    nodes.forEach((node) => {
      const key = node.dataset.i18nKey;
      if (key) node.textContent = tr(key);
    });
  }

  const STORAGE_KEY = "access_token";

  let preferencesLoaded = false;
  let profileSnapshot = null;
  let profileLoading = null;
  let profileDenied = false;
  let authVerifyPromise = null;
  let refreshPromise = null;

  const profileMenu = $("#profileMenu");
  const profileToggle = $("#profileToggle");
  const profileDropdown = $("#profileDropdown");
  const profileNameEl = $("#profileName");
  const profileEmailEl = $("#profileEmail");
  const profileAvatarEl = $("#profileAvatar");
  const profileLink = $("#profileLink");
  const profileModal = $("#profileModal");
  const profileModalClose = $("#profileModalClose");
  const profileModalCloseFooter = $("#profileModalCloseFooter");
  const profileModalEmail = $("#profileModalEmail");
  const profileModalCreated = $("#profileModalCreated");
  const profileModalStatus = $("#profileModalStatus");
  const profileModalStats = $("#profileModalStats");
  const profileModalAgeValue = $("#profileModalAgeValue");
  const profileModalSexValue = $("#profileModalSexValue");
  const profileModalForm = $("#profileModalForm");
  const profileAgeInput = $("#profileAge");
  const profileSexSelect = $("#profileSex");
  const profileSaveBtn = $("#profileSaveBtn");
  const profileSaveStatus = $("#profileSaveStatus");
  const profileAllergiesList = $("#profileAllergiesList");
  const profileAllergiesForm = $("#profileAllergiesForm");
  const profileAllergyInput = $("#profileAllergyInput");
  const profileAllergiesStatus = $("#profileAllergiesStatus");
  const profileConditionsList = $("#profileConditionsList");
  const profileConditionsForm = $("#profileConditionsForm");
  const profileConditionInput = $("#profileConditionInput");
  const profileConditionsStatus = $("#profileConditionsStatus");
  const profileMedicationsList = $("#profileMedicationsList");
  const profileMedicationsForm = $("#profileMedicationsForm");
  const profileMedicationName = $("#profileMedicationName");
  const profileMedicationDose = $("#profileMedicationDose");
  const profileMedicationStart = $("#profileMedicationStart");
  const profileMedicationsStatus = $("#profileMedicationsStatus");
  const profileContactsList = $("#profileContactsList");
  const profileContactsForm = $("#profileContactsForm");
  const profileContactName = $("#profileContactName");
  const profileContactRelationship = $("#profileContactRelationship");
  const profileContactPhone = $("#profileContactPhone");
  const profileContactEmail = $("#profileContactEmail");
  const profileContactPrimary = $("#profileContactPrimary");
  const profileContactsStatus = $("#profileContactsStatus");
  const profileFamilyList = $("#profileFamilyList");
  const profileFamilyForm = $("#profileFamilyForm");
  const profileFamilyName = $("#profileFamilyName");
  const profileFamilyRelationship = $("#profileFamilyRelationship");
  const profileFamilyBirthdate = $("#profileFamilyBirthdate");
  const profileFamilyStatus = $("#profileFamilyStatus");
  const profileHistoryList = $("#profileHistoryList");
  const profileModalBackdrop = profileModal ? profileModal.querySelector(".modal-backdrop") : null;
  const profileLanguageButtons = $$(".profile-lang");

  const getToken = () => localStorage.getItem(STORAGE_KEY) || "";
  const setToken = (t) => {
    localStorage.setItem(STORAGE_KEY, t || "");
    profileSnapshot = null;
    profileLoading = null;
    profileDenied = false;
    window.dispatchEvent(new CustomEvent("auth:state-changed"));
  };
  const clearToken = () => {
    localStorage.removeItem(STORAGE_KEY);
    preferencesLoaded = false;
    profileSnapshot = null;
    profileLoading = null;
    profileDenied = false;
    resetProfileMenuUI();
    window.dispatchEvent(new CustomEvent("auth:state-changed"));
  };

  async function loadPreferenceLanguage() {
    if (!I18n || preferencesLoaded) {
      return;
    }
    const token = await ensureAccessToken();
    if (!token) {
      return;
    }
    const res = await apiFetch("/profile/preferences/");
    if (res.ok) {
      const lang = res.data?.data?.language;
      if (lang) {
        I18n.setLanguage(lang);
      }
      preferencesLoaded = true;
      return;
    }
    if (res.status === 401) {
      profileDenied = true;
      console.warn("[auth] preferences endpoint returned 401");
      const ok = await verifyCurrentAuth();
      if (!ok) clearToken();
    }
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
        credentials: "same-origin",
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

  function setProfileMenuOpen(open) {
    if (!profileMenu) return;
    const value = open ? "true" : "false";
    profileMenu.dataset.open = value;
    profileMenu.classList.toggle("open", open);
    if (profileToggle) profileToggle.setAttribute("aria-expanded", value);
  }

  function defaultProfileLabel() {
    return tr("nav.profile");
  }

  function nameFromEmail(email) {
    if (!email || typeof email !== "string") return "";
    const local = email.split("@")[0] || "";
    if (!local) return "";
    const parts = local.split(/[._-]+/).filter(Boolean);
    if (!parts.length) {
      return local.charAt(0).toUpperCase() + local.slice(1);
    }
    return parts
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function avatarInitial(source) {
    if (!source) return "👤";
    const text = String(source).trim();
    if (!text) return "👤";
    return text.charAt(0).toUpperCase();
  }

  function applyProfileMenuUI(profile) {
    const email = profile?.user?.email || "";
    const display = nameFromEmail(email) || email || defaultProfileLabel();
    if (profileNameEl) profileNameEl.textContent = display;
    if (profileEmailEl) profileEmailEl.textContent = email;
    if (profileAvatarEl) profileAvatarEl.textContent = avatarInitial(display || email);
  }

  function resetProfileMenuUI() {
    setProfileMenuOpen(false);
    if (profileNameEl) profileNameEl.textContent = defaultProfileLabel();
    if (profileEmailEl) profileEmailEl.textContent = "";
    if (profileAvatarEl) profileAvatarEl.textContent = "👤";
  }

  async function ensureProfileSnapshot() {
    if (profileDenied) return null;
    let token = getToken();
    if (!token) {
      token = await ensureAccessToken();
      if (!token) return null;
    }
    if (profileSnapshot) {
      refreshProfileLocale();
      return profileSnapshot;
    }
    if (profileLoading) {
      return profileLoading;
    }
    profileLoading = (async () => {
      const res = await apiFetch("/profile/");
      profileLoading = null;
      if (!res.ok) {
        if (res.status === 401) {
          profileDenied = true;
          console.warn("[auth] profile endpoint returned 401");
          verifyCurrentAuth().then((ok) => {
            if (!ok) clearToken();
          });
        }
        return null;
      }
      if (!res.data || !res.data.data) {
        return null;
      }
      profileSnapshot = res.data.data;
      refreshProfileLocale();
      return profileSnapshot;
    })();
    return profileLoading;
  }

  function isProfileModalOpen() {
    return profileModal && !profileModal.classList.contains("hidden");
  }

  function formatDateTime(value) {
    if (!value) return tr("profile.modal.unknown");
    const date = typeof value === "string" ? new Date(value) : value;
    if (Number.isNaN(date.getTime())) {
      return tr("profile.modal.unknown");
    }
    return date.toLocaleString();
  }

  function closeProfileModal() {
    if (!profileModal) return;
    profileModal.classList.add("hidden");
    document.body.classList.remove("modal-open");
    const focusTarget = profileToggle || profileMenu || document.body;
    if (focusTarget && typeof focusTarget.focus === "function") {
      focusTarget.focus();
    }
  }

  const ALLOWED_SEX_VALUES = new Set(["female", "male", "other", "unknown"]);

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function parseId(value) {
    if (value === null || value === undefined || value === "") return null;
    const num = Number.parseInt(String(value), 10);
    return Number.isNaN(num) ? null : num;
  }

  function translateSexValue(value) {
    if (!value) return tr("profile.modal.sex_unknown");
    const normalized = String(value).toLowerCase();
    const keyMap = {
      female: "profile.modal.sex_female",
      male: "profile.modal.sex_male",
      other: "profile.modal.sex_other",
      unknown: "profile.modal.sex_unknown_option",
    };
    const key = keyMap[normalized];
    if (key) {
      const translated = tr(key);
      return translated && translated !== key ? translated : normalized;
    }
    return normalized.charAt(0).toUpperCase() + normalized.slice(1);
  }

  function buildStat(label, value) {
    return `
      <div class="stat">
        <span class="stat-label">${label}</span>
        <span>${value}</span>
      </div>
    `;
  }

  function populateProfileModal(profile) {
    if (!profileModal) return;
    const user = profile?.user || {};
    const summary = profile?.summary || {};
    const profileCore = profile?.profile || {};

    const email = user.email || "";
    if (profileModalEmail) profileModalEmail.textContent = email || tr("profile.modal.unknown");

    const created = user.created_at ? formatDateTime(user.created_at) : tr("profile.modal.unknown");
    if (profileModalCreated) profileModalCreated.textContent = created;

    const statusParts = [];
    if (user.is_active === false) {
      statusParts.push(tr("profile.modal.inactive"));
    } else {
      statusParts.push(tr("profile.modal.active"));
    }
    if (user.email_verified) {
      statusParts.push(tr("profile.modal.email_verified"));
    } else {
      statusParts.push(tr("profile.modal.email_unverified"));
    }
    if (profileModalStatus) profileModalStatus.textContent = statusParts.join(" · ");

    const ageValue = profileCore?.age;
    if (profileModalAgeValue) {
      profileModalAgeValue.textContent =
        ageValue !== undefined && ageValue !== null ? String(ageValue) : tr("profile.modal.unknown");
    }

    const sexValue = profileCore?.sex;
    if (profileModalSexValue) {
      profileModalSexValue.textContent = translateSexValue(sexValue);
    }

    const statMap = [
      ["total_allergies", "profile.modal.stat_allergies"],
      ["total_conditions", "profile.modal.stat_conditions"],
      ["active_medications", "profile.modal.stat_medications"],
      ["total_health_entries", "profile.modal.stat_checks"],
      ["emergency_contacts", "profile.modal.stat_contacts"],
      ["family_members", "profile.modal.stat_family"],
    ];

    const statsHtml = statMap
      .map(([key, labelKey]) => {
        const val = summary[key];
        if (val === undefined || val === null) return "";
        return buildStat(tr(labelKey), val);
      })
      .filter(Boolean)
      .join("");

    if (profileModalStats) {
      profileModalStats.innerHTML = statsHtml || `<div class="muted">${tr("profile.modal.no_stats")}</div>`;
    }

    if (profileAgeInput) {
      profileAgeInput.value = ageValue !== undefined && ageValue !== null ? String(ageValue) : "";
    }
    if (profileSexSelect) {
      const normalized = sexValue ? String(sexValue).toLowerCase() : "";
      if (normalized) {
        const hasOption = Array.from(profileSexSelect.options || []).some((opt) => opt.value === normalized);
        if (!hasOption) {
          const option = document.createElement("option");
          option.value = normalized;
          option.textContent = translateSexValue(normalized);
          profileSexSelect.appendChild(option);
        }
      }
      profileSexSelect.value = normalized;
    }

    renderAllergiesList(profile);
    renderConditionsList(profile);
    renderMedicationsList(profile);
    renderContactsList(profile);
    renderFamilyList(profile);
    renderHistoryList(profile);
  }

  function setProfileSaveMessage(message, tone) {
    if (!profileSaveStatus) return;
    profileSaveStatus.textContent = message || "";
    if (message) {
      profileSaveStatus.dataset.state = tone || "info";
    } else {
      delete profileSaveStatus.dataset.state;
    }
  }

  function setSectionStatus(el, message, tone) {
    if (!el) return;
    el.textContent = message || "";
    if (message) {
      el.dataset.state = tone || "info";
    } else {
      delete el.dataset.state;
    }
  }

  function handleProfileUnauthorized() {
    profileDenied = true;
    verifyCurrentAuth().then((ok) => {
      if (!ok) clearToken();
    });
  }

  function formatDateOnly(value) {
    if (!value) return "";
    const date = typeof value === "string" ? new Date(value) : value;
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
      return "";
    }
    return date.toLocaleDateString();
  }

  function resetCollectionForms() {
    if (profileAllergiesForm) profileAllergiesForm.reset();
    if (profileConditionsForm) profileConditionsForm.reset();
    if (profileMedicationsForm) profileMedicationsForm.reset();
    if (profileContactsForm) profileContactsForm.reset();
    if (profileFamilyForm) profileFamilyForm.reset();
    if (profileContactPrimary) profileContactPrimary.checked = false;
  }

  function renderAllergiesList(profile) {
    if (!profileAllergiesList) return;
    const items = Array.isArray(profile?.allergies) ? profile.allergies : [];
    if (!items.length) {
      profileAllergiesList.innerHTML = `<li class="muted" data-empty>${escapeHtml(tr("profile.collections.allergies.empty"))}</li>`;
      return;
    }
    profileAllergiesList.innerHTML = items
      .map((item) => {
        const name = item?.name ? escapeHtml(item.name) : escapeHtml(tr("profile.collections.untitled"));
        const id = item?.id ?? "";
        return `
          <li data-id="${id}">
            <div class="profile-item-info">
              <strong>${name}</strong>
            </div>
            <div class="profile-item-actions">
              <button type="button" class="btn btn-ghost" data-action="remove-allergy" data-id="${id}">
                ${escapeHtml(tr("profile.collections.remove_button"))}
              </button>
            </div>
          </li>
        `;
      })
      .join("");
  }

  function renderConditionsList(profile) {
    if (!profileConditionsList) return;
    const items = Array.isArray(profile?.conditions) ? profile.conditions : [];
    if (!items.length) {
      profileConditionsList.innerHTML = `<li class="muted" data-empty>${escapeHtml(tr("profile.collections.conditions.empty"))}</li>`;
      return;
    }
    profileConditionsList.innerHTML = items
      .map((item) => {
        const name = item?.name ? escapeHtml(item.name) : escapeHtml(tr("profile.collections.untitled"));
        const id = item?.id ?? "";
        return `
          <li data-id="${id}">
            <div class="profile-item-info">
              <strong>${name}</strong>
            </div>
            <div class="profile-item-actions">
              <button type="button" class="btn btn-ghost" data-action="remove-condition" data-id="${id}">
                ${escapeHtml(tr("profile.collections.remove_button"))}
              </button>
            </div>
          </li>
        `;
      })
      .join("");
  }

  function renderMedicationsList(profile) {
    if (!profileMedicationsList) return;
    const items = Array.isArray(profile?.medications) ? profile.medications : [];
    if (!items.length) {
      profileMedicationsList.innerHTML = `<li class="muted" data-empty>${escapeHtml(tr("profile.collections.medications.empty"))}</li>`;
      return;
    }
    profileMedicationsList.innerHTML = items
      .map((item) => {
        const id = item?.id ?? "";
        const name = item?.drug_name
          ? escapeHtml(item.drug_name)
          : escapeHtml(tr("profile.collections.medications.unknown_drug"));
        const detailParts = [];
        if (item?.dosage) detailParts.push(escapeHtml(item.dosage));
        const started = formatDateOnly(item?.started_at);
        if (started) {
          detailParts.push(escapeHtml(tr("profile.collections.medications.started", { date: started })));
        }
        const ended = formatDateOnly(item?.ended_at);
        if (ended) {
          detailParts.push(escapeHtml(tr("profile.collections.medications.ended", { date: ended })));
        }
        const detailHtml = detailParts.length ? `<span class="muted">${detailParts.join(" · ")}</span>` : "";
        const badgeKey = item?.is_active ? "profile.collections.medications.active_badge" : "profile.collections.medications.inactive_badge";
        const badgeClass = item?.is_active ? "badge success" : "badge";
        const badge = `<span class="${badgeClass}">${escapeHtml(tr(badgeKey))}</span>`;
        return `
          <li data-id="${id}">
            <div class="profile-item-info">
              <strong>${name}</strong>
              ${detailHtml}
            </div>
            <div class="profile-item-actions">
              ${badge}
              <button type="button" class="btn btn-ghost" data-action="remove-medication" data-id="${id}">
                ${escapeHtml(tr("profile.collections.remove_button"))}
              </button>
            </div>
          </li>
        `;
      })
      .join("");
  }

  function renderContactsList(profile) {
    if (!profileContactsList) return;
    const items = Array.isArray(profile?.emergency_contacts) ? profile.emergency_contacts : [];
    if (!items.length) {
      profileContactsList.innerHTML = `<li class="muted" data-empty>${escapeHtml(tr("profile.collections.contacts.empty"))}</li>`;
      return;
    }
    profileContactsList.innerHTML = items
      .map((contact) => {
        const id = contact?.id ?? "";
        const name = contact?.name ? escapeHtml(contact.name) : escapeHtml(tr("profile.collections.untitled"));
        const relation = contact?.relationship ? `<span class="muted">${escapeHtml(contact.relationship)}</span>` : "";
        const contactParts = [];
        if (contact?.phone) contactParts.push(escapeHtml(contact.phone));
        if (contact?.email) contactParts.push(escapeHtml(contact.email));
        const contactInfo = contactParts.length ? `<span class="muted">${contactParts.join(" · ")}</span>` : "";
        const primaryBadge = contact?.is_primary
          ? `<span class="badge success">${escapeHtml(tr("profile.collections.contacts.primary_badge"))}</span>`
          : "";
        return `
          <li data-id="${id}">
            <div class="profile-item-info">
              <strong>${name}</strong>
              ${relation}
              ${contactInfo}
            </div>
            <div class="profile-item-actions">
              ${primaryBadge}
              <button type="button" class="btn btn-ghost" data-action="remove-contact" data-id="${id}">
                ${escapeHtml(tr("profile.collections.remove_button"))}
              </button>
            </div>
          </li>
        `;
      })
      .join("");
  }

  function renderFamilyList(profile) {
    if (!profileFamilyList) return;
    const items = Array.isArray(profile?.family_members) ? profile.family_members : [];
    if (!items.length) {
      profileFamilyList.innerHTML = `<li class="muted" data-empty>${escapeHtml(tr("profile.collections.family.empty"))}</li>`;
      return;
    }
    profileFamilyList.innerHTML = items
      .map((member) => {
        const id = member?.id ?? "";
        const name = member?.name ? escapeHtml(member.name) : escapeHtml(tr("profile.collections.untitled"));
        const relation = member?.relationship ? `<span class="muted">${escapeHtml(member.relationship)}</span>` : "";
        const birth = formatDateOnly(member?.birthdate);
        const birthHtml = birth ? `<span class="muted">${escapeHtml(birth)}</span>` : "";
        return `
          <li data-id="${id}">
            <div class="profile-item-info">
              <strong>${name}</strong>
              ${relation}
              ${birthHtml}
            </div>
            <div class="profile-item-actions">
              <button type="button" class="btn btn-ghost" data-action="remove-family" data-id="${id}">
                ${escapeHtml(tr("profile.collections.remove_button"))}
              </button>
            </div>
          </li>
        `;
      })
      .join("");
  }

  function renderHistoryList(profile) {
    if (!profileHistoryList) return;
    const items = Array.isArray(profile?.health_history) ? profile.health_history : [];
    if (!items.length) {
      profileHistoryList.innerHTML = `<li class="muted" data-empty>${escapeHtml(tr("profile.collections.history.empty"))}</li>`;
      return;
    }
    profileHistoryList.innerHTML = items
      .map((entry) => {
        const dateText = escapeHtml(formatDateTime(entry?.entered_at) || "");
        const symptoms = entry?.symptoms ? escapeHtml(entry.symptoms) : escapeHtml(tr("profile.collections.untitled"));
        const riskLevel = entry?.risk_evaluation?.risk_level;
        const riskText = riskLevel ? escapeHtml(tr("profile.collections.history.risk", { level: riskLevel })) : "";
        const riskBadge = riskText ? `<span class="badge">${riskText}</span>` : "";
        return `
          <li data-id="${entry?.id ?? ""}">
            <div class="profile-item-info">
              <strong>${dateText}</strong>
              <span class="muted">${symptoms}</span>
            </div>
            <div class="profile-item-actions">
              ${riskBadge}
            </div>
          </li>
        `;
      })
      .join("");
  }

  async function reloadProfileSnapshot() {
    profileSnapshot = null;
    profileLoading = null;
    const refreshed = await ensureProfileSnapshot();
    if (refreshed) {
      resetCollectionForms();
    }
    return refreshed;
  }

  async function openProfileModal() {
    if (!profileModal) return;
    profileModal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    const focusEl = profileModalClose || profileModal.querySelector(".modal-content");
    if (focusEl && typeof focusEl.focus === "function") {
      focusEl.focus();
    }
    if (profileSaveBtn) profileSaveBtn.disabled = false;
    setProfileSaveMessage("");
    const profile = await ensureProfileSnapshot();
    if (!profile) {
      if (profileModalStats) profileModalStats.innerHTML = `<div class="muted">${tr("profile.modal.fetch_error")}</div>`;
      if (profileModalEmail) profileModalEmail.textContent = tr("profile.modal.unknown");
      if (profileModalCreated) profileModalCreated.textContent = tr("profile.modal.unknown");
      if (profileModalStatus) profileModalStatus.textContent = tr("profile.modal.unknown");
      return;
    }
    populateProfileModal(profile);
    resetCollectionForms();
  }

  function currentLanguage() {
    if (I18n && typeof I18n.getLanguage === "function") {
      return I18n.getLanguage();
    }
    return "en";
  }

  function applyLanguageButtons() {
    if (!profileLanguageButtons.length) return;
    const activeLang = currentLanguage();
    profileLanguageButtons.forEach((btn) => {
      if (!btn) return;
      const lang = (btn.dataset.lang || "").toLowerCase();
      if (!lang) return;
      const code = tr(`languages.short.${lang}`);
      const label = tr(`languages.full.${lang}`);
      btn.textContent = code !== `languages.short.${lang}` ? code : lang.toUpperCase();
      btn.setAttribute("aria-label", label !== `languages.full.${lang}` ? label : lang);
      btn.setAttribute("title", label !== `languages.full.${lang}` ? label : lang.toUpperCase());
      btn.classList.toggle("active", lang === activeLang);
    });
  }

  async function handleLanguageSelect(lang) {
    if (!lang || !I18n || typeof I18n.setLanguage !== "function") return;
    const normalized = String(lang).toLowerCase();
    const previous = currentLanguage();
    if (normalized === previous) {
      applyLanguageButtons();
      return;
    }
    I18n.setLanguage(normalized);
    applyLanguageButtons();
    applyDatasetTranslations();
    refreshProfileLocale();
    const token = getToken();
    if (token) {
      const res = await apiFetch("/profile/preferences/", {
        method: "PUT",
        body: { language: normalized },
      });
      if (!res.ok) {
        if (res.status === 401) {
          profileDenied = true;
          console.warn("[auth] updating preferences denied (401)");
          verifyCurrentAuth().then((ok) => {
            if (!ok) clearToken();
          });
        }
        console.warn("[profile] failed to persist language preference", res);
        return;
      }
    }
    updateNavForAuth();
  }

  async function handleProfileSave(event) {
    event.preventDefault();

    let snapshot = profileSnapshot;
    if (!snapshot) {
      snapshot = await ensureProfileSnapshot();
      if (!snapshot) {
        const failMsg = tr("profile.modal.save_error");
        setProfileSaveMessage(failMsg, "error");
        toast(failMsg, "error", tr("profile.modal.save_error_title"));
        return;
      }
    }

    const profileCore = snapshot?.profile || {};
    const currentAge = profileCore?.age ?? null;
    const currentSex = (profileCore?.sex || "").toLowerCase();

    const ageRaw = profileAgeInput ? String(profileAgeInput.value || "").trim() : "";
    const sexRaw = profileSexSelect ? String(profileSexSelect.value || "").trim() : "";

    const updates = {};

    if (ageRaw !== "") {
      const ageNum = Number.parseInt(ageRaw, 10);
      if (!Number.isFinite(ageNum) || Number.isNaN(ageNum) || ageNum < 0 || ageNum > 120) {
        const msg = tr("profile.modal.form_age_invalid");
        setProfileSaveMessage(msg, "error");
        toast(msg, "error", tr("profile.modal.save_error_title"));
        return;
      }
      if (currentAge !== ageNum) {
        updates.age = ageNum;
      }
    }

    const normalizedSex = sexRaw ? sexRaw.toLowerCase() : "";
    if (normalizedSex) {
      if (!ALLOWED_SEX_VALUES.has(normalizedSex)) {
        const msg = tr("profile.modal.form_sex_invalid");
        setProfileSaveMessage(msg, "error");
        toast(msg, "error", tr("profile.modal.save_error_title"));
        return;
      }
      if (normalizedSex !== currentSex) {
        updates.sex = normalizedSex;
      }
    } else if (currentSex && currentSex !== "unknown") {
      updates.sex = "unknown";
    }

    if (!Object.keys(updates).length) {
      setProfileSaveMessage(tr("profile.modal.form_no_changes"), "info");
      return;
    }

    setProfileSaveMessage(tr("profile.modal.save_saving"), "info");
    if (profileSaveBtn) profileSaveBtn.disabled = true;

    const res = await apiFetch("/profile/", { method: "PUT", body: updates });

    if (profileSaveBtn) profileSaveBtn.disabled = false;

    if (!res.ok) {
      if (res.status === 401) {
        profileDenied = true;
        verifyCurrentAuth().then((ok) => {
          if (!ok) clearToken();
        });
      }
      const detail = res?.data?.error || res?.data?.msg || tr("profile.modal.save_error");
      setProfileSaveMessage(detail, "error");
      toast(detail, "error", tr("profile.modal.save_error_title"));
      return;
    }

    setProfileSaveMessage(tr("profile.modal.save_success"), "success");
    toast(tr("profile.modal.save_success"), "success");
    await reloadProfileSnapshot();
  }

  async function handleAddAllergy(event) {
    event.preventDefault();
    if (!profileAllergyInput) return;
    const name = profileAllergyInput.value.trim();
    if (!name) {
      setSectionStatus(profileAllergiesStatus, tr("profile.collections.validation_required"), "error");
      return;
    }
    setSectionStatus(profileAllergiesStatus, tr("profile.collections.status_saving"), "info");
    const res = await apiFetch("/profile/allergies/", { method: "POST", body: { name } });
    if (!res.ok) {
      if (res.status === 401) handleProfileUnauthorized();
      const detail = res?.data?.error || res?.data?.msg || tr("profile.collections.allergies.add_error");
      setSectionStatus(profileAllergiesStatus, detail, "error");
      toast(detail, "error", tr("profile.collections.allergies.title"));
      return;
    }
    setSectionStatus(profileAllergiesStatus, tr("profile.collections.allergies.add_success"), "success");
    toast(tr("profile.collections.allergies.add_success"), "success");
    await reloadProfileSnapshot();
  }

  async function handleAllergiesListClick(event) {
    const button = event.target.closest("[data-action='remove-allergy']");
    if (!button) return;
    event.preventDefault();
    const id = parseId(button.dataset.id || button.closest("li")?.dataset.id);
    if (id === null) return;
    await removeAllergy(id);
  }

  async function removeAllergy(id) {
    setSectionStatus(profileAllergiesStatus, tr("profile.collections.status_removing"), "info");
    const res = await apiFetch(`/profile/allergies/${id}/`, { method: "DELETE" });
    if (!res.ok) {
      if (res.status === 401) handleProfileUnauthorized();
      const detail = res?.data?.error || res?.data?.msg || tr("profile.collections.allergies.delete_error");
      setSectionStatus(profileAllergiesStatus, detail, "error");
      toast(detail, "error", tr("profile.collections.allergies.title"));
      return;
    }
    setSectionStatus(profileAllergiesStatus, tr("profile.collections.allergies.delete_success"), "success");
    toast(tr("profile.collections.allergies.delete_success"), "success");
    await reloadProfileSnapshot();
  }

  async function handleAddCondition(event) {
    event.preventDefault();
    if (!profileConditionInput) return;
    const name = profileConditionInput.value.trim();
    if (!name) {
      setSectionStatus(profileConditionsStatus, tr("profile.collections.validation_required"), "error");
      return;
    }
    setSectionStatus(profileConditionsStatus, tr("profile.collections.status_saving"), "info");
    const res = await apiFetch("/profile/conditions/", { method: "POST", body: { name } });
    if (!res.ok) {
      if (res.status === 401) handleProfileUnauthorized();
      const detail = res?.data?.error || res?.data?.msg || tr("profile.collections.conditions.add_error");
      setSectionStatus(profileConditionsStatus, detail, "error");
      toast(detail, "error", tr("profile.collections.conditions.title"));
      return;
    }
    setSectionStatus(profileConditionsStatus, tr("profile.collections.conditions.add_success"), "success");
    toast(tr("profile.collections.conditions.add_success"), "success");
    await reloadProfileSnapshot();
  }

  async function handleConditionsListClick(event) {
    const button = event.target.closest("[data-action='remove-condition']");
    if (!button) return;
    event.preventDefault();
    const id = parseId(button.dataset.id || button.closest("li")?.dataset.id);
    if (id === null) return;
    await removeCondition(id);
  }

  async function removeCondition(id) {
    setSectionStatus(profileConditionsStatus, tr("profile.collections.status_removing"), "info");
    const res = await apiFetch(`/profile/conditions/${id}/`, { method: "DELETE" });
    if (!res.ok) {
      if (res.status === 401) handleProfileUnauthorized();
      const detail = res?.data?.error || res?.data?.msg || tr("profile.collections.conditions.delete_error");
      setSectionStatus(profileConditionsStatus, detail, "error");
      toast(detail, "error", tr("profile.collections.conditions.title"));
      return;
    }
    setSectionStatus(profileConditionsStatus, tr("profile.collections.conditions.delete_success"), "success");
    toast(tr("profile.collections.conditions.delete_success"), "success");
    await reloadProfileSnapshot();
  }

  async function handleAddMedication(event) {
    event.preventDefault();
    if (!profileMedicationName || !profileMedicationDose) return;
    const name = profileMedicationName.value.trim();
    const dosage = profileMedicationDose.value.trim();
    const started_at = profileMedicationStart ? profileMedicationStart.value.trim() : "";
    if (!name || !dosage) {
      setSectionStatus(profileMedicationsStatus, tr("profile.collections.validation_required"), "error");
      return;
    }
    const payload = { drug_name: name, dosage };
    if (started_at) payload.started_at = started_at;
    setSectionStatus(profileMedicationsStatus, tr("profile.collections.status_saving"), "info");
    const res = await apiFetch("/profile/medications/", { method: "POST", body: payload });
    if (!res.ok) {
      if (res.status === 401) handleProfileUnauthorized();
      const detail = res?.data?.error || res?.data?.msg || tr("profile.collections.medications.add_error");
      setSectionStatus(profileMedicationsStatus, detail, "error");
      toast(detail, "error", tr("profile.collections.medications.title"));
      return;
    }
    setSectionStatus(profileMedicationsStatus, tr("profile.collections.medications.add_success"), "success");
    toast(tr("profile.collections.medications.add_success"), "success");
    await reloadProfileSnapshot();
  }

  async function handleMedicationsListClick(event) {
    const button = event.target.closest("[data-action='remove-medication']");
    if (!button) return;
    event.preventDefault();
    const id = parseId(button.dataset.id || button.closest("li")?.dataset.id);
    if (id === null) return;
    await removeMedication(id);
  }

  async function removeMedication(id) {
    setSectionStatus(profileMedicationsStatus, tr("profile.collections.status_removing"), "info");
    const res = await apiFetch(`/profile/medications/${id}/`, { method: "DELETE" });
    if (!res.ok) {
      if (res.status === 401) handleProfileUnauthorized();
      const detail = res?.data?.error || res?.data?.msg || tr("profile.collections.medications.delete_error");
      setSectionStatus(profileMedicationsStatus, detail, "error");
      toast(detail, "error", tr("profile.collections.medications.title"));
      return;
    }
    setSectionStatus(profileMedicationsStatus, tr("profile.collections.medications.delete_success"), "success");
    toast(tr("profile.collections.medications.delete_success"), "success");
    await reloadProfileSnapshot();
  }

  async function handleAddContact(event) {
    event.preventDefault();
    if (!profileContactName) return;
    const name = profileContactName.value.trim();
    const relationship = profileContactRelationship ? profileContactRelationship.value.trim() : "";
    const phone = profileContactPhone ? profileContactPhone.value.trim() : "";
    const email = profileContactEmail ? profileContactEmail.value.trim() : "";
    const is_primary = profileContactPrimary ? Boolean(profileContactPrimary.checked) : false;
    if (!name) {
      setSectionStatus(profileContactsStatus, tr("profile.collections.validation_required"), "error");
      return;
    }
    if (!phone && !email) {
      setSectionStatus(profileContactsStatus, tr("profile.collections.contacts.validation_contact"), "error");
      return;
    }
    const payload = { name };
    if (relationship) payload.relationship = relationship;
    if (phone) payload.phone = phone;
    if (email) payload.email = email;
    if (is_primary) payload.is_primary = true;
    setSectionStatus(profileContactsStatus, tr("profile.collections.status_saving"), "info");
    const res = await apiFetch("/profile/emergency-contacts/", { method: "POST", body: payload });
    if (!res.ok) {
      if (res.status === 401) handleProfileUnauthorized();
      const detail = res?.data?.error || res?.data?.msg || tr("profile.collections.contacts.add_error");
      setSectionStatus(profileContactsStatus, detail, "error");
      toast(detail, "error", tr("profile.collections.contacts.title"));
      return;
    }
    setSectionStatus(profileContactsStatus, tr("profile.collections.contacts.add_success"), "success");
    toast(tr("profile.collections.contacts.add_success"), "success");
    await reloadProfileSnapshot();
  }

  async function handleContactsListClick(event) {
    const button = event.target.closest("[data-action='remove-contact']");
    if (!button) return;
    event.preventDefault();
    const id = parseId(button.dataset.id || button.closest("li")?.dataset.id);
    if (id === null) return;
    await removeContact(id);
  }

  async function removeContact(id) {
    setSectionStatus(profileContactsStatus, tr("profile.collections.status_removing"), "info");
    const res = await apiFetch(`/profile/emergency-contacts/${id}/`, { method: "DELETE" });
    if (!res.ok) {
      if (res.status === 401) handleProfileUnauthorized();
      const detail = res?.data?.error || res?.data?.msg || tr("profile.collections.contacts.delete_error");
      setSectionStatus(profileContactsStatus, detail, "error");
      toast(detail, "error", tr("profile.collections.contacts.title"));
      return;
    }
    setSectionStatus(profileContactsStatus, tr("profile.collections.contacts.delete_success"), "success");
    toast(tr("profile.collections.contacts.delete_success"), "success");
    await reloadProfileSnapshot();
  }

  async function handleAddFamilyMember(event) {
    event.preventDefault();
    if (!profileFamilyName || !profileFamilyRelationship) return;
    const name = profileFamilyName.value.trim();
    const relationship = profileFamilyRelationship.value.trim();
    const birthdate = profileFamilyBirthdate ? profileFamilyBirthdate.value.trim() : "";
    if (!name || !relationship) {
      setSectionStatus(profileFamilyStatus, tr("profile.collections.validation_required"), "error");
      return;
    }
    const payload = { name, relationship };
    if (birthdate) payload.birthdate = birthdate;
    setSectionStatus(profileFamilyStatus, tr("profile.collections.status_saving"), "info");
    const res = await apiFetch("/profile/family-members/", { method: "POST", body: payload });
    if (!res.ok) {
      if (res.status === 401) handleProfileUnauthorized();
      const detail = res?.data?.error || res?.data?.msg || tr("profile.collections.family.add_error");
      setSectionStatus(profileFamilyStatus, detail, "error");
      toast(detail, "error", tr("profile.collections.family.title"));
      return;
    }
    setSectionStatus(profileFamilyStatus, tr("profile.collections.family.add_success"), "success");
    toast(tr("profile.collections.family.add_success"), "success");
    await reloadProfileSnapshot();
  }

  async function handleFamilyListClick(event) {
    const button = event.target.closest("[data-action='remove-family']");
    if (!button) return;
    event.preventDefault();
    const id = parseId(button.dataset.id || button.closest("li")?.dataset.id);
    if (id === null) return;
    await removeFamilyMember(id);
  }

  async function removeFamilyMember(id) {
    setSectionStatus(profileFamilyStatus, tr("profile.collections.status_removing"), "info");
    const res = await apiFetch(`/profile/family-members/${id}/`, { method: "DELETE" });
    if (!res.ok) {
      if (res.status === 401) handleProfileUnauthorized();
      const detail = res?.data?.error || res?.data?.msg || tr("profile.collections.family.delete_error");
      setSectionStatus(profileFamilyStatus, detail, "error");
      toast(detail, "error", tr("profile.collections.family.title"));
      return;
    }
    setSectionStatus(profileFamilyStatus, tr("profile.collections.family.delete_success"), "success");
    toast(tr("profile.collections.family.delete_success"), "success");
    await reloadProfileSnapshot();
  }

  function refreshProfileLocale() {
    applyLanguageButtons();
    if (profileSnapshot) {
      applyProfileMenuUI(profileSnapshot);
      populateProfileModal(profileSnapshot);
    } else {
      if (profileNameEl) profileNameEl.textContent = defaultProfileLabel();
      if (profileEmailEl) profileEmailEl.textContent = "";
      if (profileModal && !profileModal.classList.contains("hidden")) {
        if (profileModalEmail) profileModalEmail.textContent = tr("profile.modal.unknown");
        if (profileModalCreated) profileModalCreated.textContent = tr("profile.modal.unknown");
        if (profileModalStatus) profileModalStatus.textContent = tr("profile.modal.unknown");
        if (profileModalStats) profileModalStats.innerHTML = `<div class="muted">${tr("profile.modal.fetch_error")}</div>`;
      }
    }
  }

  function setBadge(text, cls="badge") {
    const b = $("#authBadge");
    if (!b) return;
    b.className = `badge ${cls}`;
    b.textContent = text;
    if (I18n) I18n.apply();
  }

  async function updateNavForAuth() {
    let token = getToken();
    if (!token) {
      token = await ensureAccessToken();
    }
    const has = !!token;

    if (!has) {
      profileSnapshot = null;
      profileLoading = null;
      profileDenied = false;
      preferencesLoaded = false;
    } else {
      profileDenied = false;
    }

    applyLanguageButtons();

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
    if (profileMenu) profileMenu.classList.toggle("hidden", !has);

    if (profileMenu) {
      if (!has) {
        resetProfileMenuUI();
      } else if (profileSnapshot) {
        refreshProfileLocale();
      } else {
        resetProfileMenuUI();
        ensureProfileSnapshot();
      }
    } else if (!has) {
      resetProfileMenuUI();
    }

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
    if (chatHint) {
      chatHint.style.display = needLogin ? "" : "none";
      if (needLogin) setNodeTextByKey(chatHint, "chat.hint");
    }
    if (diHint) {
      diHint.style.display = needLogin ? "" : "none";
      if (needLogin) setNodeTextByKey(diHint, "drug.hint");
    }
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

  (function initProfileMenu(){
    if (!profileMenu || !profileToggle) {
      if (typeof window !== "undefined") {
        window.__applyProfileLocale = () => {
          resetProfileMenuUI();
          applyLanguageButtons();
        };
      }
      return;
    }

    const handleOutsideClick = (event) => {
      if (!profileMenu || profileMenu.classList.contains("hidden")) return;
      if (profileMenu.contains(event.target)) return;
      setProfileMenuOpen(false);
    };

    const handleEscape = (event) => {
      if (event.key !== "Escape") return;
      if (isProfileModalOpen()) {
        closeProfileModal();
        return;
      }
      if (!profileMenu || profileMenu.dataset.open !== "true") return;
      setProfileMenuOpen(false);
      if (profileToggle) profileToggle.focus();
    };

    on(profileToggle, "click", (event) => {
      event.preventDefault();
      if (profileMenu.classList.contains("hidden")) return;
      const open = profileMenu.dataset.open === "true";
      setProfileMenuOpen(!open);
    });

    if (profileLink) {
      on(profileLink, "click", (event) => {
        event.preventDefault();
        if (profileMenu.classList.contains("hidden")) return;
        setProfileMenuOpen(false);
        openProfileModal();
      });
    }
    if (profileDropdown) {
      on(profileDropdown, "click", (event) => {
        // Prevent buttons inside the dropdown from closing it prematurely via bubbling to document.
        event.stopPropagation();
      });
    }

    document.addEventListener("click", handleOutsideClick);
    document.addEventListener("keydown", handleEscape);

    if (typeof window !== "undefined") {
      window.__applyProfileLocale = refreshProfileLocale;
      window.__applyProfileLocale();
    }
  })();

  (function initLanguageSwitcher(){
    if (!profileLanguageButtons.length) return;
    profileLanguageButtons.forEach((btn) => {
      on(btn, "click", (event) => {
        event.preventDefault();
        const lang = btn.dataset.lang;
        if (!lang) return;
        handleLanguageSelect(lang);
      });
    });
    applyLanguageButtons();
  })();

  (function initProfileModal(){
    if (!profileModal) return;

    if (typeof window !== "undefined") {
      window.__applyProfileModalLocale = refreshProfileLocale;
    }

    const closeNodes = [profileModalClose, profileModalCloseFooter, profileModalBackdrop];
    closeNodes.forEach((node) => {
      if (!node) return;
      on(node, "click", (event) => {
        event.preventDefault();
        closeProfileModal();
      });
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && isProfileModalOpen()) {
        closeProfileModal();
      }
    });

    if (profileModalForm) {
      on(profileModalForm, "submit", handleProfileSave);
    }
    if (profileAgeInput) {
      on(profileAgeInput, "input", () => setProfileSaveMessage(""));
    }
    if (profileSexSelect) {
      on(profileSexSelect, "change", () => setProfileSaveMessage(""));
    }

    if (profileAllergiesForm) on(profileAllergiesForm, "submit", handleAddAllergy);
    if (profileAllergiesList) on(profileAllergiesList, "click", handleAllergiesListClick);
    if (profileConditionsForm) on(profileConditionsForm, "submit", handleAddCondition);
    if (profileConditionsList) on(profileConditionsList, "click", handleConditionsListClick);
    if (profileMedicationsForm) on(profileMedicationsForm, "submit", handleAddMedication);
    if (profileMedicationsList) on(profileMedicationsList, "click", handleMedicationsListClick);
    if (profileContactsForm) on(profileContactsForm, "submit", handleAddContact);
    if (profileContactsList) on(profileContactsList, "click", handleContactsListClick);
    if (profileFamilyForm) on(profileFamilyForm, "submit", handleAddFamilyMember);
    if (profileFamilyList) on(profileFamilyList, "click", handleFamilyListClick);

    if (profileAllergyInput) on(profileAllergyInput, "input", () => setSectionStatus(profileAllergiesStatus, ""));
    if (profileConditionInput) on(profileConditionInput, "input", () => setSectionStatus(profileConditionsStatus, ""));
    if (profileMedicationName) on(profileMedicationName, "input", () => setSectionStatus(profileMedicationsStatus, ""));
    if (profileMedicationDose) on(profileMedicationDose, "input", () => setSectionStatus(profileMedicationsStatus, ""));
    if (profileMedicationStart) on(profileMedicationStart, "input", () => setSectionStatus(profileMedicationsStatus, ""));
    if (profileContactName) on(profileContactName, "input", () => setSectionStatus(profileContactsStatus, ""));
    if (profileContactRelationship) on(profileContactRelationship, "input", () => setSectionStatus(profileContactsStatus, ""));
    if (profileContactPhone) on(profileContactPhone, "input", () => setSectionStatus(profileContactsStatus, ""));
    if (profileContactEmail) on(profileContactEmail, "input", () => setSectionStatus(profileContactsStatus, ""));
    if (profileFamilyName) on(profileFamilyName, "input", () => setSectionStatus(profileFamilyStatus, ""));
    if (profileFamilyRelationship) on(profileFamilyRelationship, "input", () => setSectionStatus(profileFamilyStatus, ""));
    if (profileFamilyBirthdate) on(profileFamilyBirthdate, "input", () => setSectionStatus(profileFamilyStatus, ""));
  })();

  // ------- Logout Button -------
  on($("#navLogout"), "click", async (e) => {
    e.preventDefault();
    let serverOk = false;
    try {
      const resp = await fetch("/auth/logout", {
        method: "POST",
        credentials: "same-origin"
      });
      if (resp.ok || resp.status === 401) {
        serverOk = true;
      } else {
        console.warn("[auth] logout returned status", resp.status);
      }
    } catch (err) {
      console.warn("[auth] logout request failed", err);
    }
    clearToken();
    updateNavForAuth();
    toast(serverOk ? tr("common.logout_success") : tr("common.logout_success"));
    setProfileMenuOpen(false);
    closeProfileModal();
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
    const setHint = (key) => {
      hint.style.display = "";
      setNodeTextByKey(hint, key);
    };
    const token = getToken();
    if (!token) {
      setHint("history.prompt_login");
      return;
    }
    setHint("history.empty");
    (async () => {
      const res = await apiFetch("/profile/health-history/?page=1&per_page=5");
      if (!res.ok) {
        if (res.status === 401) {
          setHint("history.need_reauth");
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
        delete hint.dataset.i18nKey;
      } else {
        setHint("history.empty");
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
  applyDatasetTranslations();
  updateNavForAuth();

  window.addEventListener("auth:state-changed", () => {
    updateNavForAuth();
  });
  async function verifyCurrentAuth() {
    if (authVerifyPromise) return authVerifyPromise;
    const token = getToken();
    if (!token) return false;
    authVerifyPromise = (async () => {
      try {
        const resp = await fetch("/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
          credentials: "same-origin"
        });
        if (!resp.ok) {
          console.warn("[auth] /auth/me returned", resp.status);
        }
        return resp.ok;
      } catch (err) {
        console.warn("[auth] verification request failed", err);
        return false;
      } finally {
        authVerifyPromise = null;
      }
    })();
    return authVerifyPromise;
  }

  async function refreshAccessToken() {
    if (refreshPromise) return refreshPromise;
    refreshPromise = (async () => {
      try {
        const resp = await fetch("/auth/refresh", {
          method: "POST",
          credentials: "same-origin"
        });
        if (!resp.ok) {
          console.warn("[auth] refresh failed with status", resp.status);
          return "";
        }
        const data = await resp.json().catch(() => ({}));
        const token = data?.access_token;
        if (token) {
          setToken(token);
          return token;
        }
        console.warn("[auth] refresh response missing access_token");
        return "";
      } catch (err) {
        console.warn("[auth] refresh request failed", err);
        return "";
      } finally {
        refreshPromise = null;
      }
    })();
    return refreshPromise;
  }

  async function ensureAccessToken() {
    const existing = getToken();
    if (existing) return existing;
    const refreshed = await refreshAccessToken();
    return refreshed || "";
  }

})();
