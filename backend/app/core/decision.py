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

    if parsed.get("location") or parsed.get("location_details"):
        loc = parsed.get("location") or parsed.get("location_details")
        justification_parts.append(f"location={loc}")

    justification_parts.append(f"category={parsed.get('category', 'unknown')}")

    confidence = float(draft_decision.get("confidence_stub", 0.5))

    # ---------------------------
    # Detect vagueness
    # ---------------------------
    text = (parsed.get("complaint_text") or "").lower()

    vague_signals = [
        "weird", "strange", "not sure", "maybe",
        "something", "feels off", "smells funny",
        "i think", "might be", "kind of", "sort of"
    ]

    is_vague = any(v in text for v in vague_signals)

    # ---------------------------
    # Penalize missing fields
    # ---------------------------
    if parsed.get("category") in (None, "unknown"):
        confidence -= 0.15

    has_any_location = bool(str(parsed.get("location") or "").strip()) or bool(
        str(parsed.get("location_details") or "").strip()
    )
    if parsed.get("category") == "safety" and draft_decision.get("urgency_guess") == "high":
        confidence = max(confidence, 0.85)

    if not has_any_location:
        confidence -= 0.10

    if not parsed.get("time_24h"):
        confidence -= 0.05

    confidence = max(0.05, confidence)

    # ---------------------------
    # HARD CAP for vague complaints
    # ---------------------------
    if is_vague:
        confidence = min(confidence, 0.35)

    if not has_any_location:
        confidence = min(confidence, 0.40)

    # ---------------------------
    # RAG Evidence Handling
    # ---------------------------
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

            strong_evidence = (
                vote_ratio >= agency_vote_ratio_threshold
                and top_score >= score_threshold
            )

            # 🚨 DO NOT boost vague or unknown complaints
            if strong_evidence and not is_vague and parsed.get("category") != "unknown":

                if top_agency != draft_decision.get("agency_guess"):
                    draft_decision["agency_guess"] = top_agency
                    confidence = min(0.80, max(confidence, 0.60) + 0.10)

                else:
                    confidence = min(0.75, confidence + 0.05)

            else:
                confidence = max(0.20, confidence - 0.05)

    return {
        "agency": draft_decision["agency_guess"],
        "urgency": draft_decision["urgency_guess"],
        "action": draft_decision["action_guess"],
        "justification": ", ".join(justification_parts),
        "confidence": round(confidence, 2),
    }