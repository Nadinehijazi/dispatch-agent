from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .decision import build_dispatch_decision, build_reasoning
from .formatting import format_user_response
from .llm_decider import llm_available, llm_decide, llm_plan_next_action
from .preprocessing import (
    AGENCY_MAP,
    classify_category,
    estimate_urgency,
    extract_location,
    extract_recurrence,
    extract_time,
)
from .rag import retrieve_similar_cases, summarize_evidence


class AgentAction(str, Enum):
    PARSE_COMPLAINT = "PARSE_COMPLAINT"
    EMERGENCY_ESCALATE = "EMERGENCY_ESCALATE"
    RETRIEVE_SIMILAR_CASES = "RETRIEVE_SIMILAR_CASES"
    ASK_FOR_MISSING_INFO = "ASK_FOR_MISSING_INFO"
    RUN_LLM_DISAMBIGUATION = "RUN_LLM_DISAMBIGUATION"
    FINALIZE_DECISION = "FINALIZE_DECISION"
    SKIP_RETRIEVAL = "SKIP_RETRIEVAL"
    MARK_IRRELEVANT = "MARK_IRRELEVANT"


@dataclass
class AgentState:
    complaint_text: str
    complaint_id: Optional[str] = None
    complaint: Optional[Dict[str, Any]] = None
    parsed: Dict[str, Any] = field(default_factory=dict)
    reasoning: Dict[str, Any] = field(default_factory=dict)
    draft_decision: Dict[str, Any] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    rag_result: Dict[str, Any] = field(default_factory=dict)
    decision: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    confidence: float = 0.0
    emergency_indicators: bool = False
    out_of_scope: bool = False
    retrieved: bool = False
    retrieval_skipped: bool = False
    llm_used: bool = False
    asked_for_missing_info: bool = False
    finalized: bool = False
    needs_review: bool = False
    needs_followup: bool = False
    needs_human_review: bool = False
    final_response: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    max_steps: int = 5
    iteration: int = 0
    parsed_once: bool = False
    planner_used: bool = False


def _append_step(state: AgentState, module: str, prompt: Dict[str, Any], response: Dict[str, Any]) -> None:
    state.steps.append({"module": module, "prompt": prompt, "response": response})


def _compact_state(state: AgentState) -> Dict[str, Any]:
    return {
        "category": state.parsed.get("category"),
        "location": state.parsed.get("location") or state.parsed.get("location_details"),
        "borough": state.parsed.get("borough"),
        "urgency_guess": state.draft_decision.get("urgency_guess"),
        "confidence": round(float(state.confidence or 0.0), 2),
        "missing_fields": list(state.missing_fields),
        "emergency_indicators": state.emergency_indicators,
        "out_of_scope": state.out_of_scope,
        "retrieved": state.retrieved,
        "llm_used": state.llm_used,
        "planner_used": state.planner_used,
    }


def _detect_emergency(parsed: Dict[str, Any]) -> bool:
    text = (parsed.get("complaint_text") or "").lower()
    emergency_terms = [
        "gas leak",
        "strong gas smell",
        "rotten egg",
        "fire",
        "explosion",
        "shooting",
        "shots fired",
        "stabbed",
        "not breathing",
        "unconscious",
        "live wire",
        "downed wire",
    ]
    medical_terms = ["dizzy", "nauseous", "vomiting", "can't breathe", "fainting"]
    if parsed.get("category") == "safety" and parsed.get("time_24h") == "now":
        return True
    if any(term in text for term in emergency_terms):
        return True
    return parsed.get("category") == "safety" and any(term in text for term in medical_terms)


def _detect_out_of_scope(text: str, category: str) -> bool:
    t = (text or "").lower()
    obvious_non_311 = [
        "homework",
        "assignment",
        "essay",
        "write my",
        "weather forecast",
        "stock price",
        "movie recommendation",
        "restaurant recommendation",
        "recommend a restaurant",
        "tell me a joke",
        "book a flight",
        "translate this",
    ]
    if any(token in t for token in obvious_non_311):
        return True
    return category == "unknown" and any(token in t for token in ["recipe", "shopping list", "vacation plan"])


def _compute_missing_fields(parsed: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    if parsed.get("category") in (None, "unknown"):
        missing.append("category")
    has_location = bool(str(parsed.get("location") or "").strip()) or bool(
        str(parsed.get("location_details") or "").strip()
    )
    if not has_location:
        missing.append("location")
    return missing


def _ambiguity_signals(state: AgentState) -> List[str]:
    signals: List[str] = []
    if state.missing_fields:
        signals.append(f"missing_fields={','.join(state.missing_fields)}")
    if state.parsed.get("category") in (None, "unknown"):
        signals.append("unknown_category")
    if state.retrieved and state.evidence.get("total_matches", 0) > 0:
        agency_counts = state.evidence.get("agency_counts") or {}
        if len(agency_counts) > 1:
            signals.append("multi_agency_evidence")
        top_score = state.evidence.get("top_score")
        if top_score is not None and float(top_score) < 0.62:
            signals.append("weak_retrieval_match")
    if state.confidence < 0.6:
        signals.append("low_confidence")
    return signals


def _is_straightforward_noise_case(state: AgentState) -> bool:
    return (
        state.parsed.get("category") == "noise"
        and bool(state.parsed.get("location"))
        and bool(state.parsed.get("time_24h"))
        and bool(state.parsed.get("recurrence"))
        and not state.missing_fields
    )


def _needs_nontrivial_planning(state: AgentState) -> bool:
    if state.emergency_indicators or state.out_of_scope:
        return False
    if _is_straightforward_noise_case(state):
        return False
    if state.missing_fields and not state.asked_for_missing_info:
        return False
    if state.retrieved and not state.llm_used:
        return True
    if state.parsed.get("category") in {"sanitation", "street", "water", "parking"} and not state.retrieved:
        return True
    if state.confidence < 0.6:
        return True
    return len(_ambiguity_signals(state)) > 0


def _allowed_actions(state: AgentState) -> List[str]:
    actions: List[str] = []
    if not state.parsed_once:
        return [AgentAction.PARSE_COMPLAINT.value]
    if state.missing_fields and not state.asked_for_missing_info:
        actions.append(AgentAction.ASK_FOR_MISSING_INFO.value)
    if not state.retrieved and not state.retrieval_skipped and state.parsed.get("category") not in (None, "unknown"):
        actions.append(AgentAction.RETRIEVE_SIMILAR_CASES.value)
        actions.append(AgentAction.SKIP_RETRIEVAL.value)
    if state.retrieved and not state.llm_used:
        actions.append(AgentAction.RUN_LLM_DISAMBIGUATION.value)
    if state.confidence < 0.6 and not state.llm_used:
        actions.append(AgentAction.RUN_LLM_DISAMBIGUATION.value)
    actions.append(AgentAction.FINALIZE_DECISION.value)

    seen = set()
    deduped: List[str] = []
    for action in actions:
        if action not in seen:
            seen.add(action)
            deduped.append(action)
    return deduped


def _guardrail_thought(state: AgentState) -> Optional[Dict[str, Any]]:
    if not state.parsed_once:
        return {
            "thought": "I need structured complaint fields before I can decide whether to escalate, retrieve, or finalize.",
            "action": AgentAction.PARSE_COMPLAINT.value,
            "reasoning_mode": "guardrail",
            "planner_used": False,
            "known": {},
            "missing": [],
            "ambiguity": [],
        }

    if state.emergency_indicators and not state.finalized:
        return {
            "thought": "Immediate hazard indicators are already present, so the safest next action is emergency escalation without extra tool calls.",
            "action": AgentAction.EMERGENCY_ESCALATE.value,
            "reasoning_mode": "guardrail",
            "known": {
                "category": state.parsed.get("category"),
                "location": state.parsed.get("location") or state.parsed.get("location_details"),
                "urgency": state.draft_decision.get("urgency_guess"),
            },
            "missing": list(state.missing_fields),
            "ambiguity": [],
            "planner_used": False,
        }

    if state.out_of_scope and not state.finalized:
        return {
            "thought": "The request is outside 311 dispatch scope, so the correct next action is to mark it irrelevant and stop.",
            "action": AgentAction.MARK_IRRELEVANT.value,
            "reasoning_mode": "guardrail",
            "known": {"category": state.parsed.get("category")},
            "missing": list(state.missing_fields),
            "ambiguity": [],
            "planner_used": False,
        }

    return None


def _fallback_policy_thought(state: AgentState) -> Dict[str, Any]:
    ambiguity = _ambiguity_signals(state)

    if state.missing_fields and not state.asked_for_missing_info:
        return {
            "thought": "Critical dispatch fields are missing, so the agent should ask for them before trusting the routing decision.",
            "action": AgentAction.ASK_FOR_MISSING_INFO.value,
            "reasoning_mode": "fallback_policy",
            "known": {"category": state.parsed.get("category"), "confidence": round(state.confidence, 2)},
            "missing": list(state.missing_fields),
            "ambiguity": ambiguity,
            "planner_used": False,
        }

    if (
        state.parsed.get("category") == "noise"
        and state.parsed.get("location")
        and state.parsed.get("time_24h")
        and state.parsed.get("recurrence")
        and not state.retrieved
        and not state.retrieval_skipped
    ):
        return {
            "thought": "This is a straightforward recurring noise complaint with enough context to skip retrieval and finish cheaply.",
            "action": AgentAction.SKIP_RETRIEVAL.value,
            "reasoning_mode": "fallback_policy",
            "known": {
                "category": state.parsed.get("category"),
                "location": state.parsed.get("location"),
                "time_24h": state.parsed.get("time_24h"),
                "recurrence": state.parsed.get("recurrence"),
            },
            "missing": list(state.missing_fields),
            "ambiguity": ambiguity,
            "planner_used": False,
        }

    if (
        state.retrieval_skipped
        and not state.missing_fields
        and state.parsed.get("category") not in (None, "unknown")
    ):
        return {
            "thought": "Retrieval was skipped intentionally and there is enough structured information to finalize now.",
            "action": AgentAction.FINALIZE_DECISION.value,
            "reasoning_mode": "fallback_policy",
            "known": {"category": state.parsed.get("category"), "confidence": round(state.confidence, 2)},
            "missing": [],
            "ambiguity": ambiguity,
            "planner_used": False,
        }

    if (
        state.parsed.get("category") in {"sanitation", "street", "water", "parking"}
        and not state.retrieved
        and not state.retrieval_skipped
    ):
        return {
            "thought": "Historical 311 evidence is likely to improve routing confidence for this complaint type, so retrieval is the best next tool.",
            "action": AgentAction.RETRIEVE_SIMILAR_CASES.value,
            "reasoning_mode": "fallback_policy",
            "known": {"category": state.parsed.get("category"), "confidence": round(state.confidence, 2)},
            "missing": list(state.missing_fields),
            "ambiguity": ambiguity,
            "planner_used": False,
        }

    if state.confidence < 0.6 and not state.llm_used and llm_available():
        return {
            "thought": "Confidence is still low after current evidence, so one LLM disambiguation step is justified.",
            "action": AgentAction.RUN_LLM_DISAMBIGUATION.value,
            "reasoning_mode": "fallback_policy",
            "known": {"confidence": round(state.confidence, 2), "retrieved": state.retrieved},
            "missing": list(state.missing_fields),
            "ambiguity": ambiguity,
            "planner_used": False,
        }

    return {
        "thought": "Current evidence is sufficient, so the agent can finalize the decision.",
        "action": AgentAction.FINALIZE_DECISION.value,
        "reasoning_mode": "fallback_policy",
        "known": {"confidence": round(state.confidence, 2), "retrieved": state.retrieved},
        "missing": list(state.missing_fields),
        "ambiguity": ambiguity,
        "planner_used": False,
    }


def _planner_snapshot(state: AgentState) -> Dict[str, Any]:
    return {
        "known": {
            "category": state.parsed.get("category"),
            "location": state.parsed.get("location") or state.parsed.get("location_details"),
            "borough": state.parsed.get("borough"),
            "time_24h": state.parsed.get("time_24h"),
            "recurrence": state.parsed.get("recurrence"),
            "current_agency_guess": state.decision.get("agency"),
            "current_urgency": state.decision.get("urgency"),
            "confidence": round(state.confidence, 2),
            "retrieved": state.retrieved,
            "llm_used": state.llm_used,
        },
        "missing": list(state.missing_fields),
        "ambiguity_signals": _ambiguity_signals(state),
        "evidence": {
            "agency_counts": state.evidence.get("agency_counts"),
            "total_matches": state.evidence.get("total_matches"),
            "top_score": state.evidence.get("top_score"),
        },
        "reasoning": state.reasoning,
    }


def _apply_parse_complaint(state: AgentState) -> Dict[str, Any]:
    prompt_text = state.complaint_text
    complaint = state.complaint

    category = classify_category(prompt_text)
    time_24h = extract_time(prompt_text)
    location = extract_location(prompt_text)
    recurrence = extract_recurrence(prompt_text)
    urgency = estimate_urgency(prompt_text, category, time_24h)

    location_details = None
    borough = None

    if complaint:
        location_details = str(complaint.get("location_details") or "").strip() or None
        borough = str(complaint.get("borough") or "").strip().upper() or None
        if complaint.get("incident_time") and not time_24h:
            time_24h = complaint.get("incident_time")

    if not location and location_details:
        location = location_details

    if not borough and location and location.lower() in ["brooklyn", "manhattan", "queens", "bronx", "staten island"]:
        borough = location.upper()

    parsed = {
        "category": category,
        "location": location,
        "location_details": location_details,
        "borough": borough,
        "time_24h": time_24h,
        "recurrence": recurrence,
        "complaint_text": prompt_text,
    }

    action_guess = "Log ticket for review"
    if category == "noise":
        action_guess = "Create noise complaint ticket; advise caller; dispatch non-emergency check if repeated"
    elif category == "sanitation":
        action_guess = "Create sanitation ticket; schedule cleanup/inspection"
    elif category == "parking":
        action_guess = "Create parking enforcement request; recommend tow/inspection if blocking"
    elif category == "street":
        action_guess = "Create public works ticket; schedule repair/inspection"
    elif category == "water":
        action_guess = "Create water/sewer ticket; dispatch crew if leak/flood risk"
    elif category == "safety":
        action_guess = "Escalate immediately to emergency services"

    draft_decision = {
        "agency_guess": AGENCY_MAP.get(category, AGENCY_MAP["unknown"]),
        "urgency_guess": urgency,
        "action_guess": action_guess,
        "confidence_stub": 0.35 if category == "unknown" else 0.55,
    }

    reasoning = build_reasoning(parsed)
    decision = build_dispatch_decision(parsed, dict(draft_decision), None)
    confidence = float(decision.get("confidence", 0.0))

    state.parsed = parsed
    state.reasoning = reasoning
    state.draft_decision = draft_decision
    state.decision = decision
    state.confidence = confidence
    state.missing_fields = _compute_missing_fields(parsed)
    state.emergency_indicators = _detect_emergency(parsed) or (parsed.get("category") == "safety" and urgency == "high")
    state.out_of_scope = _detect_out_of_scope(prompt_text, category)
    state.parsed_once = True

    _append_step(
        state,
        "Preprocessing_ContextExtraction",
        {"input_prompt": prompt_text},
        {"extracted": state.parsed},
    )
    _append_step(
        state,
        "Reason_UnderstandComplaint",
        {"parsed": state.parsed},
        state.reasoning,
    )
    _append_step(
        state,
        "Decide_DispatchDecision",
        {"parsed": state.parsed, "draft_decision": state.draft_decision, "evidence": state.evidence},
        state.decision,
    )

    return {
        "parsed": state.parsed,
        "reasoning": state.reasoning,
        "baseline_decision": state.decision,
    }


def _build_thought(state: AgentState) -> Dict[str, Any]:
    guardrail = _guardrail_thought(state)
    if guardrail:
        return guardrail

    if _needs_nontrivial_planning(state) and llm_available():
        allowed_actions = _allowed_actions(state)
        try:
            plan = llm_plan_next_action(_planner_snapshot(state), allowed_actions)
            state.planner_used = True
            return {
                "thought": plan["thought"],
                "action": plan["action"],
                "reasoning_mode": "llm_planner",
                "known": _planner_snapshot(state)["known"],
                "missing": list(state.missing_fields),
                "ambiguity": _ambiguity_signals(state),
                "why": plan.get("why", ""),
                "need_more_information": plan.get("need_more_information", False),
                "planner_used": True,
                "planner_allowed_actions": allowed_actions,
            }
        except Exception as exc:
            fallback = _fallback_policy_thought(state)
            fallback["reasoning_mode"] = "fallback_after_llm_error"
            fallback["planner_error"] = str(exc)
            fallback["planner_allowed_actions"] = allowed_actions
            return fallback

    return _fallback_policy_thought(state)


def _apply_missing_info_followup(state: AgentState) -> Dict[str, Any]:
    state.asked_for_missing_info = True
    state.needs_followup = True

    followup_questions: List[str] = []
    if "location" in state.missing_fields:
        followup_questions.append("exact address or nearest cross-street")
        followup_questions.append("borough")
    if "category" in state.missing_fields:
        followup_questions.append("what issue is happening and what is visibly affected")

    state.decision["agency"] = "311 Triage (Needs More Info)"
    state.decision["confidence"] = min(float(state.decision.get("confidence", 0.4)), 0.4)
    state.decision["action"] = (
        "Ask the reporter for: "
        + ", ".join(followup_questions)
        + ". If there is immediate danger, instruct the reporter to call 911."
    )
    state.decision["justification"] = (
        (state.decision.get("justification") or "Insufficient dispatch information.")
        + f" Missing fields: {', '.join(state.missing_fields)}."
    )
    state.confidence = float(state.decision["confidence"])

    return {
        "missing_fields": list(state.missing_fields),
        "follow_up_action": state.decision["action"],
        "confidence": state.confidence,
    }


def _apply_retrieval(state: AgentState) -> Dict[str, Any]:
    state.rag_result = retrieve_similar_cases(state.parsed, top_k=3)
    state.retrieved = True
    _append_step(
        state,
        "Act_RAG_RetrieveSimilarCases",
        {"parsed": state.parsed, "top_k": 3},
        state.rag_result,
    )

    cases = state.rag_result.get("cases", []) if isinstance(state.rag_result, dict) else []
    state.evidence = summarize_evidence(cases)
    _append_step(
        state,
        "Observe_SummarizeEvidence",
        {"cases": cases},
        state.evidence,
    )
    state.decision = build_dispatch_decision(state.parsed, dict(state.draft_decision), state.evidence)
    state.confidence = float(state.decision.get("confidence", 0.0))

    return {
        "rag_result": state.rag_result,
        "evidence": state.evidence,
        "decision_after_retrieval": state.decision,
    }


def _apply_llm(state: AgentState) -> Dict[str, Any]:
    state.llm_used = True
    llm_prompt = {
        "parsed": state.parsed,
        "evidence": {
            "agency_counts": state.evidence.get("agency_counts"),
            "total_matches": state.evidence.get("total_matches"),
            "top_score": state.evidence.get("top_score"),
        },
        "current_decision": state.decision,
        "missing_fields": state.missing_fields,
    }

    if not llm_available():
        return {"skipped": True, "error": "LLM not configured"}
    try:
        llm_out = llm_decide(state.parsed, evidence=state.evidence)
    except Exception as exc:
        _append_step(
            state,
            "LLM_Disambiguation",
            llm_prompt,
            {"skipped": False, "error": str(exc)},
        )
        return {"skipped": False, "error": str(exc)}

    if state.parsed.get("category") in (None, "unknown"):
        llm_out["agency"] = "311 Triage (Unknown)"

    if "location" in state.missing_fields:
        llm_out["confidence"] = min(float(llm_out.get("confidence", 0.4)), 0.4)

    state.decision = llm_out
    state.confidence = float(state.decision.get("confidence", 0.0))
    _append_step(state, "LLM_Disambiguation", llm_prompt, llm_out)

    return {"llm_prompt": llm_prompt, "llm_decision": llm_out}


def _apply_emergency_escalation(state: AgentState) -> Dict[str, Any]:
    location = state.parsed.get("location") or state.parsed.get("location_details") or "reported location"
    state.decision = {
        "agency": "Emergency Services / Police",
        "urgency": "high",
        "action": "Escalate immediately to emergency services",
        "justification": f"Immediate hazard indicators detected; emergency escalation is safer than waiting for additional evidence. location={location}",
        "confidence": 0.95,
    }
    state.confidence = 0.95
    return {"decision": state.decision}


def _apply_irrelevant_mark(state: AgentState) -> Dict[str, Any]:
    state.decision = {
        "agency": "311 Triage (Irrelevant)",
        "urgency": "low",
        "action": "Mark request as out of scope for municipal 311 dispatch and route to a general support channel.",
        "justification": "The complaint content appears unrelated to municipal service triage.",
        "confidence": 0.95,
    }
    state.confidence = 0.95
    return {"decision": state.decision}


def _apply_skip_retrieval(state: AgentState) -> Dict[str, Any]:
    state.retrieval_skipped = True
    return {
        "reason": "Complaint is clear enough to finalize without historical retrieval.",
        "decision_before_finalize": state.decision,
    }


def _finalize_state(state: AgentState) -> Dict[str, Any]:
    state.missing_fields = _compute_missing_fields(state.parsed)
    if not state.decision:
        state.decision = build_dispatch_decision(state.parsed, dict(state.draft_decision), state.evidence or None)

    confidence = float(state.decision.get("confidence", 0.0))
    needs_review = confidence < 0.6
    needs_followup = len(state.missing_fields) > 0 or state.asked_for_missing_info
    needs_human_review = needs_review or needs_followup

    state.needs_review = needs_review
    state.needs_followup = needs_followup
    state.needs_human_review = needs_human_review
    state.finalized = True
    state.confidence = confidence

    final_decision = dict(state.decision)
    final_decision["needs_human_review"] = needs_human_review
    final_decision["missing_fields"] = list(state.missing_fields)
    return final_decision


def _execute_action(state: AgentState, action: AgentAction) -> Dict[str, Any]:
    if action == AgentAction.PARSE_COMPLAINT:
        return _apply_parse_complaint(state)
    if action == AgentAction.EMERGENCY_ESCALATE:
        return _apply_emergency_escalation(state)
    if action == AgentAction.MARK_IRRELEVANT:
        return _apply_irrelevant_mark(state)
    if action == AgentAction.ASK_FOR_MISSING_INFO:
        return _apply_missing_info_followup(state)
    if action == AgentAction.RETRIEVE_SIMILAR_CASES:
        return _apply_retrieval(state)
    if action == AgentAction.RUN_LLM_DISAMBIGUATION:
        return _apply_llm(state)
    if action == AgentAction.SKIP_RETRIEVAL:
        return _apply_skip_retrieval(state)
    if action == AgentAction.FINALIZE_DECISION:
        return _finalize_state(state)
    return {"error": f"Unsupported action: {action.value}"}


def run_agent_loop(
    prompt_text: str,
    complaint: Optional[Dict[str, Any]] = None,
    complaint_id: Optional[str] = None,
) -> Dict[str, Any]:
    state = AgentState(complaint_text=prompt_text, complaint_id=complaint_id, complaint=complaint)

    while not state.finalized and state.iteration < state.max_steps:
        state.iteration += 1
        thought = _build_thought(state)
        action = AgentAction(thought["action"])

        _append_step(
            state,
            "Agent_Thought",
            {"iteration": state.iteration, "state": _compact_state(state)},
            thought,
        )

        _append_step(
            state,
            "Agent_Action",
            {"iteration": state.iteration, "chosen_action": action.value},
            {
                "tool_target": {
                    AgentAction.PARSE_COMPLAINT: "Preprocessing_ContextExtraction / Reason_UnderstandComplaint / Decide_DispatchDecision",
                    AgentAction.RETRIEVE_SIMILAR_CASES: "Act_RAG_RetrieveSimilarCases",
                    AgentAction.RUN_LLM_DISAMBIGUATION: "LLM_Disambiguation",
                    AgentAction.EMERGENCY_ESCALATE: "Emergency policy",
                    AgentAction.ASK_FOR_MISSING_INFO: "Follow-up policy",
                    AgentAction.MARK_IRRELEVANT: "Out-of-scope policy",
                    AgentAction.SKIP_RETRIEVAL: "Planner policy",
                    AgentAction.FINALIZE_DECISION: "Finalization policy",
                }[action]
            },
        )

        observation = _execute_action(state, action)
        _append_step(
            state,
            "Agent_Observation",
            {"iteration": state.iteration, "action": action.value},
            {
                "observation": observation,
                "state": _compact_state(state),
                "continue": not state.finalized,
            },
        )

        if action in {
            AgentAction.EMERGENCY_ESCALATE,
            AgentAction.MARK_IRRELEVANT,
            AgentAction.FINALIZE_DECISION,
        }:
            state.finalized = action != AgentAction.FINALIZE_DECISION or state.finalized

        if action in {AgentAction.EMERGENCY_ESCALATE, AgentAction.MARK_IRRELEVANT}:
            _finalize_state(state)

    if not state.finalized:
        _finalize_state(state)

    _append_step(
        state,
        "Confidence_Gating",
        {"confidence": state.confidence, "threshold": 0.6, "missing_fields": state.missing_fields},
        {"passes": not state.needs_review},
    )
    _append_step(
        state,
        "Human_Review_Escalation",
        {"confidence": state.confidence, "missing_fields": state.missing_fields},
        {
            "needs_review": state.needs_review,
            "needs_followup": state.needs_followup,
            "needs_human_review": state.needs_human_review,
        },
    )

    _append_step(
        state,
        "Final_Decision",
        {"state": _compact_state(state)},
        {
            "decision": state.decision,
            "needs_review": state.needs_review,
            "needs_followup": state.needs_followup,
            "needs_human_review": state.needs_human_review,
            "missing_fields": state.missing_fields,
        },
    )

    state.final_response = format_user_response(state.decision)
    _append_step(
        state,
        "Response_Generator",
        {"decision": state.decision},
        {"text": state.final_response},
    )

    return {
        "status": "ok",
        "error": None,
        "response": state.final_response,
        "steps": state.steps,
        "decision": state.decision,
        "evidence": state.evidence,
        "missing_fields": state.missing_fields,
        "needs_review": state.needs_review,
        "needs_followup": state.needs_followup,
        "needs_human_review": state.needs_human_review,
    }
