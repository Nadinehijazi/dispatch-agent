# Dispatch AI Agent

Autonomous municipal complaint triage system (311-style) that converts unstructured citizen reports into structured dispatch decisions using retrieval-grounded reasoning, deterministic policy logic, and confidence-based human escalation.

## 🎬 Demo Video

![Dispatch AI Agent Demo](./assets/demo.gif)

## 🌟 Why Dispatch AI Agent

### Unique Advantages

- **Structured reasoning pipeline**: ReAct-style modular flow instead of a single opaque model call
- **Retrieval-grounded decisions**: Pinecone evidence is summarized and fed into policy logic
- **Operational safety controls**: confidence gating and explicit human escalation
- **Traceability by design**: every run returns detailed `steps[]` and can be persisted for audit

## 💡 Real-World Triage Scenarios

### Scenario 1: Recurring Noise Complaint

**Input**: "There is a loud party with shouting at 2am every weekend."  
**System behavior**: classifies `noise`, retrieves similar historical cases, recommends non-emergency routing.  
**Outcome**: medium urgency + repeat-handling action.

### Scenario 2: Hazard-Like Signal

**Input**: "Strong gas smell near a manhole and people feel dizzy."  
**System behavior**: classifies `safety`, applies high-risk urgency heuristics, surfaces emergency action.  
**Outcome**: immediate escalation-oriented action.

### Scenario 3: Ambiguous Odor Report

**Input**: "Bad smell near my building, source unknown."  
**System behavior**: retrieval runs, confidence may drop due to ambiguity/missing detail.  
**Outcome**: follow-up requirements + human review safeguard.

## 🎯 System Features

### Intake & API

- Structured complaint intake endpoint: `POST /api/complaints`
- Main execution endpoint with strict contract: `POST /api/execute`
- Required informational endpoints:
  - `GET /api/team_info`
  - `GET /api/agent_info`
  - `GET /api/model_architecture`

### Decisioning & Safety

- ReAct-style module pipeline with canonical module names
- Pinecone retrieval + evidence summarization (`agency_counts`, `top_score`, `total_matches`)
- Deterministic policy decision with confidence scoring
- Optional gated LLM disambiguation (`llm_decider.py`)
- Confidence gating and human escalation (`needs_human_review`, follow-up signals)

### UI & Auditability

- Single-page UI for intake, decision card, and trace inspection
- Expandable execution trace with module/prompt/response
- Complaint and execution persistence in Supabase
- Recent complaints view for quick operational context

## 🤖 Agent Architecture

Core modules:

- `Preprocessing_ContextExtraction`
- `Reason_UnderstandComplaint`
- `Act_RAG_RetrieveSimilarCases`
- `Observe_SummarizeEvidence`
- `Decide_DispatchDecision`
- `Confidence_Gating`
- `Human_Review_Escalation`
- `Response_Generator`

System diagram:

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

## 🔧 Technical Architecture

### Backend

- FastAPI application in `backend/app/main.py`
- Core orchestration and domain logic in `backend/app/core/`

### Retrieval Layer

- Pinecone vector search in `backend/app/core/rag.py`
- Query embeddings through LLMod OpenAI-compatible endpoint

### Persistence

- Supabase integration in `backend/app/core/supabase_client.py`
- Complaint and execution records persisted for audit

### Frontend

- Static UI served by FastAPI:
  - `backend/app/static/index.html`
  - `backend/app/static/style.css`
  - `backend/app/static/app.js`

## 📊 System Outputs

Primary decision output includes:
- Agency recommendation
- Urgency level
- Action plan
- Confidence score
- Escalation flag

Full execution trace includes:
- Module name
- Prompt payload
- Response payload

## 📁 Project Structure

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
|  |  |- static/
|  |  |  |- index.html
|  |  |  |- style.css
|  |  |  |- app.js
|  |  |  |- logo.png
|- scripts/
|  |- download_311_data.py
|  |- clean_311_data.py
|  |- embed_311_openai_compat.py
|  |- pinecone_upsert.py
|  |- eval_routing.py
|  |- sanity_execute.py
|  |- supabase_schema.sql
|- data/
|- assets/
|  |- Dispatch Agent.mp4
|- .env.example
|- README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+ recommended
- Pinecone account and index credentials
- LLMod API key
- Supabase project with required tables

### Installation

1. Clone repository:

```bash
git clone https://github.com/<your-user>/dispatch-agent.git
cd dispatch-agent
```

2. Create and activate virtual environment (Windows PowerShell):

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install fastapi uvicorn pydantic requests pandas openai pinecone python-dotenv certifi
```

4. Configure environment:

```powershell
copy .env.example .env
```

Set values in `.env`:

```env
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=nyc-311-dispatch
PINECONE_HOST=...
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

LLMOD_API_KEY=...
LLMOD_BASE_URL=https://api.llmod.ai
EMBEDDING_MODEL=RPRTHPB-text-embedding-3-small
CHAT_MODEL=RPRTHPB-gpt-5-mini

SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_COMPLAINTS_TABLE=complaints
SUPABASE_EXECUTIONS_TABLE=executions
```

5. Create Supabase schema:

```text
scripts/supabase_schema.sql
```

### Running Locally

```powershell
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Open:
- App UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

## 🛡 Reliability and Safeguards

- strict endpoint response contract
- deterministic baseline decisioning path
- retrieval evidence scoring and summarization
- confidence gating and explicit escalation
- execution trace visibility and Supabase persistence

Validation scripts:
- `scripts/sanity_execute.py`
- `scripts/eval_routing.py`
- `scripts/check_pinecone.py` and related helpers

## 🚧 Limitations and Future Improvements

Current limitations:
- no authentication/authorization
- no dedicated multi-operator dashboard
- no queue assignment workflow
- no background worker for large ingestion/reindex tasks
- dependencies not pinned in lockfile
- limited automated test coverage

Next improvements:
- operator queue and assignment interface
- role-based access and audit permissions
- async task processing for ingestion/indexing
- stronger regression/evaluation suite
- production observability (metrics, tracing, retry policies)
