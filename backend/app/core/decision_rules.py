
from typing import Dict, Any

def build_reasoning(parsed: Dict[str, Any]) -> Dict[str, Any]:
    missing = []
    if not parsed.get("location"):
        missing.append("exact location/address")
    if not parsed.get("time_24h"):
        missing.append("time of incident")

    constraints = []
    if parsed.get("recurrence"):
        constraints.append("recurring issue")

    return {
        "intent": f"Handle a {parsed.get('category','unknown')} complaint",
        "constraints": constraints,
        "missing_info": missing
    }

def build_dispatch_decision(parsed: Dict[str, Any], draft_decision: Dict[str, Any]) -> Dict[str, Any]:
    # Add a justification based on signals (simple, deterministic)
    justification_parts = []
    if parsed.get("time_24h"):
        justification_parts.append(f"time={parsed['time_24h']}")
    if parsed.get("recurrence"):
        justification_parts.append(f"recurrence={parsed['recurrence']}")
    if parsed.get("location"):
        justification_parts.append(f"location={parsed['location']}")
    justification_parts.append(f"category={parsed.get('category','unknown')}")

    return {
        "agency": draft_decision["agency_guess"],
        "urgency": draft_decision["urgency_guess"],
        "action": draft_decision["action_guess"],
        "justification": ", ".join(justification_parts),
        "confidence": draft_decision["confidence_stub"]
    }

def format_user_response(decision: Dict[str, Any]) -> str:
    return (
        f"Decision:\n"
        f"- Agency: {decision['agency']}\n"
        f"- Urgency: {decision['urgency']}\n"
        f"- Action: {decision['action']}\n"
        f"- Justification: {decision['justification']}\n"
        f"- Confidence: {decision['confidence']}\n"
    )
