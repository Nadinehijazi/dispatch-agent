# Dispatch AI Agent

AI-powered NYC 311 complaint triage assistant that produces operational decisions (agency, urgency, action) from complaint text using deterministic preprocessing, retrieval from historical cases, and a gated LLM disambiguation step.

## Quick Demo

![Dispatch AI Agent Demo](./assets/quick_demo.gif)
Full HD demo video: [assets/quick_demo.mp4](./assets/quick_demo.mp4)

## Why This Agent

- Structured modular pipeline instead of a single opaque model call
- Retrieval-grounded evidence from Pinecone
- Confidence gating with human review escalation
- Cost-aware design: LLM is called only when needed
- Auditable API outputs and execution records

## Required API Endpoints

- `GET /api/team_info`
- `GET /api/agent_info`
- `GET /api/model_architecture`
- `POST /api/execute`

Also available as backward-compatible aliases without `/api`.

## Agent Architecture

High-level modules:

- `Preprocessing_ContextExtraction`
- `Reason_UnderstandComplaint`
- `Act_RAG_RetrieveSimilarCases`
- `Observe_SummarizeEvidence`
- `Decide_DispatchDecision`
- `LLM_Disambiguation` (optional, gated)
- `Confidence_Gating`
- `Human_Review_Escalation`
- `Response_Generator`

Execution flow:

```text
Input_Complaint
  -> Preprocessing_ContextExtraction
  -> Reason_UnderstandComplaint
  -> Act_RAG_RetrieveSimilarCases
  -> Observe_SummarizeEvidence
  -> Decide_DispatchDecision
  -> [Low confidence or missing critical info?]
       Yes -> LLM_Disambiguation -> Confidence_Gating
       No  ---------------------> Confidence_Gating
  -> Human_Review_Escalation
  -> Response_Generator
  -> API_Output
```

## `/api/execute` Output Contract

Top-level response fields:

```json
{
  "status": "ok",
  "error": null,
  "response": "...",
  "steps": []
}
```

Error format:

```json
{
  "status": "error",
  "error": "Human-readable error",
  "response": null,
  "steps": []
}
```

`steps[]` semantics in this implementation:

- Includes actual LLM calls only
- Deterministic and retrieval steps are not included in `steps[]`
- `steps` may be empty for straightforward cases
- When invoked, `LLM_Disambiguation` appears with `module`, `prompt`, and `response`

## Tech Stack

- FastAPI (`backend/app/main.py`)
- Pinecone retrieval (`backend/app/core/rag.py`)
- LLM disambiguation (`backend/app/core/llm_decider.py`)
- Rule-based decision logic (`backend/app/core/decision.py`, `backend/app/core/preprocessing.py`)
- Supabase persistence (`backend/app/core/supabase_client.py`)
- Static frontend served by FastAPI (`index.html`, `style.css`, `app.js`, `logo.png`)

## Project Structure

```text
dispatch-agent/
|- backend/
|  |- app/
|  |  |- main.py
|  |  |- model_architecture.png
|  |  |- core/
|  |  |  |- preprocessing.py
|  |  |  |- rag.py
|  |  |  |- decision.py
|  |  |  |- llm_decider.py
|  |  |  |- formatting.py
|  |  |  |- supabase_client.py
|- index.html
|- style.css
|- app.js
|- logo.png
|- examples/
|- scripts/
|- data/
|- assets/
|- .env.example
|- requirements.txt
|- README.md
```

## Local Setup

Prerequisites:

- Python 3.10+
- Pinecone index and API key
- LLMOD API key
- Supabase project/tables

Install:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Open:

- App UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

## Environment Variables

Required in production:

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
- `PINECONE_HOST` (recommended)

Optional / currently unused by runtime code:

- `SUPABASE_ANON_KEY`
- `PINECONE_CLOUD`
- `PINECONE_REGION`

## Deploy on Render

Create a **Web Service** and use:

- Build command:
  - `pip install -r requirements.txt`
- Start command:
  - `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`

Then add the required environment variables above, deploy, and verify:

- `/`
- `/docs`
- `/api/team_info`
- `/api/agent_info`
- `/api/model_architecture`
- `/api/execute` (POST via docs)
