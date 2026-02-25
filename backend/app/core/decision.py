from typing import Any, Dict


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
        "intent": f"Handle a {parsed.get('category', 'unknown')} complaint",
        "constraints": constraints,
        "missing_info": missing,
    }


def build_dispatch_decision(
    parsed: Dict[str, Any],
    draft_decision: Dict[str, Any],
    evidence: Dict[str, Any] | None = None,
    agency_vote_ratio_threshold: float = 0.70,
    score_threshold: float = 0.62,
) -> Dict[str, Any]:
    justification_parts = []
    if parsed.get("time_24h"):
        justification_parts.append(f"time={parsed['time_24h']}")
    if parsed.get("recurrence"):
        justification_parts.append(f"recurrence={parsed['recurrence']}")
    if parsed.get("location"):
        justification_parts.append(f"location={parsed['location']}")
    justification_parts.append(f"category={parsed.get('category', 'unknown')}")

    confidence = float(draft_decision.get("confidence_stub", 0.5))

    # Penalize missing critical fields (makes gating more meaningful)
    if parsed.get("category") in (None, "unknown"):
        confidence -= 0.15
    if not parsed.get("location"):
        confidence -= 0.10
    if not parsed.get("time_24h"):
        confidence -= 0.05
    confidence = max(0.05, confidence)

    if evidence:
        agency_counts = evidence.get("agency_counts") or {}
        total_matches = int(evidence.get("total_matches") or 0)
        top_score = evidence.get("top_score")
        top_agency = None
        top_count = 0
        if agency_counts:
            top_agency = max(agency_counts, key=agency_counts.get)
            top_count = agency_counts.get(top_agency, 0)

        vote_ratio = (top_count / total_matches) if total_matches else 0.0
        if top_agency:
            justification_parts.append(f"evidence_top_agency={top_agency}")
            justification_parts.append(f"evidence_vote_ratio={vote_ratio:.2f}")
            if top_score is not None:
                justification_parts.append(f"evidence_top_score={top_score:.2f}")

        if top_agency and top_score is not None:
            strong_evidence = vote_ratio >= agency_vote_ratio_threshold and top_score >= score_threshold
            if strong_evidence and top_agency != draft_decision.get("agency_guess"):
                # evidence-driven override
                draft_decision["agency_guess"] = top_agency
                confidence = min(0.92, max(confidence, 0.7) + 0.15)
            elif strong_evidence and top_agency == draft_decision.get("agency_guess"):
                confidence = min(0.9, confidence + 0.1)
            else:
                confidence = max(0.25, confidence - 0.05)

    return {
        "agency": draft_decision["agency_guess"],
        "urgency": draft_decision["urgency_guess"],
        "action": draft_decision["action_guess"],
        "justification": ", ".join(justification_parts),
        "confidence": round(confidence, 2),
    }
