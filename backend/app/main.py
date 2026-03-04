from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import os
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from .core.rag import retrieve_similar_cases, summarize_evidence
from .core.llm_decider import llm_available, llm_decide

from .core.preprocessing import (
    AGENCY_MAP,
    classify_category,
    estimate_urgency,
    extract_location,
    extract_recurrence,
    extract_time,
)

from .core.decision import build_reasoning, build_dispatch_decision
from .core.formatting import format_user_response
from .core.supabase_client import (
    fetch_complaint,
    insert_complaint,
    insert_execution,
    list_recent_complaints,
    update_complaint_status,
)

app = FastAPI(title="Dispatch AI Agent")
static_dir = os.path.join(os.path.dirname(__file__), "../../static")
app.mount("../../static", StaticFiles(directory=static_dir), name="static")

@app.get("/team_info")
def team_info():
    return {
        "group_batch_order_number": "Batch2_10",
        "team_name": "Nadine_Sara_Noor",
        "students": [
            {"name": "Nadine Hijazi", "email": "nadeenhijazi@campus.technion.ac.il"},
            {"name": "Sara Rafe", "email": "Sararafe@campus.technion.ac.il"},
            {"name": "Noor Shahin", "email": "noor.shahin@campus.technion.ac.il"},
        ],
    }


@app.get("/agent_info")
def agent_info():
    return {
        "description": (
            "Dispatch AI agent that triages a 311-style complaint and outputs an operational decision: "
            "agency + urgency + recommended action, with traceable steps."
        ),
        "purpose": (
            "Assist human dispatchers by standardizing triage decisions with evidence from similar historical cases. "
            "The agent recommends agency and urgency, and uses a gated LLM refinement step only when confidence is low or critical information is missing."
        ),
        "modules": [
            "Preprocessing_ContextExtraction",
            "Reason_UnderstandComplaint",
            "Act_RAG_RetrieveSimilarCases",
            "Observe_SummarizeEvidence",
            "Decide_DispatchDecision",
            "LLM_Disambiguation",
            "Confidence_Gating",
            "Human_Review_Escalation",
            "Response_Generator",
        ],
        "steps_semantics": (
            "The steps array includes actual LLM calls only. "
            "In this agent, LLM_Disambiguation appears only when confidence is low or critical fields are missing; deterministic and retrieval steps are not included in steps."
        ),
        "prompt_template": {
            "template": (
                "You are a municipal dispatch agent.\n"
                "Given a complaint, return JSON with:\n"
                "{agency, urgency(low/medium/high), action, justification, confidence(0-1)}\n\n"
                "Complaint: {complaint_text}\n"
                "Location: {location}\n"
                "Time: {time}\n"
            )
        },
        "prompt_examples": [
            {
                "prompt": "loud party at 2am in Brooklyn, recurring every weekend.",
                "full_response": (
                    "Decision:\n"
                    "- Agency: NYPD\n"
                    "- Urgency: medium\n"
                    "- Action: Create noise complaint ticket; advise caller; dispatch non-emergency check if repeated\n"
                    "- Justification: time=02:00, recurrence=every weekend, location=Brooklyn, category=noise, evidence_top_agency=NYPD, evidence_vote_ratio=1.00, evidence_top_score=0.62\n"
                    "- Confidence: 0.85\n"
                ),
                "steps": [],
            }
        ],
    }

@app.get("/model_architecture")
def model_architecture():
    png_path = os.path.join(os.path.dirname(__file__), "model_architecture.png")
    if not os.path.exists(png_path):
        raise HTTPException(status_code=404, detail="model_architecture.png not found")
    return FileResponse(png_path, media_type="image/png")


class ExecuteRequest(BaseModel):
    prompt: Optional[str] = None
    complaint_id: Optional[str] = None


class ComplaintCreate(BaseModel):
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    complaint_text: str
    borough: Optional[str] = None
    location_details: Optional[str] = None
    incident_time: Optional[str] = None
    urgency_hint: Optional[str] = None
    consent: Optional[bool] = None

class Step(BaseModel):
    module: str
    prompt: Dict[str, Any]
    response: Dict[str, Any]


@app.post("/complaints")
def create_complaint(payload: ComplaintCreate):
    try:
        if not payload.full_name or not payload.full_name.strip():
            return {"status": "error", "error": "full_name is required", "complaint_id": None}

        if not payload.complaint_text or not payload.complaint_text.strip():
            return {"status": "error", "error": "complaint_text is required", "complaint_id": None}

        # ✅ NEW CHECK: Borough required
        if not payload.borough or payload.borough.upper() == "UNKNOWN":
            return {"status": "error", "error": "borough is required", "complaint_id": None}

        # ✅ NEW CHECK: Location details required
        if not payload.location_details or not payload.location_details.strip():
            return {"status": "error", "error": "location_details is required", "complaint_id": None}

        if payload.consent is not True:
            return {"status": "error", "error": "consent is required", "complaint_id": None}

        complaint_id = insert_complaint(
            {
                "full_name": payload.full_name.strip(),
                "phone": payload.phone,
                "email": payload.email,
                "complaint_text": payload.complaint_text.strip(),
                "borough": payload.borough,
                "location_details": payload.location_details.strip(),
                "incident_time": payload.incident_time,
                "urgency_hint": payload.urgency_hint,
                "status": "new",
            }
        )

        return {"status": "ok", "error": None, "complaint_id": complaint_id}

    except Exception as e:
        return {"status": "error", "error": f"Supabase insert failed: {str(e)}", "complaint_id": None}

@app.get("/complaints_recent")
def complaints_recent():
    try:
        return {"status": "ok", "error": None, "items": list_recent_complaints(10)}
    except Exception as e:
        return {"status": "error", "error": f"Supabase fetch failed: {str(e)}", "items": []}

@app.post("/execute")
def execute(req: ExecuteRequest):
    """
    Course requirement:
    - Top-level response fields MUST be exactly: status, error, response, steps
    - steps[] logs the full pipeline in order (module + prompt + response)
    “We use gated LLM calls only when confidence is low or critical info is missing, to minimize cost.”
    """
    try:
        complaint = None
        prompt_text = None
        complaint_id = None

        if req.complaint_id:
            complaint_id = req.complaint_id
            complaint = fetch_complaint(complaint_id)
            if not complaint:
                return {
                    "status": "error",
                    "error": "Complaint not found for provided complaint_id.",
                    "response": None,
                    "steps": []
                }
            prompt_text = complaint.get("complaint_text")
        elif req.prompt and req.prompt.strip():
            prompt_text = req.prompt.strip()
        else:
            return {
                "status": "error",
                "error": "Provide either complaint_id or a non-empty prompt.",
                "response": None,
                "steps": []
            }

        steps: List[Dict[str, Any]] = []

        # -------- Preprocessing (deterministic, no LLM yet) --------
        category = classify_category(prompt_text)
        time_24h = extract_time(prompt_text)
        location = extract_location(prompt_text)
        recurrence = extract_recurrence(prompt_text)
        urgency = estimate_urgency(prompt_text, category, time_24h)

        # structured fields from complaint (if exists)
        location_details = None
        if complaint and complaint.get("location_details"):
            location_details = str(complaint.get("location_details")).strip() or None

        # if NLP location missing, use structured location_details as fallback
        if (not location) and location_details:
            location = location_details

        borough = None
        if location and location.lower() in ["brooklyn", "manhattan", "queens", "bronx", "staten island"]:
            borough = location.upper()
        if complaint and complaint.get("borough"):
            borough = str(complaint.get("borough")).upper()

        if complaint and complaint.get("incident_time") and not time_24h:
            time_24h = complaint.get("incident_time")

        agency_guess = AGENCY_MAP.get(category, AGENCY_MAP["unknown"])

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

        parsed = {
            "category": category,
            "location": location,  # may now come from location_details
            "location_details": location_details,  # keep for trace/audit
            "borough": borough,
            "time_24h": time_24h,
            "recurrence": recurrence,
            "complaint_text": prompt_text,
        }
        draft_decision = {
            "agency_guess": agency_guess,
            "urgency_guess": urgency,
            "action_guess": action_guess,
            "confidence_stub": 0.35 if category == "unknown" else 0.55,
        }

        reasoning = build_reasoning(parsed)

        rag_result = retrieve_similar_cases(parsed, top_k=3)
        cases = rag_result.get("cases", []) if isinstance(rag_result, dict) else []

        evidence = summarize_evidence(cases)

        decision = build_dispatch_decision(parsed, draft_decision, evidence)

        if parsed.get("category") in (None, "unknown"):
            decision["agency"] = "311 Triage (Unknown)"

        # -------- Compute critical missing (based on parsed) --------
        critical_missing = []

        if parsed.get("category") in (None, "unknown"):
            critical_missing.append("category")

        has_any_location = (
                bool(str(parsed.get("location") or "").strip()) or
                bool(str(parsed.get("location_details") or "").strip())
        )
        if not has_any_location:
            critical_missing.append("location")

        # -------- Optional gated LLM refinement --------
        confidence = float(decision.get("confidence", 0.0))
        rag_ok = isinstance(rag_result, dict) and rag_result.get("ok") is True
        rag_skipped_or_failed = not rag_ok

        should_call_llm = (
                confidence < 0.6
                or len(critical_missing) > 0
                or (rag_skipped_or_failed and parsed.get("category") in (None, "unknown"))
        )

        if should_call_llm:
            if llm_available():
                try:
                    llm_prompt_obj = {
                        "parsed": parsed,
                        "evidence": {
                            "agency_counts": evidence.get("agency_counts"),
                            "total_matches": evidence.get("total_matches"),
                            "top_score": evidence.get("top_score"),
                        },
                        "current_decision": decision,
                        "critical_missing": critical_missing,
                    }

                    llm_out = llm_decide(parsed, evidence=evidence)

                    # Final decision is refined only in this gated LLM step.
                    decision = llm_out
                    # 🔒 FINAL AGENCY LOCK (after LLM)
                    if parsed.get("category") in (None, "unknown"):
                        decision["agency"] = "311 Triage (Unknown)"
                    # 🔒 Lock urgency deterministically
                    heur = estimate_urgency(
                        parsed.get("complaint_text", ""),
                        parsed.get("category", "unknown"),
                        parsed.get("time_24h")
                    )
                    decision["urgency"] = heur

                    # 🔒 Cap confidence deterministically
                    if parsed.get("category") in (None, "unknown"):
                        decision["confidence"] = min(decision.get("confidence", 0.0), 0.4)

                    if "location" in critical_missing:
                        decision["confidence"] = min(decision.get("confidence", 0.0), 0.4)

                    steps.append({
                        "module": "LLM_Disambiguation",
                        "prompt": llm_prompt_obj,
                        "response": llm_out
                    })

                except Exception as e:
                    steps.append({
                        "module": "LLM_Disambiguation",
                        "prompt": {"parsed": parsed, "critical_missing": critical_missing},
                        "response": {"skipped": False, "error": str(e)}
                    })
        if "location" in critical_missing:
            decision["action"] = (
                "Request exact address or nearest cross-street and borough, then route to DSNY for inspection/cleanup; "
                "escalate to DOHMH only if pests, persistent odor, or hazardous waste are reported."
            )

            just = (decision.get("justification") or "").strip()
            if "missing required dispatch field" not in just.lower():
                decision["justification"] = just + " (Missing required dispatch field: location/address.)"

        # -------- Confidence gating --------
        confidence = float(decision.get("confidence", 0.0))
        passes = confidence >= 0.6
        needs_review = confidence < 0.6
        needs_followup = len(critical_missing) > 0
        needs_human_review = needs_review or needs_followup

        user_friendly = format_user_response(decision)

        final_response = user_friendly

        payload = {
            "status": "ok",
            "error": None,
            "response": final_response,
            "steps": steps
        }
        if complaint_id:
            try:
                top_matches = evidence.get("top_cases", []) if isinstance(evidence, dict) else []
                insert_execution(
                    {
                        "complaint_id": complaint_id,
                        "final_agency": decision.get("agency"),
                        "final_urgency": decision.get("urgency"),
                        "final_action": decision.get("action"),
                        "confidence": decision.get("confidence"),
                        "escalated": needs_human_review,
                        "top_matches": top_matches,
                        "steps": steps,
                        "response_text": final_response,
                        "needs_review": needs_review,
                        "needs_followup": needs_followup,
                        "missing_fields": critical_missing,
                    }
                )
                update_complaint_status(complaint_id, "needs_human" if needs_human_review else "processed")
            except Exception as e:
                print("Insert execution failed:", e)
        return payload

    except Exception as e:
        error_payload = {
            "status": "error",
            "error": f"Unexpected server error: {str(e)}",
            "response": None,
            "steps": []
        }
        return error_payload


@app.get("/", response_class=HTMLResponse)
def ui():
    html_path = os.path.join(os.path.dirname(__file__), "../../static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()





