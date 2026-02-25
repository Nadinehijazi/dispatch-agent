import os
from typing import Any, Dict, Optional

def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

def _get_env(name: str) -> Optional[str]:
    _load_dotenv()
    v = os.getenv(name)
    return v if v and str(v).strip() else None

def llm_available() -> bool:
    return bool(_get_env("LLMOD_API_KEY") and _get_env("LLMOD_BASE_URL") and _get_env("CHAT_MODEL"))

def llm_decide(parsed: Dict[str, Any], evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Returns a strict decision dict:
    {agency, urgency, action, justification, confidence}
    """
    api_key = _get_env("LLMOD_API_KEY")
    base_url = _get_env("LLMOD_BASE_URL")
    model = _get_env("CHAT_MODEL")
    if not (api_key and base_url and model):
        raise ValueError("LLM not configured (missing LLMOD_API_KEY / LLMOD_BASE_URL / CHAT_MODEL)")

    # Keep prompt SMALL to save budget
    complaint_text = (parsed.get("complaint_text") or "")[:800]
    location = parsed.get("location") or ""
    borough = parsed.get("borough") or ""
    time_24h = parsed.get("time_24h") or ""
    recurrence = parsed.get("recurrence") or ""
    category = parsed.get("category") or "unknown"

    # Summarize evidence cheaply (no huge blobs)
    ev = evidence or {}
    agency_counts = ev.get("agency_counts") or {}
    top_score = ev.get("top_score")
    total_matches = ev.get("total_matches", 0)

    system = (
        "You are a municipal 311 dispatch assistant. "
        "Return ONLY valid JSON (no markdown). "
        "JSON keys must be exactly: agency, urgency, action, justification, confidence. "
        "urgency must be one of: low, medium, high. "
        "confidence must be a number between 0 and 1."
    )

    user = {
        "complaint_text": complaint_text,
        "parsed": {
            "category": category,
            "location": location,
            "borough": borough,
            "time_24h": time_24h,
            "recurrence": recurrence,
        },
        "evidence_summary": {
            "agency_counts": agency_counts,
            "total_matches": total_matches,
            "top_score": top_score,
        },
        "task": "Decide the best agency + urgency + recommended action for dispatch.",
    }

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": str(user)},
        ],
        temperature=0.1,
    )

    text = resp.choices[0].message.content or "{}"

    # Parse JSON safely
    import json
    try:
        out = json.loads(text)
    except Exception:
        # If the model returns non-JSON, fail loudly (but caller will handle)
        raise ValueError(f"LLM returned non-JSON: {text[:200]}")

    # Minimal validation / normalization
    urgency = out.get("urgency")
    if urgency not in ("low", "medium", "high"):
        out["urgency"] = "medium"

    conf = out.get("confidence")
    try:
        conf = float(conf)
    except Exception:
        conf = 0.5
    out["confidence"] = max(0.0, min(1.0, conf))

    return {
        "agency": out.get("agency") or "UNKNOWN",
        "urgency": out.get("urgency") or "medium",
        "action": out.get("action") or "Create ticket for review",
        "justification": out.get("justification") or "LLM decision (no justification provided).",
        "confidence": round(out["confidence"], 2),
    }