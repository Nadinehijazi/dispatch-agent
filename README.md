# Dispatch AI Agent

Dispatch AI Agent is a FastAPI-based autonomous triage system for municipal complaints (311-style intake).  
It ingests citizen reports, retrieves similar historical cases from Pinecone, and returns a structured dispatch recommendation with confidence and escalation signals.  
The architecture combines deterministic extraction, retrieval-grounded reasoning, and optional gated LLM disambiguation for ambiguous cases.  
Each run returns a full execution trace and can be persisted in Supabase for audit.

## Why This Is an AI Agent 🧠

This system follows a structured reasoning pipeline inspired by ReAct (`reason -> act -> observe -> decide`), not a single prompt-response chatbot.

Specialized agents/modules:
- Preprocessing Agent (`Preprocessing_ContextExtraction`) for signal extraction
- Reasoning Agent (`Reason_UnderstandComplaint`) for intent and missing-information analysis
- Retrieval Agent (`Act_RAG_RetrieveSimilarCases`) for Pinecone search
- Observation Agent (`Observe_SummarizeEvidence`) for evidence summarization
- Policy Agent (`Decide_DispatchDecision`) for recommendation and confidence
- Safety Agents (`Confidence_Gating`, `Human_Review_Escalation`) for escalation control
- Response Agent (`Response_Generator`) for user-facing output formatting

## Quick Demo 🎬

<p>
  <a href="./assets/Dispatch%20Agent.mp4">
    <img src="./backend/app/static/logo.png" alt="Dispatch AI Agent Demo" width="1100" />
  </a>
</p>

<p><sub>Click the image to open the demo video.</sub></p>

Example complaint:

```text
Water leaking from hydrant in Brooklyn.
```

Output structure:
- Agency: `<predicted agency>`
- Urgency: `<low|medium|high>`
- Action: `<recommended action>`
- Confidence: `<0.00-1.00>`
- Escalation: `<true|false>`

The trace section can be expanded to inspect step-by-step module reasoning (`module`, `prompt`, `response`).

## Problem Statement 🏙️

Municipal complaint triage is often manual, inconsistent, and difficult to audit.  
Complaints arrive as unstructured text and may be incomplete, ambiguous, or urgent.

This project addresses that by:
- standardizing triage outputs,
- grounding decisions in retrieval evidence,
- exposing uncertainty via confidence and escalation.

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

- Complaint intake:
  - `POST /api/complaints` stores structured complaint data in Supabase.
- Retrieval:
  - `backend/app/core/rag.py` embeds complaint query text and retrieves top Pinecone matches with metadata filters.
- Reasoning and decision:
  - deterministic logic in `backend/app/core/preprocessing.py` and `backend/app/core/decision.py`,
  - optional gated refinement in `backend/app/core/llm_decider.py`.
- Human escalation:
  - `Confidence_Gating` + `Human_Review_Escalation` mark low-confidence or missing-field runs.
- Execution trace:
  - returned in `/api/execute` as `steps`,
  - persisted in Supabase `executions.steps` for complaint-linked runs.

Backend/frontend implementation:
- Backend: FastAPI (`backend/app/main.py`)
- Frontend: static HTML/CSS/JS served by FastAPI (`backend/app/static/`)

## Features ✨

Implemented features only:
- Structured complaint submission (`/api/complaints`)
- Main execution endpoint with strict response schema (`/api/execute`)
- ReAct-style traceable module pipeline
- Pinecone-based retrieval with evidence summary
- Deterministic draft decision + confidence scoring
- Optional LLM disambiguation under gating conditions
- Human escalation signaling (`needs_human_review`, follow-up context)
- UI visibility of decision, confidence, escalation banner, and trace steps
- Auditability through complaint IDs, timestamps, and Supabase execution records

## Example Execution Flow 🔄

1. User submits complaint in UI (`POST /api/complaints`) and receives `complaint_id`.
2. UI calls `POST /api/execute` with `complaint_id` (or direct `prompt` in quick-run mode).
3. Agent runs preprocessing, retrieval, evidence observation, decision, and gating.
4. API returns:
   - `response` (human-readable dispatch output)
   - `steps` (full module-level trace)
5. For complaint-linked runs, execution metadata and trace are stored in Supabase.
6. If confidence is low or required fields are missing, escalation flags are set and surfaced in UI.

### Concrete Scenario: Ambiguous Complaint

Input:

```text
There is a bad smell near my building.
```

Behavior:
- Retrieval is triggered to search similar historical cases.
- Evidence may be weak/conflicting, reducing confidence.
- Confidence gating can mark the run for escalation.
- Human review safeguard activates instead of overconfident routing.

## Design Decisions ⚙️

- Single-page UI:
  - chosen for fast intake-to-decision workflow in demos/grading.
- Collapsed trace by default:
  - keeps UI readable while preserving transparency.
- Explicit escalation banner:
  - makes uncertain outcomes visible and actionable.
- Complaint-linked execution persistence:
  - keeps decision + trace auditable per complaint.
- Tradeoff vs multi-page workflow:
  - simpler and faster, but not a full dispatcher operations console.

## Reliability and Safeguards 🛡️

Current safeguards:
- strict `/api/execute` response contract (`status,error,response,steps`)
- deterministic base path (preprocessing + policy)
- retrieval evidence signals (`agency_counts`, `top_score`, `total_matches`)
- confidence gating + explicit human escalation
- Supabase persistence for audit

Validation scripts:
- `scripts/sanity_execute.py` for API contract checks
- `scripts/eval_routing.py` for retrieval/routing sanity checks
- `scripts/check_pinecone.py` and related scripts for vector DB verification

Failure handling:
- endpoint-level error mode (`status="error"` with readable `error`)
- retrieval/LLM path can fail or skip without silent success
- escalation path remains available for uncertain decisions

## Installation and Setup 🧩

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

If your branch does not include a pinned requirements file, install packages used by code:

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

Run:

```text
scripts/supabase_schema.sql
```

### 6) Start FastAPI locally

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
│     ├─ model_architecture.png     # Architecture image endpoint asset
│     ├─ core/
│     │  ├─ preprocessing.py        # Signal extraction, category, urgency heuristics
│     │  ├─ rag.py                  # Embedding call + Pinecone retrieval + evidence summary
│     │  ├─ decision.py             # Rule/policy decision logic and confidence handling
│     │  ├─ llm_decider.py          # Gated LLM refinement
│     │  ├─ formatting.py           # Final response formatting
│     │  └─ supabase_client.py      # Supabase persistence access layer
│     └─ static/
│        ├─ index.html              # Single-page UI
│        ├─ style.css               # UI styling
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
├─ assets/
│  └─ Dispatch Agent.mp4
├─ .env.example
└─ README.md
```

## Limitations and Future Improvements 🚧

Current limitations:
- no authentication/authorization
- no dedicated multi-operator dashboard
- no queue/assignment workflow
- no background worker for heavy ingestion/reindex tasks
- dependencies not pinned in lockfile/requirements
- limited automated test coverage

Next improvements:
- operator queue and assignment UI
- role-based access and audit permissions
- background task processing for ingestion and indexing
- expanded regression suite for retrieval and decision quality
- production observability (metrics, tracing, retries)
