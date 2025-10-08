# MedAssistant · Backlog (Stand: 2025-10-07)

## Priorität Hoch
- [x] Audit- und Support-Export bereitstellen (CLI-Erweiterung in `health_app/__init__.py` + REST-Endpoint), inkl. Filter nach Zeitraum/User, optionaler Pseudonymisierung und verifizierenden Tests für JSON/CSV-Payloads.
- [x] Medikamentenerinnerungen tatsächlich ausspielen: Scheduler/Worker für E-Mail/Push/SMS in `health_app/services/reminder_service.py` bauen, `UserPreferences.notify_*` respektieren und Versandprotokolle speichern.
- [x] Mehrsprachigkeit aktivieren: UI-Strings (`health_app/static/js/app.js`, Templates) und Fallback-/Mailtexte (`health_app/services/ai_service.py`, Mail-Utilities) anhand von `UserPreferences.language` lokalisieren, inklusive automatisierter Tests.

## Priorität Mittel
- [x] Self-Service-Downloads in der Web-Oberfläche anbieten (Buttons/Modals für `/profile/export`, `/chat/export`, künftigen Audit-Export) mit Ladezustand und barrierefreien Hinweisen.
- [x] Dokumentation nachziehen (`docs/user_manual.md`, `docs/api.md`, `docs/deployment.md`): neue Exportfunktionen, MFA-Status und Reminder-Workflow beschreiben, veraltete TODO-Hinweise entfernen.
- [x] Datenhaltung aufräumen: Rolling-Retention für Chat-Sessions und `chat_messages` (z. B. 90 Tage) plus begleitender CLI (`flask prune-chat-history`) und Tests, damit PII nicht dauerhaft bleibt.

## Priorität Niedrig
- [x] Mobile UX verbessern: Layout/Assets in `health_app/static/css/style.css` und `templates/web` auf echte Mobile-First-Layouts trimmen (reduzierte Animationen, vereinfachte Navigation, bessere Screenreader-Order).
- [x] Observability ergänzen: Kennzahlen zu AI-Fallbacks (`health_app/services/ai_service.py`) und Rate-Limit-Hits (`health_app/utils/rate_limit.py`) an Prometheus/OTel ausgeben, Alerts für hohe Fehlerquoten definieren.
- [x] Datenexporte optional anonymisieren: Pipeline in `health_app/routes/profile.py` & künftigem Audit-Export, die personenbezogene Felder maskiert und Auswahl im UI zulässt.
