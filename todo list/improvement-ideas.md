# MedAssistant · Verbesserungsvorschläge

## Priorität Hoch
- [x] `health_app/services/ai_service.py`: Fallback-Texte lokalisieren (Deutsch) und konfigurierbar machen, damit UI- und API-Ausgaben konsistent bleiben; zusätzliche Tests auf deutschsprachige Sicherheits-Hinweise ergänzen.
- [x] `health_app/static/js/app.js`: Netzwerkfehler in `apiFetch` abfangen (try/catch) und barrierefreie Fehlermeldungen anzeigen, damit Offline-/Timeout-Situationen nicht lautlos scheitern.
- [x] `health_app/routes/drug_check.py`: AI-Analyse mit echten Profilinformationen (Alter, Geschlecht, Schwangerschaft, Allergien) versorgen statt des Dummy-Profils; Prompt um diese Felder erweitern und Tests für realistische Antworten ergänzen.

## Priorität Mittel
- [x] `health_app/routes/chat.py`: Chat-Sessions aktuell auf Tageswechsel begrenzt (`created_at >= utc midnight`); auf echte 24h-Fenster umstellen, um nächtliche Gespräche nicht abrupt zu trennen.
- [x] `health_app/routes/drug_check.py`: `_fetch_drugs_map` vermeidet keine Volltabellen-Scans bei Synonymen. Synonyme in eigene Tabelle/Index auslagern oder vorberechneten Lookup-Cache nutzen, damit große Datenbestände performant bleiben.
- [x] Tests: Volle `pytest`-Suite läuft lokal >5 min (Timeout). Schwere Tests markieren (`pytest.mark.slow`) und Standardlauf verschlanken oder parallelisieren, um lokale/dev Runs praktikabler zu machen.

## Priorität Niedrig
- [x] `docs/deployment.md` & `setup_ai.py`: Dokumentation zur neuen Fallback-Logik und Live-/Stub-Umschaltung ergänzen (lokalisierte Antworten, Monitoring-Hinweise), damit Ops den Unterschied kennt.
- [x] `health_app/static/js/app.js`: Toast-Komponente für Screenreader ankündigen (z. B. `aria-live="assertive"`), damit Warnungen auch ohne visuelle Hinweise wahrgenommen werden.
