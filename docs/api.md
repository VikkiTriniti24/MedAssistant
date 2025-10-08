# MedAssistant API Reference

Base URL: `https://<host>` (development default `http://127.0.0.1:5000`). All endpoints expect and return JSON unless noted.

Authentication uses JWT Bearer tokens obtained from `/auth/login`.

## Auth

### POST /auth/register
**Request**
```json
{
  "email": "user@example.com",
  "password": "StrongPass123"
}
```
- Password must be ≥8 characters and include letters and digits.

**Response 200**
```json
{ "access_token": "<jwt>" }
```

### POST /auth/login
Same payload as register. Returns `{ "access_token": "..." }` on success.

### GET /auth/me *(JWT required)*
Returns `{ "user_id": "<id>" }`.

### POST /auth/reset/request
Request body:
```json
{ "email": "user@example.com" }
```
Always returns 200 with `{ "msg": "If the account exists..." }` and, in development, a `reset_token` field (useful for integration tests).

### POST /auth/reset/confirm
```json
{ "token": "<reset_token>", "password": "NewPass123" }
```
Validates the token, updates the password, and responds `{ "msg": "password updated" }`.

### POST /auth/verify/request *(JWT required)*
Sends a verification email and returns `{ "msg": "verification email sent" }`. For development a `token` field is also returned.

### POST /auth/verify/confirm
```json
{ "token": "<verification_token>" }
```
Marks the user's email as verified.

### DELETE /auth/account *(JWT required)*
Request body:
```json
{ "password": "CurrentPass123", "hard_delete": false }
```
Soft-deactivates the account (`hard_delete=true` permanently removes it). Returns `{ "msg": "account deactivated" }`.

### POST /auth/reactivate
```json
{ "email": "user@example.com", "password": "CurrentPass123" }
```
Reactivates a previously deactivated account and returns a new access token.

## Health Check *(JWT required)*
### POST /health-check/
**Request**
```json
{
  "symptoms": "persistent cough, mild fever",
  "age": 28,
  "sex": "female",
  "duration": "3 days",
  "onset": "gradual",
  "vitals": { "temp_c": 38.0, "hr": 95 },
  "medications": ["ibuprofen"],
  "conditions": ["asthma"],
  "allergies": ["penicillin"],
  "pregnant": false
}
```

**Response 200**
```json
{
  "success": true,
  "data": {
    "summary": {
      "risk_level": "medium",
      "urgency": "see-doctor",
      "severity": {
        "score": 52,
        "level": "moderate",
        "factors": ["AI risk level: medium"]
      },
      "notes": ["Rest", "Hydrate"]
    },
    "diagnoses": [
      {"condition": "Mock Condition", "probability": 0.5, "triage": "medium"}
    ],
    "follow_up": {
      "self_care_advice": ["Rest", "Hydrate"],
      "when_to_seek_help": []
    },
    "ai_mode": "stub"
  },
  "errors": []
}
```

## Drug Check *(JWT required)*
### POST /drug-check/
**Request**
```json
{
  "drugs": [
    {"name": "ibuprofen", "dose": "400 mg", "freq_per_day": 3},
    {"name": "warfarin", "dose": "5 mg", "freq_per_day": 1}
  ],
  "conditions": ["hypertension"],
  "allergies": ["penicillin"],
  "pregnant": false
}
```

**Response 200**
```json
{
  "success": true,
  "data": {
    "summary": {
      "safe_to_proceed": false,
      "major_issue_count": 1,
      "moderate_issue_count": 0,
      "total_issues": 2,
      "notes": ["Issues found — review details below."]
    },
    "interactions": [
      {"drug1": "Ibuprofen", "drug2": "Warfarin", "severity": "major", "description": "..."}
    ],
    "overdose_alerts": [],
    "contraindications": [],
    "allergy_conflicts": [],
    "ai_analysis": {
      "mode": "stub",
      "interactions": [],
      "overdose_alerts": [],
      "contraindications": []
    }
  },
  "errors": []
}
```

## Chat *(JWT required)*
### POST /chat/
Supports three modes via payload:

1. **Symptom analysis** – send `{ "symptoms": "..." }` and optional demographics. Returns triage JSON identical to `/health-check/` stub.
2. **Conversational chat** – send `{ "messages": [{"role": "user", "content": "..."}] }`; returns `{ "kind": "message", "message": "...", "session_id": <int> }`.
3. **Health question** – send `{ "question": "...", "context": "optional" }`; returns `{ "kind": "answer", "answer": "...", "sources": [...] }`.

### GET /chat/export
Download the latest or specific chat transcript. Query parameters:
- `session_id` – optional, defaults to the most recent session
- `format` – `json` or `txt` (default `json`)
- `anonymize=true` – removes timestamps and replaces the numeric session id with a hashed identifier

### GET /chat/history
Returns latest chat sessions and messages.

### POST /chat/new-session
Creates an empty chat session.

### GET /chat/suggestions
Returns preset question categories.

## Profile *(JWT required)*
### GET /profile/
Returns user info, profile demographics, allergies, conditions, medications, and recent health history (including severity + risk evaluations).

### PUT /profile/
Update profile demographics.
```json
{ "age": 30, "sex": "female" }
```

### GET /profile/preferences/
Returns saved notification/language preferences.

### PUT /profile/preferences/
```json
{
  "language": "de",
  "notify_email": false,
  "notify_push": true,
  "notify_sms": false
}
```
Language values: `en`, `de`, `es`, `fr`, `it`. Notification fields must be boolean.

### POST /profile/allergies/
Add allergy: `{ "name": "penicillin" }`

### DELETE /profile/allergies/<id>/
Remove allergy entry.

Similar POST/DELETE endpoints exist for `/conditions/` and `/medications/` (see code for payloads including dosage and dates).

### GET /profile/reminders/
Returns `reminders` array with each medication’s reminder payload, including `next_reminder_at`, channel toggles, and the original schedule windows.

### GET /profile/export/
Exports a JSON snapshot covering user metadata, allergies, conditions, medications (including reminder payloads), and the most recent health history entries. Optional query parameter `anonymize=true` masks personally identifiable fields (user email, emergency contacts, family member names) and sets `"anonymized": true` in the response.

### GET /profile/emergency-contacts/
Lists stored emergency contacts ordered with the primary contact first.

### POST /profile/emergency-contacts/
Create a contact. At minimum `name` and one of `phone`/`email` are required. Passing `is_primary=true` demotes other contacts automatically.

### PUT /profile/emergency-contacts/<id>/
Update contact details or primary flag.

### DELETE /profile/emergency-contacts/<id>/
Remove a stored emergency contact.

### GET /profile/family-members/
Returns family members linked to the profile.

### POST /profile/family-members/
Create a family member. Requires `name` and `relationship`; accepts optional `birthdate` (ISO `YYYY-MM-DD`), `notes`, and `share_preferences` flag.

### PUT /profile/family-members/<id>/
Update an existing family member record.

### DELETE /profile/family-members/<id>/
Remove a family member from the profile.

## System & Utility
- `GET /healthz` – health check (no auth).
- `GET /` – dashboard HTML (requires JWT in client storage).

## Rate Limiting & Audit
- Rate limiting applied automatically; 429 response includes `{ "msg": "too many requests", "retry_after": seconds }`.
- Audit logs capture every request server-side; no client interaction needed.

## Support

### GET /support/audit-export *(JWT admin required)*
- Returns audit log records for support investigations.
- Query parameters:
  - `format` (`json`|`csv`, default `json`)
  - `start` / `end` (ISO-8601 timestamps) to bound the export window
  - `user_id` (integer) to filter by user
  - `pseudonymize` (`true`/`false`, default `false`) to hash user identifiers and IP addresses
- Example: `/support/audit-export?format=csv&start=2025-10-01&end=2025-10-07&pseudonymize=true`
- JSON response
```json
{
  "count": 12,
  "items": [
    {
      "id": 42,
      "user": "user-0fbc7a4d2e31",
      "method": "GET",
      "path": "/profile/export/",
      "status_code": 200,
      "duration_ms": 18.4,
      "created_at": "2025-10-07T08:15:23.120000",
      "remote_addr": "ip-1a2b3c4d5e6f",
      "user_agent": "ua-7f2e9c1d0b4a"
    }
  ]
}
```

## Error Format
Errors use HTTP status codes with JSON bodies:
```json
{
  "success": false,
  "errors": ["descriptive message"]
}
```

## CLI Utilities
Run with the app virtualenv activated:
- `flask --app health_app db migrate -m "msg"`
- `flask --app health_app db upgrade`
- `flask --app health_app backup-db [--dest=DIR]`
- `flask --app health_app prune-audit-logs [--days=N]`
