from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import os
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from .core.agent_controller import run_agent_loop
from .core.supabase_client import (
    fetch_complaint,
    insert_complaint,
    insert_execution,
    list_recent_complaints,
    update_complaint_status,
)

app = FastAPI(title="Dispatch AI Agent")
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/api/team_info")
@app.get("/team_info")
def team_info():
    return {
        "group_batch_order_number": "2_10",
        "team_name": "Nadine_Sara_Noor",
        "students": [
            {"name": "Nadine Hijazi", "email": "nadeenhijazi@campus.technion.ac.il"},
            {"name": "Sara Rafe", "email": "Sararafe@campus.technion.ac.il"},
            {"name": "Noor Shahin", "email": "noor.shahin@campus.technion.ac.il"},
        ],
    }


@app.get("/api/agent_info")
@app.get("/agent_info")
def agent_info():
    return {
        "description": (
            "Dispatch AI agent that triages a 311-style complaint using a dynamic "
            "Thought -> Action -> Observation loop and outputs an operational decision."
        ),
        "purpose": (
            "Assist human dispatchers by choosing the next best tool at runtime: "
            "escalate immediately, retrieve similar cases, ask for missing information, "
            "run a gated LLM disambiguation step, or finalize early when enough evidence exists. "
            "The planner uses deterministic guardrails for hard constraints and an LLM-assisted next-action planner for ambiguous cases."
        ),
        "modules": [
            "Preprocessing_ContextExtraction",
            "Reason_UnderstandComplaint",
            "Agent_Thought",
            "Agent_Action",
            "Agent_Observation",
            "Act_RAG_RetrieveSimilarCases",
            "Observe_SummarizeEvidence",
            "Decide_DispatchDecision",
            "LLM_Disambiguation",
            "Confidence_Gating",
            "Human_Review_Escalation",
            "Final_Decision",
            "Response_Generator",
        ],
        "action_space": [
            "PARSE_COMPLAINT",
            "EMERGENCY_ESCALATE",
            "RETRIEVE_SIMILAR_CASES",
            "RUN_LLM_DISAMBIGUATION",
            "ASK_FOR_MISSING_INFO",
            "SKIP_RETRIEVAL",
            "MARK_IRRELEVANT",
            "FINALIZE_DECISION",
        ],
        "steps_semantics": (
            "The steps array records the agent's dynamic control flow. "
            "Each loop iteration emits Agent_Thought, Agent_Action, and Agent_Observation entries. "
            "Deterministic preprocessing, retrieval, decision, and gating steps are logged when used. "
            "Agent_Thought includes the reasoning mode (guardrail, llm_planner, fallback_policy, or fallback_after_llm_error). "
            "LLM_Disambiguation appears only when the agent explicitly chooses to use the LLM."
        ),
        "prompt_template": {
            "template": (
                "Citizen complaint: {complaint_text}\n"
                "The agent decides dynamically whether to escalate, retrieve, ask for more info, "
                "run LLM disambiguation, or finalize."
            )
        },
        "prompt_examples": [
            {
                "prompt": "loud party at 2am in Brooklyn, recurring every weekend.",
                "full_response": (
                    "Decision:\n"
                    "- Agency: Noise Control / Non-emergency Police\n"
                    "- Urgency: medium\n"
                    "- Action: Create noise complaint ticket; advise caller; dispatch non-emergency check if repeated\n"
                    "- Justification: Recurring late-night noise at 02:00 in Brooklyn is a straightforward non-emergency quality-of-life complaint with enough detail to route directly without additional evidence.\n"
                    "- Confidence: 0.78\n"
                ),
                "steps": [
                    {
                        "module": "Agent_Thought",
                        "prompt": {"iteration": 1},
                        "response": {
                            "thought": "I need structured complaint fields before I can decide whether to escalate, retrieve, or finalize.",
                            "action": "PARSE_COMPLAINT",
                            "reasoning_mode": "guardrail",
                        },
                    },
                    {
                        "module": "Agent_Action",
                        "prompt": {"iteration": 1, "chosen_action": "PARSE_COMPLAINT"},
                        "response": {"tool_target": "Preprocessing_ContextExtraction / Reason_UnderstandComplaint / Decide_DispatchDecision"},
                    },
                    {
                        "module": "Preprocessing_ContextExtraction",
                        "prompt": {"input_prompt": "loud party at 2am in Brooklyn, recurring every weekend."},
                        "response": {
                            "extracted": {
                                "category": "noise",
                                "location": "Brooklyn",
                                "location_details": None,
                                "borough": "BROOKLYN",
                                "time_24h": "02:00",
                                "recurrence": "every weekend",
                                "complaint_text": "loud party at 2am in Brooklyn, recurring every weekend.",
                            }
                        },
                    },
                    {
                        "module": "Reason_UnderstandComplaint",
                        "prompt": {
                            "parsed": {
                                "category": "noise",
                                "location": "Brooklyn",
                                "location_details": None,
                                "borough": "BROOKLYN",
                                "time_24h": "02:00",
                                "recurrence": "every weekend",
                                "complaint_text": "loud party at 2am in Brooklyn, recurring every weekend.",
                            }
                        },
                        "response": {
                            "intent": "Handle a noise complaint",
                            "constraints": ["recurring issue"],
                            "missing_info": [],
                        },
                    },
                    {
                        "module": "Decide_DispatchDecision",
                        "prompt": {
                            "parsed": {
                                "category": "noise",
                                "location": "Brooklyn",
                                "location_details": None,
                                "borough": "BROOKLYN",
                                "time_24h": "02:00",
                                "recurrence": "every weekend",
                                "complaint_text": "loud party at 2am in Brooklyn, recurring every weekend.",
                            },
                            "draft_decision": {
                                "agency_guess": "Noise Control / Non-emergency Police",
                                "urgency_guess": "medium",
                                "action_guess": "Create noise complaint ticket; advise caller; dispatch non-emergency check if repeated",
                                "confidence_stub": 0.55,
                            },
                            "evidence": {},
                        },
                        "response": {
                            "agency": "Noise Control / Non-emergency Police",
                            "urgency": "medium",
                            "action": "Create noise complaint ticket; advise caller; dispatch non-emergency check if repeated",
                            "justification": "Recurring late-night noise at 02:00 in Brooklyn is a straightforward non-emergency quality-of-life complaint with enough detail to route directly without additional evidence.",
                            "confidence": 0.78,
                        },
                    },
                    {
                        "module": "Agent_Observation",
                        "prompt": {"iteration": 1, "action": "PARSE_COMPLAINT"},
                        "response": {"continue": True},
                    },
                    {
                        "module": "Agent_Thought",
                        "prompt": {"iteration": 2},
                        "response": {
                            "thought": "This is a straightforward recurring noise complaint with enough context to skip retrieval and finish cheaply.",
                            "action": "SKIP_RETRIEVAL",
                            "reasoning_mode": "fallback_policy",
                        },
                    },
                    {
                        "module": "Agent_Action",
                        "prompt": {"iteration": 2, "chosen_action": "SKIP_RETRIEVAL"},
                        "response": {"tool_target": "Planner policy"},
                    },
                    {
                        "module": "Agent_Observation",
                        "prompt": {"iteration": 2, "action": "SKIP_RETRIEVAL"},
                        "response": {"continue": True},
                    },
                    {
                        "module": "Agent_Thought",
                        "prompt": {"iteration": 3},
                        "response": {
                            "thought": "Retrieval was skipped intentionally and there is enough structured information to finalize now.",
                            "action": "FINALIZE_DECISION",
                            "reasoning_mode": "fallback_policy",
                        },
                    },
                    {
                        "module": "Agent_Action",
                        "prompt": {"iteration": 3, "chosen_action": "FINALIZE_DECISION"},
                        "response": {"tool_target": "Finalization policy"},
                    },
                    {
                        "module": "Agent_Observation",
                        "prompt": {"iteration": 3, "action": "FINALIZE_DECISION"},
                        "response": {"continue": False},
                    },
                    {
                        "module": "Confidence_Gating",
                        "prompt": {"confidence": 0.78, "threshold": 0.6, "missing_fields": []},
                        "response": {"passes": True},
                    },
                    {
                        "module": "Human_Review_Escalation",
                        "prompt": {"confidence": 0.78, "missing_fields": []},
                        "response": {
                            "needs_review": False,
                            "needs_followup": False,
                            "needs_human_review": False,
                        },
                    },
                ],
            }
        ],
    }


@app.get("/api/model_architecture")
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


@app.post("/api/complaints")
@app.post("/complaints")
def create_complaint(payload: ComplaintCreate):
    try:
        if not payload.full_name or not payload.full_name.strip():
            return {"status": "error", "error": "full_name is required", "complaint_id": None}

        if not payload.complaint_text or not payload.complaint_text.strip():
            return {"status": "error", "error": "complaint_text is required", "complaint_id": None}

        # Borough is required for the structured complaint intake flow.
        if not payload.borough or payload.borough.upper() == "UNKNOWN":
            return {"status": "error", "error": "borough is required", "complaint_id": None}

        # Location details are required for the structured complaint intake flow.
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

@app.get("/api/complaints_recent")
@app.get("/complaints_recent")
def complaints_recent():
    try:
        return {"status": "ok", "error": None, "items": list_recent_complaints(10)}
    except Exception as e:
        return {"status": "error", "error": f"Supabase fetch failed: {str(e)}", "items": []}

@app.post("/api/execute")
@app.post("/execute")
def execute(req: ExecuteRequest):
    """
    Course requirement:
    - Top-level response fields MUST be exactly: status, error, response, steps
    - steps[] logs the dynamic agent loop (module + prompt + response)
    - The agent chooses tools at runtime instead of following a fixed pipeline.
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

        agent_result = run_agent_loop(prompt_text, complaint=complaint, complaint_id=complaint_id)
        payload = {
            "status": agent_result["status"],
            "error": agent_result["error"],
            "response": agent_result["response"],
            "steps": agent_result["steps"],
        }
        if complaint_id:
            try:
                top_matches = agent_result.get("evidence", {}).get("top_cases", [])
                insert_execution(
                    {
                        "complaint_id": complaint_id,
                        "final_agency": agent_result["decision"].get("agency"),
                        "final_urgency": agent_result["decision"].get("urgency"),
                        "final_action": agent_result["decision"].get("action"),
                        "confidence": agent_result["decision"].get("confidence"),
                        "escalated": agent_result.get("needs_human_review", False),
                        "top_matches": top_matches,
                        "steps": agent_result["steps"],
                        "response_text": agent_result["response"],
                        "needs_review": agent_result.get("needs_review", False),
                        "needs_followup": agent_result.get("needs_followup", False),
                        "missing_fields": agent_result.get("missing_fields", []),
                    }
                )
                update_complaint_status(
                    complaint_id,
                    "needs_human" if agent_result.get("needs_human_review", False) else "processed",
                )
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
    html_path = os.path.join(static_dir, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()






