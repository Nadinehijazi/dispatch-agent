# Dispatch AI Agent 🤖

Dispatch AI Agent is a FastAPI-based autonomous triage system for municipal complaints (311-style intake).  
It ingests citizen reports, retrieves similar historical cases from Pinecone, and produces a structured dispatch recommendation with confidence and escalation signals.  
The architecture is interesting because it combines deterministic extraction, retrieval-grounded reasoning, and optional LLM disambiguation under gating conditions.  
Each run returns a full execution trace and can be persisted for audit in Supabase.

## Why This Is an AI Agent 🧠

This system is implemented as a structured reasoning pipeline inspired by ReAct (`reason -> act -> observe -> decide`), not as a single prompt-response chatbot.

Operationally, the pipeline is divided into specialized agents/modules:
- Preprocessing Agent (`Preprocessing_ContextExtraction`) for signal extraction
- Reasoning Agent (`Reason_UnderstandComplaint`) for intent and missing-information analysis
- Retrieval Agent (`Act_RAG_RetrieveSimilarCases`) for Pinecone search
- Observation Agent (`Observe_SummarizeEvidence`) for evidence summarization
- Policy Agent (`Decide_DispatchDecision`) for recommendation and confidence
- Safety Agents (`Confidence_Gating`, `Human_Review_Escalation`) for escalation control
- Response Agent (`Response_Generator`) for user-facing output formatting

## Quick Demo 🎬

Example complaint:

```text
"Water leaking from hydrant in Brooklyn."
```

System output structure:
- Agency: `<predicted agency>`
- Urgency: `<low|medium|high>`
- Action: `<recommended dispatch action>`
- Confidence: `<0.00-1.00>`
- Escalation: `<true|false>`

The trace panel can be expanded to inspect the full reasoning path (`module`, `prompt`, `response`) for each step.  
A screenshot or demo GIF can be inserted here later.

## Problem Statement 🏙️

Municipal complaint triage is often manual, inconsistent, and hard to audit.  
Free-text reports may be incomplete, ambiguous, or operationally urgent.

This project addresses that by:
- standardizing triage decisions,
- grounding recommendations in historical retrieval evidence,
- exposing uncertainty explicitly through confidence and escalation.

## Architecture 🏗️

### System Diagram

```text
[Static Frontend (single page)]
        |
        v
[FastAPI /api/complaints] ---> [Supabase complaints table]
        |
        v
[FastAPI /api/execute]
   1) Preprocessing_ContextExtraction
   2) Reason_UnderstandComplaint
   3) Act_RAG_RetrieveSimilarCases ---> [LLMod embeddings] ---> [Pinecone]
   4) Observe_SummarizeEvidence
   5) Decide_DispatchDecision
   6) Confidence_Gating
   7) Human_Review_Escalation
   8) Response_Generator
        |
        +--> API response {status,error,response,steps}
        +--> Supabase executions table (complaint-linked runs)
```

### Component Explanation

- Complaint Intake:
  - `POST /api/complaints` stores structured complaint data in Supabase.
- Retrieval:
  - `backend/app/core/rag.py` embeds complaint query text and retrieves top Pinecone matches with metadata filters.
- Reasoning and Decision:
  - deterministic extraction and policy logic in `preprocessing.py` and `decision.py`,
  - optional gated refinement in `llm_decider.py`.
- Escalation:
  - confidence gating and missing-field checks trigger human review flags.
- Trace:
  - full step trace is returned in `/api/execute` and persisted in Supabase execution records.

Backend/frontend implementation:
- Backend: FastAPI (`backend/app/main.py`)
- Frontend: static HTML/CSS/JS served by FastAPI (`backend/app/static/`)

## Features ✨

Implemented features only:
- Structured complaint intake with persisted `complaint_id`
- Main execution endpoint with strict response contract: `status`, `error`, `response`, `steps`
- ReAct-style traceable module pipeline
- Retrieval-Augmented Generation with Pinecone-backed evidence
- Deterministic base decision policy with confidence scoring
- Optional LLM disambiguation under explicit gating conditions
- Human escalation signaling (`needs_human_review`, follow-up/missing-field context)
- Audit visibility in UI (decision card, confidence, escalation banner, trace, recent complaints)
- Supabase persistence for complaints and executions

## Example Execution Flow 🔄

1. User submits complaint in UI via `POST /api/complaints`.
2. UI receives `complaint_id` and calls `POST /api/execute`.
3. Agent runs extraction, retrieval, evidence observation, decision, and gating.
4. API returns decision text plus complete `steps[]`.
5. Execution metadata and trace are written to Supabase (for complaint-linked runs).
6. If confidence is low or critical fields are missing, escalation is surfaced in trace and UI.

### Concrete Scenario: Ambiguous Complaint

Input:

```text
"There’s a bad smell near my building."
```

Behavior:
- Retrieval is still triggered to look for similar historical patterns.
- Evidence may be weak or conflicting, so confidence can drop.
- Confidence gating can mark the run for escalation.
- Human review safeguard activates, preventing silent overconfident routing.

## Design Decisions ⚙️

- Single-page UI:
  - chosen to keep intake-to-decision interaction fast for demo, grading, and operator review.
- Collapsed trace by default:
  - preserves clarity for non-technical users while keeping technical transparency one click away.
- Explicit escalation banner:
  - makes uncertain outcomes operationally visible and actionable.
- Complaint-linked execution persistence:
  - keeps decision, trace, and escalation context auditable per complaint.
- Tradeoff vs multi-page workflow:
  - simpler and faster to operate, but not yet a full dispatcher operations console.

## Reliability & Safeguards 🛡️

Current safeguards:
- strict `/api/execute` schema contract
- deterministic base path (preprocessing + policy) even if optional services are unavailable
- retrieval evidence summarization (`agency_counts`, `top_score`, `total_matches`)
- confidence gating + explicit human escalation
- traceability in API response and persisted Supabase execution record

Validation scripts included:
- `scripts/sanity_execute.py` for API contract checks
- `scripts/eval_routing.py` for retrieval/routing sanity evaluation
- `scripts/check_pinecone.py` and related utilities for vector DB validation

Failure handling:
- endpoint-level error mode (`status="error"` with readable error message)
- retrieval/LLM path can be skipped or errored without silent success
- escalation path remains available for uncertain outputs

## Installation & Setup 🧩

### 1) Clone repository

```bash
git clone https://github.com/<your-user>/dispatch-agent.git
cd dispatch-agent
```

### 2) Create and activate virtual environment

Windows PowerShell:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
```

### 3) Install dependencies

If your branch does not include a pinned requirements file, install the packages used by the code:

```powershell
pip install fastapi uvicorn pydantic requests pandas openai pinecone python-dotenv certifi
```

### 4) Configure environment variables

Copy `.env.example` to `.env`, then set real values:

```env
# Pinecone
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=nyc-311-dispatch
PINECONE_HOST=...
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

# LLMod (OpenAI-compatible)
LLMOD_API_KEY=...
LLMOD_BASE_URL=https://api.llmod.ai
EMBEDDING_MODEL=RPRTHPB-text-embedding-3-small
CHAT_MODEL=RPRTHPB-gpt-5-mini

# Supabase
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_COMPLAINTS_TABLE=complaints
SUPABASE_EXECUTIONS_TABLE=executions
```

### 5) Create Supabase schema

Execute:

```text
scripts/supabase_schema.sql
```

### 6) Run FastAPI locally

```powershell
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Access:
- App UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

## Project Structure 📂

```text
dispatch-agent/
├─ backend/
│  └─ app/
│     ├─ main.py                    # FastAPI routes and orchestration
│     ├─ model_architecture.png     # Architecture image served by endpoint
│     ├─ core/
│     │  ├─ preprocessing.py        # Signal extraction, categorization, urgency heuristics
│     │  ├─ rag.py                  # Embedding call + Pinecone retrieval + evidence summary
│     │  ├─ decision.py             # Rule/policy decision logic and confidence handling
│     │  ├─ llm_decider.py          # Gated LLM refinement
│     │  ├─ formatting.py           # Final response formatting
│     │  └─ supabase_client.py      # Supabase persistence access layer
│     └─ static/
│        ├─ index.html              # Single-page UI
│        ├─ style.css               # UI styles
│        ├─ app.js                  # Submission, execution, and trace rendering flow
│        └─ logo.png
├─ scripts/
│  ├─ download_311_data.py
│  ├─ clean_311_data.py
│  ├─ embed_311_openai_compat.py
│  ├─ pinecone_upsert.py
│  ├─ eval_routing.py
│  ├─ sanity_execute.py
│  └─ supabase_schema.sql
├─ data/
├─ .env.example
└─ README.md
```

## Limitations & Future Improvements 🚧

Current limitations:
- no authentication/authorization
- no dedicated multi-operator dashboard
- no queueing/assignment workflow
- no background worker for heavy ingestion/reindex tasks
- dependency installation is not pinned in a lockfile
- limited automated test coverage

Realistic next improvements:
- operator queue and assignment UI
- role-based access and audit permissions
- background task processing for ingestion and indexing
- expanded regression suite for decision and retrieval quality
- production observability (metrics, tracing, retry policies)
