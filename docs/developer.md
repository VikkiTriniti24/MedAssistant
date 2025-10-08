# MedAssistant Developer Notes

## Security Controls

### Rate Limiting
- Implemented persistent rate limiting backed by the `rate_limit_hits` table.
- Limits are configurable via environment variables (`RATE_LIMIT_*`) with role-based multipliers.
- Sensitive routes (`/auth/*`, `/health-check/`, `/drug-check/`, `/chat/`) automatically enforce limits via a shared helper.
- Disable globally with `RATE_LIMITING_DISABLED=true` for local debugging.

### Audit Logging
- Every API request (excluding static assets and `/healthz`) writes an entry to the `audit_logs` table.
- Captures user ID (when available), method, path, status code, client IP, user agent, and latency.
- Configure behaviour with:
  - `AUDIT_LOG_ENABLED` (default `true`)
  - `AUDIT_LOG_EXCLUDE_PREFIXES` (comma-separated list)
  - `AUDIT_LOG_RETENTION_DAYS` (default `90`)
- Rotate logs with `flask --app health_app prune-audit-logs [--days=N]`.
- Export logs for support via `flask --app health_app export-audit-logs` (CSV/JSON, optional pseudonymisation) or the dashboard **Data Exports** card (admin only for audit CSV).

### Database Backups
- Use the Flask CLI command `flask --app health_app backup-db` to create timestamped SQLite copies.
- Optional `--dest` flag chooses an output directory (defaults to `instance/backups`).
- Command is SQLite-only; it emits a helpful message if another backend is in use.

### Cookie & Header Hardening
- Secure, HTTP-only cookies with `SameSite=Lax` defaults (configurable via env vars or `instance/config.py`).
- Global security headers applied to every response (HSTS, CSP, referrer policy, etc.).
- Max request body size defaults to 1 MB (`MAX_CONTENT_LENGTH`).

### Email Delivery
- SMTP settings (optional) drive password reset emails: configure `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, and `MAIL_DEFAULT_SENDER`.
- Reset links can embed `PASSWORD_RESET_URL`; otherwise the email body includes the token.
- Email verification uses the same transport, leveraging `EMAIL_VERIFICATION_URL` and `EMAIL_VERIFICATION_TOKEN_MINUTES` configs.

### Session Management
- Access/refresh lifetimes configurable via `JWT_ACCESS_TOKEN_EXPIRES` and `JWT_REFRESH_TOKEN_EXPIRES` (seconds).
- Refresh tokens are issued as HTTP-only cookies; `/auth/refresh` exchanges them for new access tokens.
- Deactivation or logout endpoints clear cookies to prevent reuse.

### User Preferences
- Stored in `user_preferences` with defaults on first access.
- Allowed languages: `en`, `de`, `es`, `fr`, `it` (configurable by editing `_ALLOWED_LANGUAGES`).
- Manage via `/profile/preferences/` (GET/PUT).
- The selected language now drives AI fallback wording, transactional emails, and the web UI via `static/js/i18n.js`.

### Support & Operations
- Reminder delivery can be triggered manually with `flask --app health_app dispatch-reminders [--grace-minutes=5]`.
- Chat history retention is handled by `flask --app health_app prune-chat-history [--days=N]` (defaults to `CHAT_HISTORY_RETENTION_DAYS`).
- The dashboard **Data Exports** card allows authenticated users to download profile/last chat artifacts; audit CSV is limited to admins.
- Runtime counters (AI fallbacks, rate-limit hits) are exposed at `/metrics` in Prometheus text format for scraping.

## Testing
- `pytest` runs the fast subset of tests (skipping those marked `@pytest.mark.slow`).
- Run the slower integration flows with `pytest -m slow` or run everything via `pytest -m "slow or not slow"`.
- Use `pytest tests/test_rate_limiting.py` or similar for focused runs.
- API reference: see `docs/api.md` for request/response samples and CLI helpers.
- User manual: see `docs/user_manual.md` for step-by-step usage guidance.

## Database Models
- New tables: `rate_limit_hits` and `audit_logs` support the security features above.
- Tests bootstrap SQLite schemas automatically; run `flask db migrate` after deploying to generate migrations.
- Use Flask-Migrate for schema changes:
  1. `flask --app health_app db migrate -m "<message>"`
  2. `flask --app health_app db upgrade`
  3. Commit the generated file(s) under `migrations/versions/`.

## Configuration Tips
- Place local overrides in `instance/config.py` (already honors the new settings).
- For staging/production, set env vars in `.env` or your deployment platform.

## Sample Drug Data
- Populate the local database with realistic drug metadata by running `python seed_drug_data.py` from the project root.
- The seeder inserts brand synonyms, side-effect hints, and representative interaction pairs for common medications (ibuprofen, aspirin, warfarin, etc.).
- The script is idempotent: re-running it updates metadata (brand synonyms, side effects) without duplicating rows.
- Tests `tests/test_seed_data.py` validate the seeder; keep them green when modifying the dataset.
- Reminders derive `next_reminder_at` automatically from medication schedules, so seeded data is ready for front-end notification demos.
- Health check responses now include `body_systems` and `differential_diagnosis` blocks derived from heuristics plus AI output—ensure clients handle these arrays when visualising triage results.
- Emergency contacts are stored via `/profile/emergency-contacts/` (CRUD). Marking a contact `is_primary` automatically clears previous primaries. Health checks return the top emergency contact in `emergency_contact` for escalation flows.
- Family members can be managed via `/profile/family-members/` (CRUD). The primary profile summary and exports now include a `family_members` array and count—useful for future shared-access workflows.
