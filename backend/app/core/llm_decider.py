import json
import os
from typing import Any, Dict, List, Optional

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


def _openai_client():
    api_key = _get_env("LLMOD_API_KEY")
    base_url = _get_env("LLMOD_BASE_URL")
    model = _get_env("CHAT_MODEL")
    if not (api_key and base_url and model):
        raise ValueError("LLM not configured (missing LLMOD_API_KEY / LLMOD_BASE_URL / CHAT_MODEL)")

    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=base_url), model


def llm_plan_next_action(state_snapshot: Dict[str, Any], allowed_actions: List[str]) -> Dict[str, Any]:
    client, model = _openai_client()

    system = (
        "You are the planner for a municipal 311 ReAct agent. "
        "Choose the single best next action based on current state. "
        "Return ONLY valid JSON with keys: thought, action, why, need_more_information. "
        "Allowed actions are provided by the user. "
        "Use RETRIEVE_SIMILAR_CASES when historical evidence would reduce routing uncertainty. "
        "Use RUN_LLM_DISAMBIGUATION only when ambiguity remains after current evidence. "
        "Use FINALIZE_DECISION if enough information already exists. "
        "Use ASK_FOR_MISSING_INFO if critical dispatch fields are missing. "
        "Be concise and operational."
    )

    user_payload = {
        "allowed_actions": allowed_actions,
        "state": state_snapshot,
        "task": "Choose the next best action for the agent.",
    }

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=True)},
        ],
    )

    text = resp.choices[0].message.content or "{}"
    try:
        out = json.loads(text)
    except Exception as exc:
        raise ValueError(f"Planner returned non-JSON: {text[:200]}") from exc

    action = str(out.get("action") or "").strip()
    if action not in allowed_actions:
        raise ValueError(f"Planner returned unsupported action: {action}")

    return {
        "thought": str(out.get("thought") or "Planner selected the next action from current state.").strip(),
        "action": action,
        "why": str(out.get("why") or "").strip(),
        "need_more_information": bool(out.get("need_more_information", False)),
    }

def llm_decide(parsed: Dict[str, Any], evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Returns a strict decision dict:
    {agency, urgency, action, justification, confidence}
    """
    client, model = _openai_client()

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
        "confidence must be a number between 0 and 1. "
        "IMPORTANT: If the complaint is vague, unclear, speculative, or missing key info "
        "(like category or location), set confidence <= 0.6 and include FOLLOW-UP NEEDED "
        "questions in the action. "
        "Urgency must reflect immediate physical hazard only. "
        "If the complaint is vague or lacks concrete threat details, urgency MUST be 'low'. "
        "Do NOT set urgency to 'medium' or 'high' unless there is specific described harm, "
        "active risk, or concrete hazard. "
        "Only use 'high' for explicit immediate danger such as fire, gas leak, violence, "
        "severe injury, or life-threatening conditions."
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

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=True)},
        ],
    )

    text = resp.choices[0].message.content or "{}"

    # Parse JSON safely
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
