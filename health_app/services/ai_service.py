# health_app/services/ai_service.py
import os
import json
import re
import time
import logging
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Env laden
# -----------------------------------------------------------------------------
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
_ENV = (os.getenv("FLASK_ENV") or os.getenv("ENV") or "development").lower()

# Optionaler Schalter zum Erzwingen des Stub-Modus (bequem in Dev/Tests)
# .env: AI_STUB=1  (oder "true"/"yes")
_FORCE_STUB = (os.getenv("AI_STUB", "").strip().lower() in {"1", "true", "yes"})

# -----------------------------------------------------------------------------
# Stub-Mode Ermittlung
# _STUB=True => keine echten API-Calls; deterministische Platzhalter.
# -----------------------------------------------------------------------------
_STUB: bool = False
if _FORCE_STUB:
    _STUB = True
    OPENAI_API_KEY = "test"
elif not OPENAI_API_KEY:
    if _ENV in ("development", "testing", ""):
        _STUB = True
        OPENAI_API_KEY = "test"
    else:
        raise RuntimeError("Missing OPENAI_API_KEY (set it in environment or .env)")

# -----------------------------------------------------------------------------
# OpenAI SDK detection
# -----------------------------------------------------------------------------
_client = None
_NEW_SDK = False
try:
    # New SDK (openai>=1.x)
    from openai import OpenAI  # type: ignore
    _NEW_SDK = True
    if not _STUB:
        _client = OpenAI(api_key=OPENAI_API_KEY)  # create once
except Exception:  # pragma: no cover - nur wenn neues SDK fehlt
    # Legacy SDK (openai<1.x)
    import openai  # type: ignore
    _NEW_SDK = False
    if not _STUB:
        openai.api_key = OPENAI_API_KEY  # type: ignore

# Initialisierungs-Info
log.info(
    "ai_service initialisiert | env=%s stub=%s sdk=%s model=%s",
    _ENV, _STUB, "new" if _NEW_SDK else "legacy", DEFAULT_MODEL
)

# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------
class AIServiceError(Exception):
    """Raised when the upstream AI service fails after retries."""

class AIJSONError(AIServiceError):
    """Raised when JSON parsing of the AI response fails."""

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

def _strip_code_fences(s: str) -> str:
    """Extract JSON content if wrapped in triple backticks."""
    if not isinstance(s, str):
        return ""
    m = _CODE_FENCE_RE.search(s)
    return (m.group(1) if m else s).strip()

def _last_user_text(messages: List[Dict[str, Any]]) -> str:
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    return ((last_user or {}).get("content") or "").strip()

def _stub_text(messages: List[Dict[str, Any]]) -> str:
    """Deterministic stub reply for dev/testing without API key."""
    content = _last_user_text(messages)
    reply = f"[stub:{DEFAULT_MODEL}] {content}".strip() or "[stub:ok]"
    log.debug("Stub-Antwort erzeugt: %s", reply[:120])
    return reply

def _stub_json() -> Dict[str, Any]:
    """Deterministic JSON stub."""
    payload = {
        "diagnoses": [{"condition": "Example condition", "probability": 0.5, "triage": "medium"}],
        "risk_evaluation": {"risk_level": "medium", "urgency": "see-doctor"},
    }
    log.debug("Stub-JSON erzeugt: %s", payload)
    return payload

def is_stub_mode() -> bool:
    return _STUB

# -----------------------------------------------------------------------------
# Core call
# -----------------------------------------------------------------------------
def _call_chat(
    messages: List[Dict[str, Any]],
    *,
    response_format: Optional[Dict[str, str]] = None,
    timeout: int = 30,          # für Legacy SDK / Signatur
    temperature: float = 0.2,
    max_retries: int = 2,
    model: Optional[str] = None,
) -> str:
    """
    Calls OpenAI Chat mit Retries.
    Dev/Testing liefert Stub; in Dev/Testing gibt es zusätzlich einen Fail-Safe,
    der bei Fehlern '[stub-fallback:...]' zurückgibt, damit keine 502 im Dev entstehen.
    """
    if _STUB:
        log.info("Stub-Mode aktiv – überspringe echten API-Call")
        return _stub_text(messages)

    model = model or DEFAULT_MODEL
    last_exc: Optional[Exception] = None
    start_ts = time.monotonic()

    for attempt in range(max_retries + 1):
        try:
            log.debug(
                "OpenAI Call (Versuch %d/%d) | model=%s sdk=%s",
                attempt + 1, max_retries + 1, model, "new" if _NEW_SDK else "legacy"
            )
            if _NEW_SDK:
                # Neues SDK: KEIN 'timeout' übergeben (einige Versionen akzeptieren das nicht)
                resp = _client.chat.completions.create(  # type: ignore[union-attr]
                    model=model,
                    messages=messages,
                    response_format=response_format or {"type": "text"},
                    temperature=temperature,
                )
                out = (resp.choices[0].message.content or "").strip()
                log.debug("OpenAI OK (new SDK) | len=%d", len(out))
                return out
            else:
                # Legacy SDK: 'request_timeout' ist korrekt
                resp = openai.ChatCompletion.create(  # type: ignore[name-defined]
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    request_timeout=timeout,
                )
                out = (resp.choices[0].message["content"] or "").strip()
                log.debug("OpenAI OK (legacy SDK) | len=%d", len(out))
                return out

        except Exception as exc:
            last_exc = exc
            log.warning(
                "OpenAI-Call fehlgeschlagen (Versuch %d/%d): %s",
                attempt + 1, max_retries + 1, exc
            )
            time.sleep(0.5 * (2 ** attempt))  # einfacher Backoff

    dur = time.monotonic() - start_ts
    msg = f"OpenAI chat call failed after {max_retries+1} attempts (took {dur:.2f}s): {last_exc}"
    if _ENV in ("development", "testing", ""):
        # Fail-safe in Dev/Tests: niemals 502 werfen
        log.error("%s | gebe stub-fallback zurück", msg)
        return f"[stub-fallback:{DEFAULT_MODEL}] {_last_user_text(messages)}".strip() or "[stub-fallback:ok]"

    # In Prod: Exception propagieren
    log.exception(msg)
    raise AIServiceError(msg)

# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def chat_raw(messages: List[Dict[str, Any]], *, timeout: int = 30) -> str:
    """
    Pass-through chat; returns raw text (oder Stub in Dev/Testing).
    'timeout' wird nur im Legacy SDK genutzt, beim neuen SDK ignoriert.
    """
    return _call_chat(messages, timeout=timeout)

def chat_json(prompt_text: str, *, timeout: int = 30) -> Dict[str, Any]:
    """
    Erzwingt JSON-Antwort (falls unterstützt), sonst Parsing von Text/Fenced JSON.
    In Dev/Testing: gibt deterministisches Stub-JSON zurück, wenn kein Key vorhanden ist.
    """
    if _STUB:
        log.info("Stub-Mode aktiv – liefere deterministisches JSON")
        return _stub_json()

    messages = [
        {"role": "system", "content": "You are a careful medical assistant. Reply in valid JSON only."},
        {"role": "user", "content": prompt_text},
    ]

    text = _call_chat(
        messages,
        response_format={"type": "json_object"},
        timeout=timeout,
        temperature=0.0,
    )

    try:
        return json.loads(text)
    except Exception:
        candidate = _strip_code_fences(text)
        try:
            return json.loads(candidate)
        except Exception as exc:
            log.exception("JSON-Parsing fehlgeschlagen. Rohtext-Länge=%d", len(text) if isinstance(text, str) else -1)
            raise AIJSONError(f"Failed to parse JSON response: {exc}") from exc

# -----------------------------------------------------------------------------
# Prompt builders
# -----------------------------------------------------------------------------
def build_health_prompt(profile, allergies, conditions, symptoms_text: str) -> str:
    return f"""
You are a medical diagnosis assistant.
Patient data:
- Age: {getattr(profile, 'age', 'unknown')}
- Sex: {getattr(profile, 'sex', 'unknown')}
- Allergies: {', '.join(allergies) if allergies else 'none'}
- Pre-existing conditions: {', '.join(conditions) if conditions else 'none'}

Reported symptoms:
{symptoms_text}

Tasks:
1. List the top 5 possible diagnoses, each with a probability (0.00–1.00).
2. For each diagnosis, give a triage level: low, medium or high.
3. Provide an overall risk evaluation: risk_level (low/medium/high) and urgency (self-care, see-doctor, emergency).

Respond in JSON:
{{
  "diagnoses": [
    {{"condition": "...", "probability": 0.00, "triage": "..."}}
  ],
  "risk_evaluation": {{"risk_level": "...", "urgency": "..."}}
}}
""".strip()

def build_drug_prompt(profile, allergies, conditions, drug_context_list) -> str:
    return f"""
You are a pharmacology expert AI.
Patient profile:
- Age: {getattr(profile, 'age', 'unknown')}
- Sex: {getattr(profile, 'sex', 'unknown')}
- Allergies: {', '.join(allergies) if allergies else 'none'}
- Pre-existing conditions: {', '.join(conditions) if conditions else 'none'}

Current medications:
{json.dumps(drug_context_list, ensure_ascii=False)}

For each medication:
1. Check if the prescribed dosage exceeds the max_daily_dose. If so, flag an overdose risk.
2. Identify severe or moderate drug-drug interactions among the list.
3. Identify any contraindications based on the patient’s conditions and allergies.

Respond in JSON:
{{
  "overdose_alerts": [
    {{"drug": "...", "dosage": "...", "max_daily_dose": "...", "alert": true}}
  ],
  "interactions": [
    {{"drug1": "...", "drug2": "...", "severity": "...", "description": "..."}}
  ],
  "contraindications": [
    {{"drug": "...", "condition": "...", "notes": "..."}}
  ]
}}
""".strip()

