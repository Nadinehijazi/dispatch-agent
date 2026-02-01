from typing import Any, Dict


def format_user_response(decision: Dict[str, Any]) -> str:
    return (
        "Decision:\n"
        f"- Agency: {decision['agency']}\n"
        f"- Urgency: {decision['urgency']}\n"
        f"- Action: {decision['action']}\n"
        f"- Justification: {decision['justification']}\n"
        f"- Confidence: {decision['confidence']}\n"
    )
