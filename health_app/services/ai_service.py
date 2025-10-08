# health_app/services/ai_service.py
import os
import json
import re
import time
import logging
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from ..utils.i18n import normalize_language
from ..metrics import track_ai_fallback

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
_ALLOW_FALLBACK = os.getenv("AI_ALLOW_FALLBACK", "1").strip().lower() not in {"0", "false", "no"}

_FALLBACK_LANGUAGE = normalize_language(os.getenv("AI_FALLBACK_LANGUAGE", "de"))
_FALLBACK_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "de": {
        "prefix": "MedAssistant-Notfallantwort:",
        "header": "Ich konnte den Live-Gesundheitsassistenten{context} nicht erreichen.",
        "lines": [
            "Diese Hinweise ersetzen keine ärztliche Beratung.",
            "Rufen Sie bei Brustschmerzen, Atemnot, Verwirrtheit oder starkem Unwohlsein den Notruf.",
            "Kontaktieren Sie Ihre Hausärztin/Ihren Hausarzt oder eine medizinische Hotline, wenn Beschwerden anhalten oder sich verschlimmern.",
            "Bitte beobachten Sie Ihre Symptome, ruhen Sie sich aus und trinken Sie ausreichend Flüssigkeit, bis Sie professionelle Hilfe erhalten.",
        ],
    },
    "en": {
        "prefix": "MedAssistant fallback response:",
        "header": "I could not reach the live medical assistant{context}.",
        "lines": [
            "This information is general and does not replace professional medical advice.",
            "Seek urgent care or call emergency services if you have chest pain, trouble breathing, confusion, or severe symptoms.",
            "For ongoing or worsening issues, contact your healthcare provider or an urgent care clinic.",
            "Monitor your symptoms, stay hydrated, and rest while you arrange professional follow-up.",
        ],
    },
}

_fallback_template = _FALLBACK_TEMPLATES.get(_FALLBACK_LANGUAGE, _FALLBACK_TEMPLATES["en"])
_FALLBACK_REASON_MAP = {
    "de": {
        "stub mode active": "Stub-Modus aktiv",
        "temporary service interruption": "vorübergehende Dienstunterbrechung",
    },
    "en": {
        "stub mode active": "stub mode active",
        "temporary service interruption": "temporary service interruption",
    },
}
FALLBACK_PREFIX = os.getenv("AI_FALLBACK_PREFIX", _fallback_template["prefix"])
_FALLBACK_LINES_RAW = os.getenv("AI_FALLBACK_LINES")
if _FALLBACK_LINES_RAW:
    _FALLBACK_LINES = [
        line.strip()
        for line in _FALLBACK_LINES_RAW.split("|")
        if line.strip()
    ]
else:
    _FALLBACK_LINES = list(_fallback_template["lines"])

FALLBACK_PREFIXES = {
    FALLBACK_PREFIX,
    *[tmpl["prefix"] for tmpl in _FALLBACK_TEMPLATES.values()],
}

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

def _safe_fallback_text(
    user_text: str,
    *,
    reason: str,
    language: Optional[str] = None,
) -> str:
    """Return a user-facing fallback with safety guidance and clear context."""
    lang = normalize_language(language or _FALLBACK_LANGUAGE)
    template = _FALLBACK_TEMPLATES.get(lang, _FALLBACK_TEMPLATES["en"])

    snippet = (user_text or "").strip()
    if len(snippet) > 160:
        snippet = snippet[:157].rstrip() + "..."

    if snippet:
        if lang == "de":
            context_line = f" für \"{snippet}\""
        else:
            context_line = f" for \"{snippet}\""
    else:
        context_line = ""

    local_reason = reason
    translated_reason = _FALLBACK_REASON_MAP.get(lang, {}).get(reason)
    if translated_reason:
        local_reason = translated_reason

    header_template = template.get(
        "header",
        "I could not reach the live medical assistant{context}.",
    )
    header_body = header_template.format(context=context_line)
    prefix = FALLBACK_PREFIX if lang == _FALLBACK_LANGUAGE else template.get("prefix", FALLBACK_PREFIX)
    header = f"{prefix} {local_reason}. {header_body}".strip()

    if lang == _FALLBACK_LANGUAGE and _FALLBACK_LINES_RAW:
        lines = _FALLBACK_LINES
    else:
        lines = template.get("lines", _FALLBACK_TEMPLATES["en"]["lines"])

    body = "\n" + "\n".join(f"- {line}" for line in lines)
    reply = header + body
    track_ai_fallback(lang, reason)
    log.debug("Safe fallback response erzeugt: %s", reply[:180])
    return reply


def _stub_text(messages: List[Dict[str, Any]], *, language: Optional[str] = None) -> str:
    """Safe textual fallback in environments where the live model is unavailable."""
    return _safe_fallback_text(
        _last_user_text(messages),
        reason="stub mode active",
        language=language,
    )

def _stub_json() -> Dict[str, Any]:
    """Deterministic JSON stub with more realistic medical responses."""
    payload = {
        "diagnoses": [
            {"condition": "Common cold (Viral upper respiratory infection)", "probability": 0.75, "triage": "low"},
            {"condition": "Seasonal allergies", "probability": 0.15, "triage": "low"},
            {"condition": "Mild dehydration", "probability": 0.10, "triage": "low"}
        ],
        "risk_evaluation": {"risk_level": "low", "urgency": "self-care"},
        "recommendations": [
            "Rest and stay hydrated",
            "Monitor symptoms for 3-5 days",
            "Seek medical attention if symptoms worsen"
        ],
        "differential_diagnosis": [
            {
                "condition": "Influenza",
                "likelihood": 0.4,
                "rationale": "Fever and upper respiratory symptoms overlap with influenza presentation"
            },
            {
                "condition": "Bacterial sinusitis",
                "likelihood": 0.2,
                "rationale": "Persistent congestion and headaches may indicate sinus involvement"
            }
        ]
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
    language: Optional[str] = None,
) -> str:
    """
    Calls OpenAI Chat mit Retries.
    Dev/Testing liefert Stub; im Fehlerfall gibt es einen Fail-Safe, der
    einen sicheren Hinweistext zurückgibt, damit keine 502 im Dev entstehen.
    """
    if _STUB:
        log.info("Stub-Mode aktiv – überspringe echten API-Call")
        return _stub_text(messages, language=language)

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
    log.error(msg)

    if _ALLOW_FALLBACK:
        log.warning("Returning safe fallback after OpenAI failure")
        return _safe_fallback_text(
            _last_user_text(messages),
            reason="temporary service interruption",
            language=language,
        )

    raise AIServiceError(msg)

# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def chat_raw(
    messages: List[Dict[str, Any]],
    *,
    timeout: int = 30,
    language: Optional[str] = None,
) -> str:
    """
    Pass-through chat; returns raw text (oder Stub in Dev/Testing).
    'timeout' wird nur im Legacy SDK genutzt, beim neuen SDK ignoriert.
    """
    lang = normalize_language(language) if language else None
    result = _call_chat(messages, timeout=timeout, language=lang)
    if any(result.startswith(prefix) for prefix in FALLBACK_PREFIXES) and not _ALLOW_FALLBACK:
        raise AIServiceError("Fallback disabled but stub response returned")
    return result

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
            if _ALLOW_FALLBACK:
                log.warning("Returning stub JSON after parsing failure")
                return _stub_json()
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
4. Suggest up to 3 differential diagnoses (distinct from the main list) with a likelihood score and brief rationale.

Respond in JSON:
{{
  "diagnoses": [
    {{"condition": "...", "probability": 0.00, "triage": "..."}}
  ],
  "risk_evaluation": {{"risk_level": "...", "urgency": "..."}}
  "differential_diagnosis": [
    {{"condition": "...", "likelihood": 0.0, "rationale": "..."}}
  ]
}}
""".strip()

def build_drug_prompt(
    profile,
    allergies,
    conditions,
    drug_context_list,
    *,
    pregnant: Optional[bool] = None,
) -> str:
    age = getattr(profile, "age", None)
    age_text = age if age not in {None, ""} else "unknown"
    sex_value = getattr(profile, "sex", None)
    sex_text = sex_value if sex_value else "unknown"
    pregnancy_text = (
        "yes" if pregnant is True else "no" if pregnant is False else "unknown"
    )

    return f"""
You are a pharmacology expert AI.
Patient profile:
- Age: {age_text}
- Sex: {sex_text}
- Pregnant: {pregnancy_text}
- Allergies: {', '.join(allergies) if allergies else 'none'}
- Pre-existing conditions: {', '.join(conditions) if conditions else 'none'}

Current medications:
{json.dumps(drug_context_list, ensure_ascii=False)}

For each medication:
1. Check if the prescribed dosage exceeds the max_daily_dose. If so, flag an overdose risk.
2. Identify severe or moderate drug-drug interactions among the list.
3. Identify any contraindications based on the patient’s conditions and allergies.
4. Recommend appropriate dosing guidance (typical adult dose, max daily dose) and flag if the reported dose differs meaningfully.
5. Summarize notable side effects the patient should monitor, especially severe ones, with brief recommendations.

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
  ],
  "dosage_guidance": [
    {{"drug": "...", "recommended_dose": "...", "note": "..."}}
  ],
  "side_effects": [
    {{"drug": "...", "effect": "...", "severity": "...", "recommendation": "..."}}
  ]
}}
""".strip()
