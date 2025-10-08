(function(){
  const SUPPORTED = ["en", "de", "es", "fr", "it"];
  const DEFAULT_LANG = "en";
  const STORAGE_KEY = "language";

  const TRANSLATIONS = {
    en: {
      nav: {
        brand: "My Health App",
        login: "Login",
        register: "Register",
        logout: "Logout",
        badge_auth: "Signed in",
        badge_guest: "Guest",
        skip: "Skip to content",
        theme_toggle: "Toggle theme",
      },
      common: {
        noscript: "This application requires JavaScript.",
        network_error: {
          title: "Connection issue",
          message: "We couldn’t reach the server. Check your connection and try again.",
        },
        logout_success: "Signed out.",
        error_code: "Error ({status})",
        close: "Close",
        yes: "Yes",
        no: "No",
      },
      auth: {
        login: {
          already: "Already signed in. Redirecting to dashboard…",
          logging_in: "Signing in…",
          missing_fields: "Please enter email and password.",
          generic_error: "Login failed.",
          no_token: "No access_token in response.",
          success: "Signed in. Redirecting to dashboard…",
          network_error: "Network error. Please try again.",
          logout_button: "Logout",
          hint_register: "Need an account? Use the registration form.",
          hint_reset: "Check your email/password or use the reset option.",
        },
        register: {
          submitting: "Creating account…",
          failure: "Registration failed.",
          success: "Account created. You can now sign in.",
          network_error: "Network error. Please try again.",
          suggestion_login: "Use the login form or reset your password.",
          hint_password: "Passwords must contain letters and digits.",
          hint_strength: "Minimum length: 8 characters.",
        },
      },
      chat: {
        user_label: "You",
        assistant_label: "Assistant",
        hint: "Note: you need to be signed in to use the chat.",
      },
      symptom: {
        loading: "Checking…",
        summary: {
          risk: "Risk",
          urgency: "Urgency",
        },
        no_diagnosis: "No suggestions.",
      },
      drug: {
        remove: "remove",
        need_entry: "Please enter at least one medication.",
        summary: {
          safe: "Safe to proceed",
          moderate: "Moderate",
          severe: "Severe",
        },
        sections: {
          overdose: "Overdoses",
          interactions: "Interactions",
          contraindications: "Contraindications",
          none_found: "No issues found.",
        },
      },
      history: {
        prompt_login: "Sign in to view your recent health checks.",
        empty: "No health checks recorded yet.",
        need_reauth: "Please sign in again to view your recent health checks.",
      },
      forms: {
        chat_placeholder: "Describe your symptoms…",
        symptom_placeholder: "e.g., Fever 38.1, sore throat",
        drug_name: "e.g., Ibuprofen",
        drug_dose: "400 mg",
        drug_route: "oral",
        allergies: "e.g., Penicillin",
        conditions: "e.g., Hypertension",
      },
      buttons: {
        chat_send: "Send",
        symptom_start: "Start check",
        drug_add: "Add medication",
        drug_check: "Check",
        register: "Create account",
      },
      sections: {
        dashboard: "Dashboard",
        chat_title: "Diagnostic Assistant (Chat)",
        history_title: "Recent Health Checks",
        symptom_title: "Symptom Checker",
        drug_title: "Drug Interactions",
        result: "Result",
      },
      exports: {
        title: "Data Exports",
        description: "Download your data for support requests or personal records.",
        anonymize_label: "Anonymize personal details",
        buttons: {
          chat_json: "Chat Transcript (Detailed)",
          chat_text: "Chat Transcript (Plain Text)",
          audit_csv: "Audit Log (Admin)",
        },
        status: {
          idle: "",
          require_login: "Sign in to download exports.",
          loading: "Preparing export…",
          success_chat_json: "Chat transcript (JSON) downloaded.",
          success_chat_text: "Chat transcript (Text) downloaded.",
          success_audit: "Audit export downloaded.",
          forbidden: "This export requires administrator access.",
          error: "Download failed. Please try again.",
        },
      },
    },
    de: {
      nav: {
        brand: "My Health App",
        login: "Login",
        register: "Registrieren",
        logout: "Logout",
        badge_auth: "Eingeloggt",
        badge_guest: "Gast",
        skip: "Zum Inhalt springen",
        theme_toggle: "Theme umschalten",
      },
      common: {
        noscript: "Diese Anwendung benötigt JavaScript.",
        network_error: {
          title: "Verbindungsproblem",
          message: "Wir konnten keine Verbindung zum Server herstellen. Bitte überprüfe deine Internetverbindung und versuche es erneut.",
        },
        logout_success: "Abgemeldet.",
        error_code: "Fehler ({status})",
        close: "Schließen",
        yes: "Ja",
        no: "Nein",
      },
      auth: {
        login: {
          already: "Bereits eingeloggt. Weiter zum Dashboard …",
          logging_in: "Login läuft…",
          missing_fields: "Bitte E-Mail und Passwort eingeben.",
          generic_error: "Login fehlgeschlagen.",
          no_token: "Kein access_token in der Antwort.",
          success: "Eingeloggt. Weiter zum Dashboard …",
          network_error: "Netzwerkfehler. Bitte erneut versuchen.",
          logout_button: "Logout",
          hint_register: "Noch kein Konto? Bitte über die Registrierung anmelden.",
          hint_reset: "Passwort prüfen oder Zurücksetzen-Funktion nutzen.",
        },
        register: {
          submitting: "Registrierung läuft…",
          failure: "Registrierung fehlgeschlagen.",
          success: "Konto erstellt. Du kannst dich jetzt einloggen.",
          network_error: "Netzwerkfehler. Bitte erneut versuchen.",
          suggestion_login: "Bitte das Login-Formular verwenden oder Passwort zurücksetzen.",
          hint_password: "Passwörter benötigen Buchstaben und Ziffern.",
          hint_strength: "Mindestens 8 Zeichen Länge.",
        },
      },
      chat: {
        user_label: "Du",
        assistant_label: "Assistent",
        hint: "Hinweis: Für den Chat muss man eingeloggt sein.",
      },
      symptom: {
        loading: "Wird geprüft …",
        summary: {
          risk: "Risiko",
          urgency: "Dringlichkeit",
        },
        no_diagnosis: "Keine Vorschläge.",
      },
      drug: {
        remove: "entfernen",
        need_entry: "Bitte mindestens eine Arznei eingeben.",
        summary: {
          safe: "Sicher fortfahren",
          moderate: "Moderate",
          severe: "Schwere",
        },
        sections: {
          overdose: "Überdosierungen",
          interactions: "Interaktionen",
          contraindications: "Kontraindikationen",
          none_found: "Keine Probleme gefunden.",
        },
      },
      history: {
        prompt_login: "Melde dich an, um deine letzten Gesundheits-Checks zu sehen.",
        empty: "Noch keine Gesundheits-Checks gespeichert.",
        need_reauth: "Bitte melde dich erneut an, um deine letzten Gesundheits-Checks zu sehen.",
      },
      forms: {
        chat_placeholder: "Beschreibe kurz deine Beschwerden…",
        symptom_placeholder: "z. B. Fieber 38.1, Halsschmerzen",
        drug_name: "z. B. Ibuprofen",
        drug_dose: "400 mg",
        drug_route: "oral",
        allergies: "z. B. Penicillin",
        conditions: "z. B. Hypertonie",
      },
      buttons: {
        chat_send: "Senden",
        symptom_start: "Check starten",
        drug_add: "+ Arznei hinzufügen",
        drug_check: "Prüfen",
        register: "Konto erstellen",
      },
      sections: {
        dashboard: "Dashboard",
        chat_title: "Diagnose-Assistent (Chat)",
        history_title: "Letzte Gesundheits-Checks",
        symptom_title: "Symptom Checker",
        drug_title: "Arzneimittelinteraktionen",
        result: "Ergebnis",
      },
      exports: {
        title: "Datenexporte",
        description: "Lade deine Profildaten und Chat-Verläufe für Support oder eigene Unterlagen herunter.",
        anonymize_label: "Personenbezogene Daten anonymisieren",
        buttons: {
          chat_json: "Chat-Protokoll (Detail)",
          chat_text: "Chat-Protokoll (Text)",
          audit_csv: "Audit-Log (Admin)",
        },
        status: {
          idle: "",
          require_login: "Bitte melde dich an, um Exporte herunterzuladen.",
          loading: "Export wird vorbereitet …",
          success_chat_json: "Chat-Verlauf (JSON) heruntergeladen.",
          success_chat_text: "Chat-Verlauf (Text) heruntergeladen.",
          success_audit: "Audit-Export heruntergeladen.",
          forbidden: "Dieser Export erfordert Administratorrechte.",
          error: "Download fehlgeschlagen. Bitte erneut versuchen.",
        },
      },
    },
  };

  function normalize(lang) {
    if (!lang) return DEFAULT_LANG;
    const lower = String(lang).toLowerCase();
    return SUPPORTED.includes(lower) ? lower : DEFAULT_LANG;
  }

  function getStoredLanguage() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return normalize(stored);
    } catch (err) {
      /* ignore storage errors */
    }
    const htmlLang = document.documentElement.getAttribute("lang");
    return normalize(htmlLang);
  }

  let currentLang = getStoredLanguage();

  function setLanguage(lang, options) {
    const normalized = normalize(lang);
    currentLang = normalized;
    if (!options || options.persist !== false) {
      try {
        localStorage.setItem(STORAGE_KEY, normalized);
      } catch (err) {
        /* ignore storage errors */
      }
    }
    document.documentElement.setAttribute("lang", normalized);
    applyTranslations();
  }

  function t(key, vars) {
    const path = key.split(".");
    const source = TRANSLATIONS[currentLang] || {};
    const fallback = TRANSLATIONS.en || {};
    let value = path.reduce((acc, part) => (acc && acc[part] !== undefined ? acc[part] : undefined), source);
    if (value === undefined) {
      value = path.reduce((acc, part) => (acc && acc[part] !== undefined ? acc[part] : undefined), fallback);
    }
    if (typeof value !== "string") {
      return key;
    }
    if (vars) {
      for (const [token, replacement] of Object.entries(vars)) {
        value = value.replace(new RegExp(`\\{${token}\\}`, "g"), replacement);
      }
    }
    return value;
  }

  const TEXT_SELECTORS = {
    "#navLogin": "nav.login",
    "#navRegister": "nav.register",
    "#navLogout": "nav.logout",
    "header .brand": "nav.brand",
    ".skip-link": "nav.skip",
    "#chat_hint": "chat.hint",
    "#chat-card-title": "sections.chat_title",
    "#history-card-title": "sections.history_title",
    "#symptom-card-title": "sections.symptom_title",
    "#drug-card-title": "sections.drug_title",
    "#regForm button[type=submit]": "buttons.register",
    "#chat_send": "buttons.chat_send",
    "#sc_submit": "buttons.symptom_start",
    "#di_add": "buttons.drug_add",
    "#di_check": "buttons.drug_check",
    "#exports-card-title": "exports.title",
    "#exportHint": "exports.description",
    "#exportChatJson": "exports.buttons.chat_json",
    "#exportChatText": "exports.buttons.chat_text",
    "#exportAuditCsv": "exports.buttons.audit_csv",
    "#exportAnonymizeLabel": "exports.anonymize_label",
  };

  const ATTR_SELECTORS = [
    { selector: "#chat_input", attr: "placeholder", key: "forms.chat_placeholder" },
    { selector: "#sc_symptoms", attr: "placeholder", key: "forms.symptom_placeholder" },
    { selector: "#di_name", attr: "placeholder", key: "forms.drug_name" },
    { selector: "#di_dose", attr: "placeholder", key: "forms.drug_dose" },
    { selector: "#di_route", attr: "placeholder", key: "forms.drug_route" },
    { selector: "#di_allergies", attr: "placeholder", key: "forms.allergies" },
    { selector: "#di_conditions", attr: "placeholder", key: "forms.conditions" },
  ];

  function applyTranslations() {
    for (const [selector, value] of Object.entries(TEXT_SELECTORS)) {
      const el = document.querySelector(selector);
      if (!el) continue;
      const text = typeof value === "function" ? value() : t(value);
      if (text) el.textContent = text;
    }
    for (const { selector, attr, key } of ATTR_SELECTORS) {
      const el = document.querySelector(selector);
      if (!el) continue;
      const text = t(key);
      if (text) el.setAttribute(attr, text);
    }
    const noscript = document.querySelector("noscript div");
    if (noscript) noscript.textContent = t("common.noscript");
  }

  function getLanguage() {
    return currentLang;
  }

  // expose globally
  window.I18n = {
    t,
    setLanguage,
    getLanguage,
    apply: applyTranslations,
    data: { translations: TRANSLATIONS },
  };

  document.documentElement.setAttribute("lang", currentLang);
  if (document.readyState !== "loading") {
    applyTranslations();
  } else {
    document.addEventListener("DOMContentLoaded", applyTranslations, { once: true });
  }
})();
