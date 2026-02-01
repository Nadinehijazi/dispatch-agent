from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import os
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from .core.rag import retrieve_similar_cases, summarize_evidence


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
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/api/team_info")
def team_info():
    return {
        "group_batch_order_number": "Batch1_06",
        "team_name": "Nadine_Sara_Noor",
        "students": [
            {"name": "Nadine Hijazi", "email": "nadeenhijazi@campus.technion.ac.il"},
            {"name": "Sara Rafe", "email": "Sararafe@campus.technion.ac.il"},
            {"name": "Noor Shahin", "email": "noor.shahin@campus.technion.ac.il"},
        ],
    }


@app.get("/api/agent_info")
def agent_info():
    return {
        "description": (
            "Dispatch AI agent that triages a 311-style complaint and outputs an operational decision: "
            "agency + urgency + recommended action, with traceable steps."
        ),
        "purpose": (
            "Assist human dispatchers by standardizing triage decisions with evidence from similar historical cases. "
            "The agent recommends agency and urgency, provides transparent steps, and escalates when uncertain."
        ),
        "modules": [
            "Preprocessing_ContextExtraction",
            "Reason_UnderstandComplaint",
            "Act_RAG_RetrieveSimilarCases",
            "Observe_SummarizeEvidence",
            "Decide_DispatchDecision",
            "Confidence_Gating",
            "Human_Review_Escalation",
            "Response_Generator",
        ],
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
                "prompt": "Noise complaint: loud party at 2am in Brooklyn, recurring every weekend.",
                "full_response": (
                    "agency=NYC Noise / NYPD (non-emergency), urgency=medium, action=log + advise caller + patrol check if repeated, "
                    "justification=late-night recurring disturbance, confidence=0.55"
                ),
                "steps": [
                    {
                        "module": "Preprocessing_ContextExtraction",
                        "prompt": {"input": "Noise complaint: loud party at 2am in Brooklyn, recurring every weekend."},
                        "response": {
                            "complaint_summary": "Recurring late-night noise disturbance (party) at 2am in Brooklyn",
                            "signals": ["nighttime", "recurring"],
                            "location": "Brooklyn"
                        },
                    },
                    {
                        "module": "Reason_UnderstandComplaint",
                        "prompt": {"task": "Infer urgency + route candidates (no RAG yet - stub)."},
                        "response": {
                            "candidate_agencies": ["NYC Noise", "NYPD (non-emergency)"],
                            "urgency": "medium",
                            "missing_info": ["exact address/building type"],
                        },
                    },
                ],
            }
        ],
    }

@app.get("/api/model_architecture")
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


@app.post("/api/complaints")
def create_complaint(payload: ComplaintCreate):
    try:
        if not payload.full_name or not payload.full_name.strip():
            return {"status": "error", "error": "full_name is required", "complaint_id": None}
        if not payload.complaint_text or not payload.complaint_text.strip():
            return {"status": "error", "error": "complaint_text is required", "complaint_id": None}

        complaint_id = insert_complaint(
            {
                "full_name": payload.full_name.strip(),
                "phone": payload.phone,
                "email": payload.email,
                "complaint_text": payload.complaint_text.strip(),
                "borough": payload.borough,
                "location_details": payload.location_details,
                "incident_time": payload.incident_time,
                "urgency_hint": payload.urgency_hint,
                "status": "new",
            }
        )
        return {"status": "ok", "error": None, "complaint_id": complaint_id}
    except Exception as e:
        return {"status": "error", "error": f"Supabase insert failed: {str(e)}", "complaint_id": None}


@app.get("/api/complaints_recent")
def complaints_recent():
    try:
        return {"status": "ok", "error": None, "items": list_recent_complaints(10)}
    except Exception as e:
        return {"status": "error", "error": f"Supabase fetch failed: {str(e)}", "items": []}

@app.post("/api/execute")
def execute(req: ExecuteRequest):
    """
    Course requirement:
    - Top-level response fields MUST be exactly: status, error, response, steps
    - steps[] MUST describe every LLM call in order (module + prompt + response)
    Right now we have no LLM calls; we log deterministic steps for traceability.
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
            "location": location,
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

        # -------- Steps trace (1) Preprocessing --------
        steps.append({
            "module": "Preprocessing_ContextExtraction",
            "prompt": {"input_prompt": prompt_text},
            "response": {"extracted": parsed}
        })

        # -------- Steps trace (2) Reason --------
        reasoning = build_reasoning(parsed)
        steps.append({
            "module": "Reason_UnderstandComplaint",
            "prompt": {"parsed": parsed},
            "response": reasoning
        })

        # -------- Steps trace (3) Act: RAG retrieve (stub) --------
        try:
            cases = retrieve_similar_cases(parsed, top_k=3)
            steps.append({
                "module": "Act_RAG_RetrieveSimilarCases",
                "prompt": {"parsed": parsed, "top_k": 3},
                "response": {"cases": cases}
            })
        except Exception as e:
            steps.append({
                "module": "Act_RAG_RetrieveSimilarCases",
                "prompt": {"parsed": parsed, "top_k": 3},
                "response": {"error": str(e)}
            })
            return {
                "status": "error",
                "error": f"RAG retrieval failed: {str(e)}",
                "response": None,
                "steps": steps
            }

        # -------- Steps trace (4) Observe: summarize evidence --------
        evidence = summarize_evidence(cases)
        steps.append({
            "module": "Observe_SummarizeEvidence",
            "prompt": {"cases": cases},
            "response": evidence
        })

        # -------- Steps trace (5) Decide --------
        decision = build_dispatch_decision(parsed, draft_decision, evidence)

        steps.append({
            "module": "Decide_DispatchDecision",
            "prompt": {"parsed": parsed, "draft_decision": draft_decision, "evidence": evidence},
            "response": decision
        })

        # -------- Steps trace (6) Confidence gating --------
        confidence = float(decision.get("confidence", 0.0))
        critical_missing = []
        if parsed.get("category") in (None, "unknown"):
            critical_missing.append("category")
        if not parsed.get("location"):
            critical_missing.append("location")

        needs_review = confidence < 0.6 or len(critical_missing) > 0
        steps.append({
            "module": "Confidence_Gating",
            "prompt": {"confidence": confidence, "threshold": 0.6, "critical_missing": critical_missing},
            "response": {"passes": not needs_review}
        })

        steps.append({
            "module": "Human_Review_Escalation",
            "prompt": {"confidence": confidence, "critical_missing": critical_missing},
            "response": {
                "needs_human_review": needs_review,
                "reason": "low_confidence_or_missing_info" if needs_review else "none"
            }
        })

        # -------- Steps trace (6) Response Generator --------
        user_friendly = format_user_response(decision)
        steps.append({
            "module": "Response_Generator",
            "prompt": {"decision": decision},
            "response": {"text": user_friendly}
        })

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
                        "escalated": needs_review,
                        "top_matches": top_matches,
                        "steps": steps,
                        "response_text": final_response,
                    }
                )
                update_complaint_status(complaint_id, "needs_human" if needs_review else "processed")
            except Exception:
                pass
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
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()
