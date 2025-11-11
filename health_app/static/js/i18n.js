(function(){
  const SUPPORTED = ["en", "de"];
  const DEFAULT_LANG = "en";
  const STORAGE_KEY = "language";

  const TRANSLATIONS = {
    en: {
      nav: {
        brand: "My Health App",
        login: "Login",
        register: "Register",
        logout: "Logout",
        profile: "Profile",
        menu: "Profile menu",
        signed_in_as: "Signed in as",
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
        hint: "Note: you need to be signed in to run the interaction check.",
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
        profile_age: "e.g., 35",
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
      profile: {
        menu: {
          language: "Language",
        },
        modal: {
          title: "Profile",
          email_label: "Email",
          created_label: "Account created",
          status_label: "Status",
          close: "Close",
          active: "Active",
          inactive: "Inactive",
          email_verified: "Email verified",
          email_unverified: "Email not verified",
          unknown: "Unknown",
          age_label: "Age",
          sex_label: "Sex",
          sex_unknown: "Unknown",
          form_title: "Profile information",
          form_age: "Age",
          form_sex: "Sex",
          sex_placeholder: "Select…",
          sex_female: "Female",
          sex_male: "Male",
          sex_other: "Other",
          sex_unknown_option: "Prefer not to say",
          save: "Save changes",
          save_saving: "Saving…",
          save_success: "Profile updated.",
          save_error: "Could not save changes.",
          save_error_title: "Update failed",
          form_no_changes: "No changes to save.",
          form_age_invalid: "Enter a valid age.",
          form_sex_invalid: "Select a valid option.",
          no_stats: "No additional metrics yet.",
          fetch_error: "Couldn’t load profile details.",
          stat_allergies: "Allergies",
          stat_conditions: "Conditions",
          stat_medications: "Active medications",
          stat_checks: "Health checks",
          stat_contacts: "Emergency contacts",
          stat_family: "Family members",
        },
        collections: {
          add_button: "Add",
          remove_button: "Remove",
          status_saving: "Saving…",
          status_removing: "Removing…",
          validation_required: "Please fill out the required field.",
          allergies: {
            title: "Allergies",
            label: "Allergy name",
            placeholder: "Penicillin",
            empty: "No allergies recorded yet.",
            add_success: "Allergy added.",
            add_error: "Could not add allergy.",
            delete_success: "Allergy removed.",
            delete_error: "Could not remove allergy.",
          },
          conditions: {
            title: "Conditions",
            label: "Condition name",
            placeholder: "Hypertension",
            empty: "No conditions recorded yet.",
            add_success: "Condition added.",
            add_error: "Could not add condition.",
            delete_success: "Condition removed.",
            delete_error: "Could not remove condition.",
          },
          medications: {
            title: "Active medications",
            name_label: "Medication",
            dose_label: "Dosage",
            start_label: "Start date",
            placeholder_name: "Ibuprofen",
            placeholder_dose: "400 mg",
            unknown_drug: "Unknown medication",
            empty: "No medications recorded yet.",
            add_success: "Medication added.",
            add_error: "Could not add medication.",
            delete_success: "Medication removed.",
            delete_error: "Could not remove medication.",
            active_badge: "Active",
            inactive_badge: "Inactive",
            started: "Since {date}",
            ended: "Ended {date}",
          },
          contacts: {
            title: "Emergency contacts",
            name_label: "Name",
            relationship_label: "Relationship",
            phone_label: "Phone",
            email_label: "Email",
            primary_label: "Primary contact",
            placeholder_name: "Max Mustermann",
            placeholder_relationship: "Partner",
            placeholder_phone: "+49 160 1234567",
            placeholder_email: "max@example.com",
            empty: "No emergency contacts yet.",
            add_success: "Contact saved.",
            add_error: "Could not add contact.",
            delete_success: "Contact removed.",
            delete_error: "Could not remove contact.",
            validation_contact: "Provide at least a phone number or email.",
            primary_badge: "Primary",
          },
          family: {
            title: "Family members",
            name_label: "Name",
            relationship_label: "Relationship",
            birthdate_label: "Birthdate",
            placeholder_name: "Anna Mustermann",
            placeholder_relationship: "Mother",
            empty: "No family members listed yet.",
            add_success: "Family member added.",
            add_error: "Could not add family member.",
            delete_success: "Family member removed.",
            delete_error: "Could not remove family member.",
          },
          history: {
            title: "Health checks",
            empty: "No health checks recorded yet.",
            hint: "Use the Symptom Checker to create new entries.",
            risk: "Risk: {level}",
          },
          untitled: "Unnamed entry",
        },
      },
      languages: {
        short: {
          de: "DE",
          en: "EN",
        },
        full: {
          de: "German",
          en: "English",
        },
      },
    },
    de: {
      nav: {
        brand: "My Health App",
        login: "Login",
        register: "Registrieren",
        logout: "Logout",
        profile: "Profil",
        menu: "Profilmenü",
        signed_in_as: "Angemeldet als",
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
        hint: "Hinweis: Für die Prüfung muss man eingeloggt sein.",
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
        profile_age: "z. B. 35",
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
      profile: {
        menu: {
          language: "Sprache",
        },
        modal: {
          title: "Profil",
          email_label: "E-Mail",
          created_label: "Konto erstellt",
          status_label: "Status",
          close: "Schließen",
          active: "Aktiv",
          inactive: "Inaktiv",
          email_verified: "E-Mail bestätigt",
          email_unverified: "E-Mail nicht bestätigt",
          unknown: "Unbekannt",
          age_label: "Alter",
          sex_label: "Geschlecht",
          sex_unknown: "Unbekannt",
          form_title: "Profilinformationen",
          form_age: "Alter",
          form_sex: "Geschlecht",
          sex_placeholder: "Bitte auswählen…",
          sex_female: "Weiblich",
          sex_male: "Männlich",
          sex_other: "Anderes",
          sex_unknown_option: "Keine Angabe",
          save: "Änderungen speichern",
          save_saving: "Speichern…",
          save_success: "Profil aktualisiert.",
          save_error: "Änderungen konnten nicht gespeichert werden.",
          save_error_title: "Aktualisierung fehlgeschlagen",
          form_no_changes: "Keine Änderungen zum Speichern.",
          form_age_invalid: "Bitte ein gültiges Alter eingeben.",
          form_sex_invalid: "Bitte eine gültige Option wählen.",
          no_stats: "Noch keine weiteren Kennzahlen.",
          fetch_error: "Profildaten konnten nicht geladen werden.",
          stat_allergies: "Allergien",
          stat_conditions: "Erkrankungen",
          stat_medications: "Aktive Medikamente",
          stat_checks: "Gesundheits-Checks",
          stat_contacts: "Notfallkontakte",
          stat_family: "Familienmitglieder",
        },
        collections: {
          add_button: "Hinzufügen",
          remove_button: "Entfernen",
          status_saving: "Wird gespeichert …",
          status_removing: "Wird entfernt …",
          validation_required: "Bitte das Pflichtfeld ausfüllen.",
          allergies: {
            title: "Allergien",
            label: "Allergie",
            placeholder: "Penicillin",
            empty: "Noch keine Allergien erfasst.",
            add_success: "Allergie gespeichert.",
            add_error: "Allergie konnte nicht gespeichert werden.",
            delete_success: "Allergie entfernt.",
            delete_error: "Allergie konnte nicht entfernt werden.",
          },
          conditions: {
            title: "Erkrankungen",
            label: "Erkrankung",
            placeholder: "Hypertonie",
            empty: "Noch keine Erkrankungen erfasst.",
            add_success: "Erkrankung gespeichert.",
            add_error: "Erkrankung konnte nicht gespeichert werden.",
            delete_success: "Erkrankung entfernt.",
            delete_error: "Erkrankung konnte nicht entfernt werden.",
          },
          medications: {
            title: "Aktive Medikamente",
            name_label: "Medikament",
            dose_label: "Dosierung",
            start_label: "Beginn",
            placeholder_name: "Ibuprofen",
            placeholder_dose: "400 mg",
            unknown_drug: "Unbekanntes Medikament",
            empty: "Noch keine Medikamente erfasst.",
            add_success: "Medikament gespeichert.",
            add_error: "Medikament konnte nicht gespeichert werden.",
            delete_success: "Medikament entfernt.",
            delete_error: "Medikament konnte nicht entfernt werden.",
            active_badge: "Aktiv",
            inactive_badge: "Inaktiv",
            started: "Seit {date}",
            ended: "Beendet {date}",
          },
          contacts: {
            title: "Notfallkontakte",
            name_label: "Name",
            relationship_label: "Beziehung",
            phone_label: "Telefon",
            email_label: "E-Mail",
            primary_label: "Primärer Kontakt",
            placeholder_name: "Max Mustermann",
            placeholder_relationship: "Partner",
            placeholder_phone: "+49 160 1234567",
            placeholder_email: "max@example.com",
            empty: "Noch keine Notfallkontakte erfasst.",
            add_success: "Kontakt gespeichert.",
            add_error: "Kontakt konnte nicht gespeichert werden.",
            delete_success: "Kontakt entfernt.",
            delete_error: "Kontakt konnte nicht entfernt werden.",
            validation_contact: "Bitte mindestens Telefon oder E-Mail angeben.",
            primary_badge: "Primär",
          },
          family: {
            title: "Familienmitglieder",
            name_label: "Name",
            relationship_label: "Beziehung",
            birthdate_label: "Geburtsdatum",
            placeholder_name: "Anna Mustermann",
            placeholder_relationship: "Mutter",
            empty: "Noch keine Familienmitglieder erfasst.",
            add_success: "Familienmitglied gespeichert.",
            add_error: "Familienmitglied konnte nicht gespeichert werden.",
            delete_success: "Familienmitglied entfernt.",
            delete_error: "Familienmitglied konnte nicht entfernt werden.",
          },
          history: {
            title: "Gesundheits-Checks",
            empty: "Noch keine Gesundheits-Checks erfasst.",
            hint: "Nutze den Symptom Checker, um neue Einträge anzulegen.",
            risk: "Risiko: {level}",
          },
          untitled: "Ohne Titel",
        },
      },
      languages: {
        short: {
          de: "DE",
          en: "EN",
        },
        full: {
          de: "Deutsch",
          en: "Englisch",
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
    "#profileLink": "nav.profile",
    "#profileSummaryLabel": "nav.signed_in_as",
    "#profileLanguageLabel": "profile.menu.language",
    "#profileModalTitle": "profile.modal.title",
    "#profileModalEmailLabel": "profile.modal.email_label",
    "#profileModalCreatedLabel": "profile.modal.created_label",
    "#profileModalStatusLabel": "profile.modal.status_label",
    "#profileModalCloseFooter": "profile.modal.close",
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
    "#di_hint": "drug.hint",
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
    { selector: "#profileAge", attr: "placeholder", key: "forms.profile_age" },
    { selector: "#profileAllergyInput", attr: "placeholder", key: "profile.collections.allergies.placeholder" },
    { selector: "#profileConditionInput", attr: "placeholder", key: "profile.collections.conditions.placeholder" },
    { selector: "#profileMedicationName", attr: "placeholder", key: "profile.collections.medications.placeholder_name" },
    { selector: "#profileMedicationDose", attr: "placeholder", key: "profile.collections.medications.placeholder_dose" },
    { selector: "#profileContactName", attr: "placeholder", key: "profile.collections.contacts.placeholder_name" },
    { selector: "#profileContactRelationship", attr: "placeholder", key: "profile.collections.contacts.placeholder_relationship" },
    { selector: "#profileContactPhone", attr: "placeholder", key: "profile.collections.contacts.placeholder_phone" },
    { selector: "#profileContactEmail", attr: "placeholder", key: "profile.collections.contacts.placeholder_email" },
    { selector: "#profileFamilyName", attr: "placeholder", key: "profile.collections.family.placeholder_name" },
    { selector: "#profileFamilyRelationship", attr: "placeholder", key: "profile.collections.family.placeholder_relationship" },
    { selector: "#profileToggle", attr: "aria-label", key: "nav.menu" },
    { selector: "#profileModalClose", attr: "aria-label", key: "profile.modal.close" },
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
    if (window.__applyProfileLocale) window.__applyProfileLocale();
    if (window.__applyProfileModalLocale) window.__applyProfileModalLocale();
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
