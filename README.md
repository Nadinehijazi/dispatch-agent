# Dispatch AI Agent

Dispatch AI Agent is an NYC 311 complaint triage system implemented as a ReAct agent. Given a citizen complaint, the agent iterates through Thought -> Action -> Observation cycles and decides what to do next: parse the complaint, retrieve similar historical cases, ask for missing information, run LLM disambiguation, escalate immediately, or finalize a dispatch decision.


## What The Agent Does

- Accepts a free-text municipal complaint
- Extracts structured signals such as category, location, recurrence, and time
- Decides dynamically which tool to use next
- Produces an operational dispatch decision:
  - agency
  - urgency
  - recommended action
  - justification
  - confidence
- Escalates uncertain cases for human review

## Why This Is A ReAct Agent

- The control flow is dynamic. The agent does not follow one mandatory sequence for every complaint.
- The next action is chosen at runtime from an explicit action space.
- Retrieval is a tool, not a required stage.
- The agent can stop early for emergencies and irrelevant requests.
- Ambiguous cases can trigger retrieval, then another reasoning step, then LLM disambiguation or finalization.
- The execution trace records Thought, Action, and Observation cycles directly.

## Core Action Space

- `PARSE_COMPLAINT`
- `EMERGENCY_ESCALATE`
- `RETRIEVE_SIMILAR_CASES`
- `ASK_FOR_MISSING_INFO`
- `RUN_LLM_DISAMBIGUATION`
- `SKIP_RETRIEVAL`
- `MARK_IRRELEVANT`
- `FINALIZE_DECISION`

## Architecture

High-level modules:

- `Preprocessing_ContextExtraction`
- `Reason_UnderstandComplaint`
- `Agent_Thought`
- `Agent_Action`
- `Agent_Observation`
- `Act_RAG_RetrieveSimilarCases`
- `Observe_SummarizeEvidence`
- `Decide_DispatchDecision`
- `LLM_Disambiguation`
- `Confidence_Gating`
- `Human_Review_Escalation`
- `Final_Decision`
- `Response_Generator`

ReAct loop:

```text
Input Complaint
  -> Agent_Thought
  -> Agent_Action
  -> Agent_Observation
  -> [Continue?]
       Yes -> Agent_Thought -> Agent_Action -> Agent_Observation -> ...
       No  -> Final_Decision -> Confidence_Gating -> Human_Review_Escalation -> Response_Generator
```

Planner behavior:

- Deterministic guardrails handle hard constraints first:
  - obvious emergency
  - irrelevant / out-of-scope request
- An LLM-assisted planner can choose the next action in ambiguous states
- A deterministic fallback planner is used if the planner LLM is unavailable or fails

Architecture as text:

```text
Citizen Complaint / complaint_id
        |
        v
  Agent_Thought
    - inspect current state
    - apply emergency / irrelevant guardrails
    - use LLM planner only for ambiguous next-step choice
        |
        v
   choose one action
        |
        +--> PARSE_COMPLAINT
        |      -> preprocessing + baseline reasoning + draft decision
        |
        +--> RETRIEVE_SIMILAR_CASES
        |      -> Pinecone retrieval + evidence summary
        |
        +--> RUN_LLM_DISAMBIGUATION
        |      -> refine routing only when needed
        |
        +--> ASK_FOR_MISSING_INFO
        |      -> mark follow-up required
        |
        +--> EMERGENCY_ESCALATE / MARK_IRRELEVANT
        |      -> stop early
        |
        +--> SKIP_RETRIEVAL / FINALIZE_DECISION
               -> stop when enough evidence exists

After each action:
  Agent_Observation -> update state -> loop back to Agent_Thought

When finalized:
  Confidence_Gating -> Human_Review_Escalation -> Response_Generator
  -> API response {status, error, response, steps}
  -> Supabase execution record
```

The backend also exposes `GET /api/model_architecture` as a PNG rendering of this same architecture for course compatibility.

## Required API Endpoints

- `GET /api/team_info`
- `GET /api/agent_info`
- `GET /api/model_architecture`
- `POST /api/execute`

Additional complaint persistence endpoints are also exposed:

- `POST /api/complaints`
- `GET /api/complaints_recent`

Backward-compatible aliases without `/api` are exposed for the same handlers.

Structured complaint intake currently requires:

- `full_name`
- `complaint_text`
- `borough`
- `location_details`
- `consent = true`

## `/api/execute` Response Contract

Top-level schema:

```json
{
  "status": "ok",
  "error": null,
  "response": "...",
  "steps": []
}
```

Error schema:

```json
{
  "status": "error",
  "error": "Human-readable error",
  "response": null,
  "steps": []
}
```

`steps[]` semantics:

- Every loop iteration emits:
  - `Agent_Thought`
  - `Agent_Action`
  - `Agent_Observation`
- Deterministic tool steps are logged when used
- Retrieval and LLM steps appear only when the agent actually chooses them
- `Agent_Thought` includes:
  - the chosen action
  - reasoning mode
  - known facts
  - missing fields
  - ambiguity signals

Reasoning modes currently used:

- `guardrail`
- `llm_planner`
- `fallback_policy`
- `fallback_after_llm_error`

## Example Behaviors

Emergency case:

- Prompt: `Right now there is a strong gas smell from a manhole in Queens and two people feel dizzy.`
- Expected action path: `PARSE_COMPLAINT -> EMERGENCY_ESCALATE`

Straightforward noise case:

- Prompt: `There is a loud party with music every weekend at 2am in Brooklyn.`
- Expected action path: `PARSE_COMPLAINT -> SKIP_RETRIEVAL -> FINALIZE_DECISION`

Ambiguous sanitation / health case:

- Prompt: `Overflowing garbage bags have been left on the sidewalk outside 200 Atlantic Ave in Brooklyn for three days. Rats were seen near the trash.`
- Expected action path: `PARSE_COMPLAINT -> RETRIEVE_SIMILAR_CASES -> RUN_LLM_DISAMBIGUATION -> FINALIZE_DECISION`

Irrelevant case:

- Prompt: `Can you recommend a restaurant nearby?`
- Expected action path: `PARSE_COMPLAINT -> MARK_IRRELEVANT`

## Tech Stack

- FastAPI API layer: `backend/app/main.py`
- ReAct controller: `backend/app/core/agent_controller.py`
- Deterministic preprocessing: `backend/app/core/preprocessing.py`
- Deterministic decision logic: `backend/app/core/decision.py`
- Pinecone retrieval tool: `backend/app/core/rag.py`
- LLM planner and LLM disambiguation: `backend/app/core/llm_decider.py`
- Response formatting: `backend/app/core/formatting.py`
- Supabase persistence: `backend/app/core/supabase_client.py`

## Project Structure

```text
dispatch-agent/
|- backend/
|  |- app/
|  |  |- main.py
|  |  |- model_architecture.png
|  |  |- core/
|  |  |  |- agent_controller.py
|  |  |  |- decision.py
|  |  |  |- formatting.py
|  |  |  |- llm_decider.py
|  |  |  |- preprocessing.py
|  |  |  |- rag.py
|  |  |  |- supabase_client.py
|- scripts/
|  |- clean_311_data.py
|  |- download_311_data.py
|  |- embed_311_openai_compat.py
|  |- eval_routing.py
|  |- generate_model_architecture.py
|  |- pinecone_upsert.py
|  |- sanity_execute.py
|  |- supabase_schema.sql
|  |- verify_react_paths.py
|- data/
|- api/
|- app.js
|- index.html
|- logo.png
|- requirements.txt
|- style.css
|- vercel.json
|- .env.example
|- README.md
```

## Local Setup

Prerequisites:

- Python 3.10+
- Pinecone index and API key
- LLMod API key
- Supabase project and tables

Install:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.env` from `.env.example` and set:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_COMPLAINTS_TABLE`
- `SUPABASE_EXECUTIONS_TABLE`
- `LLMOD_API_KEY`
- `LLMOD_BASE_URL`
- `EMBEDDING_MODEL`
- `CHAT_MODEL`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`
- `PINECONE_HOST`

Run locally:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Open:

- App UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

## Verification

Schema sanity check:

```powershell
backend\.venv\Scripts\python.exe scripts\sanity_execute.py
```

ReAct path verification:

```powershell
backend\.venv\Scripts\python.exe scripts\verify_react_paths.py
```

What to check in `verify_react_paths.py` output:

- emergency case shows `EMERGENCY_ESCALATE`
- recurring noise shows `SKIP_RETRIEVAL`
- trash + rats shows retrieval and possibly LLM use
- irrelevant case shows `MARK_IRRELEVANT`
- ambiguous cases should show `reasoning_mode = llm_planner` when planner connectivity is available


## Notes

- The agent is intentionally hybrid rather than LLM-only.
- Deterministic guardrails remain in place for safety and cost control.
- Retrieval and LLM use are selective.
- If the planner LLM is unavailable, the trace explicitly records fallback reasoning rather than hiding it.
