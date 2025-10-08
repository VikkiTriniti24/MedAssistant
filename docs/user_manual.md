# MedAssistant Benutzerhandbuch

Dieses Handbuch beschreibt die wichtigsten Schritte, um MedAssistant zu nutzen. Screenshots sind optional – hier konzentrieren wir uns auf Abläufe und Tipps.

## 1. Anmeldung & Registrierung
1. Öffne `https://<dein-host>/` (Entwicklung: `http://127.0.0.1:5000`).
2. Wähle „Registrieren“, gib E-Mail und sicheres Passwort ein (mind. 8 Zeichen, Buchstaben + Zahlen).
3. Nach erfolgreicher Registrierung meldest du dich automatisch an. Bestehende Nutzer verwenden die Login-Seite.
4. Nach der Registrierung erhältst du eine Verifizierungs-E-Mail. Verwende den Link oder den Token, um deine Adresse zu bestätigen. Solange sie unbestätigt ist, zeigt das Dashboard einen Hinweis an.
5. Passwort vergessen? Über den Link „Passwort zurücksetzen“ (oder über die API-Endpunkte `/auth/reset/request` & `/auth/reset/confirm`) kannst du ein neues Passwort setzen.
6. Konto deaktivieren/löschen: Im Profilbereich kannst du über „Konto deaktivieren“ dein Konto stilllegen (erneute Aktivierung mit E-Mail + Passwort). Mit „Konto löschen“ werden alle Daten entfernt.
7. Einstellungen: Unter „Einstellungen“ oder `/profile/preferences/` lassen sich Sprache und Benachrichtigungen (E-Mail, Push, SMS) steuern.

> Hinweis: Für produktive Umgebungen empfiehlt es sich, die Zugangsdaten über E-Mail-Bestätigung oder Admin-Freigabe zu verwalten (Feature noch offen).

## 2. Dashboard Überblick
Nach dem Login siehst du die Startseite mit Bereichen für Chat, Gesundheits-Checks und Medikamentenprüfung.
- **Diagnose-Assistent (Chat):** Interaktive Gesundheitsfragen oder allgemeine Ratschläge.
- **Letzte Gesundheits-Checks:** Übersicht vergangener Symptomeinschätzungen.
- **Symptom Checker:** Formular zur Einschätzung aktueller Beschwerden.
- **Drug Interactions:** Prüft Medikamente auf Wechselwirkungen.

## 3. Symptom Checker
1. Navigiere zum Abschnitt „Symptom Checker“.
2. Gib deine Symptome ein (z. B. „fieber 38.1, Halsschmerzen“).
3. Optional: Angaben zu Verlauf, Vitalwerten, Vorerkrankungen.
4. Klicke „Check starten“. Ergebnis enthält Risiko, Empfehlungen und eine Liste möglicher Diagnosen.

## 4. Chat-Assistent
### Schnellstart
1. Im Chat-Bereich eine Frage eingeben (z. B. „Ich fühle mich müde, was kann helfen?“).
2. Auf „Senden“ klicken – die Antwort erscheint im Log.
3. Für Folgefragen einfach weiter tippen; das System merkt sich die Unterhaltung innerhalb einer Sitzung.

### Erweiterte Funktionen
- **Symptomanalyse**: Über das Chat-Endpunkt kann auch `symptoms` gesendet werden (API/Entwickler-Feature).
- **Gesundheitsfragen (FAQ-Stil)**: Nutze „Gesundheitsfrage“ im Menü oder das entsprechende Formular.
- **Chat-Historie**: Unter „History“ (oder API `/chat/history`) lassen sich vorherige Sitzungen einsehen.
- **Neue Sitzung**: Falls du einen „frischen“ Kontext brauchst, klicke „Neue Session“.

## 5. Medikamentenprüfung
1. Abschnitt „Drug Interactions“ öffnen.
2. Medikamente mit Dosierung hinzufügen (z. B. „Ibuprofen 400 mg“).
3. Optional: Allergien oder Vorerkrankungen ergänzen.
4. Auf „Prüfen“ klicken. Das Ergebnis zeigt bekannte Interaktionen, Überdosierungen und AI-Hinweise.

## 6. Profilverwaltung
- **Profil anzeigen**: Menüpunkt „Profil“ (oder API `/profile/`).
- **Daten aktualisieren**: Alter, Geschlecht per Formular ändern.
- **Allergien/Vorerkrankungen**: Hinzufügen oder entfernen über entsprechende Buttons.
- **Medikamentenliste**: Übersicht aktueller Medikamente inkl. Dosierung und Zeitraum.
- **Gesundheitshistorie**: Die letzten Symptomeinträge mit Risiko- und Schweregrad.

## 7. Sicherheit & Sitzungsverwaltung
- Session basiert auf JWT; nach Ablauf (Standard 30 Minuten) erneute Anmeldung erforderlich.
- Rate Limiting schützt die API – bei zu vielen Anfragen tritt **429 Too Many Requests** auf (kurz warten).

## 8. Backups & Support (Admin-Hinweis)
- SQLite-Backups via CLI: `flask --app health_app backup-db`.
- Audit-Logs können mit `flask --app health_app prune-audit-logs --days=90` bereinigt werden.
- Für Supportanfragen findest du unter **Datenexporte** (Dashboard) Direkt-Downloads für dein letztes Chat-Protokoll (Detail/Text). Admins erhalten zusätzlich einen Audit-Log-Export; ein optionaler Anonymisierungs-Schalter blendet personenbezogene Angaben aus.

## 9. Best Practices für Nutzer
- Symptome möglichst detailliert und sachlich beschreiben.
- AI-Antworten sind informativ, ersetzen keinen Arztbesuch. Bei akuten Beschwerden Notruf wählen.
- Medikamente nur nach ärztlicher Rücksprache ändern.

## 10. Bekannte Einschränkungen
- Mehrsprachigkeit und erweiterte Kontextfunktionen noch in Planung.
- Einige Sicherheitsfeatures (2FA, OAuth, etc.) stehen auf der Roadmap.
- Mobile UI ist noch nicht vollständig optimiert.

## 11. Hilfe & Feedback
- Bug melden oder Feedback geben: Kontakt zum Projektteam oder GitHub-Issue.
- Änderungswünsche können über die To-do-Liste priorisiert werden.
