# MedAssistant · Backlog (Stand: 2025-11-07)

## Priorität Hoch
- [ ] Produktionsgeheimnisse erzwingen
  - App-Start in `health_app/__init__.py` abbrechen, wenn `SECRET_KEY` oder `JWT_SECRET_KEY` auf den Dev-Defaults stehen.
  - Beispiel-Env (`.env.example`, Docs) ergänzen und Rollout-Checkliste in `docs/deployment.md` verlinken.
  - Smoke-Test (`pytest` + manueller Start) durchführen, damit Prod-Deploys nicht versehentlich scheitern.
- [ ] Security-Header automatisiert testen
  - Neue Testdatei `tests/test_security_headers.py` anlegen, die CSP, COOP/CORP und Referrer-Policy auf Kernrouten (`/`, `/login`, `/register`, `/metrics`) prüft.
  - Nonce-Handling validieren (Header enthält `'nonce-…'` passend zum Inline-Skript).
  - Tests in CI hinterlegen und in `docs/security.md` als Pflichtlauf nennen.
- [ ] Refresh-Tokens widerrufbar machen
  - Token-IDs (`jti`) beim Ausstellen speichern (`models.py`, neue Tabelle `revoked_tokens`).
  - Logout, Passwort-Reset und Admin-Invalidate-Flow aktualisieren (`routes/auth.py`, ggf. CLI).
  - Regressionstests schreiben: gesperrter Token darf keinen Zugriff mehr erhalten.

## Priorität Mittel
- [ ] CSRF für Cookie-Flows aktivieren
  - `JWT_COOKIE_CSRF_PROTECT` in der App-Config auf `true` umstellen und neue Secrets dokumentieren.
  - Frontend (`health_app/static/js/app.js`) erweitern, damit CSRF-Token automatisch gesetzt/übertragen werden.
  - Login/Refresh-Tests ergänzen, die fehlende oder falsche Tokens ablehnen.
- [ ] Automatisches Dependency-Auditing
  - Security-Scanner (z. B. Safety, pip-audit) in `requirements-dev.txt` eintragen und in CI verankern.
  - Wöchentliche Pipeline (`docs/security.md`) beschreiben und verantwortliche Rolle benennen.
  - Kritische Findings triagieren und in Backlog übernehmen.
- [ ] Rate-Limits für Passwort-Reset härten
  - Eigenes Rate-Limit-Bucket für `/auth/request-reset` definieren und in `utils/rate_limit.py` konfigurieren.
  - Audit-Logging erweitern, um Limit-Hits festzuhalten.
  - Tests aufsetzen: legitime User bleiben möglich, automatisierte Bruteforce blockiert.

## Priorität Niedrig
- [ ] Security-Guidelines dokumentieren
  - Neues Dokument `docs/security.md` mit CSP-Flow, Nonce-Generator, TLS-/Proxy-Empfehlungen und Incident-Response-Grundlagen.
  - Abschnitt "Pflicht-Checks vor Release" hinzufügen (Header-Tests, Dependency-Scan, Log-Review).
- [ ] Permissions-Policy erweitern
  - Review offener Browser-APIs (z. B. `fullscreen`, `accelerometer`, `clipboard-read`) und Policy in `health_app/__init__.py` tighten.
  - Kompatibilität in QA durchklicken (Dashboard, Chat, Exporte).
- [ ] Admin-Audit-Exports absichern
  - Optionale IP- bzw. Netzwerk-Restriktion in `services/audit_exporter.py` evaluieren.
  - MFA-Prompt für Admin-Export-Flows designen (UX + API).
  - Dokumentation (`docs/api.md`) anpassen und Support-Team schulen.
