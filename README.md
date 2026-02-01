# Dispatch AI Agent (NYC 311 Triage)

Production-style NYC 311 complaint triage agent using a ReAct pipeline, Pinecone RAG, and LLMod.ai (OpenAI-compatible) embeddings. The system logs every step, gates low-confidence cases to human review, and stores complaints/executions in Supabase.

## Highlights

- FastAPI backend with required endpoints and strict response schema
- ReAct-style modules with full trace logging
- Real Pinecone retrieval (no fake cases)
- Evidence-driven decision + confidence gating
- Supabase as primary database (complaints + executions)
- Civic UI for citizen intake + transparency

## Architecture modules (canonical)

- Preprocessing_ContextExtraction
- Reason_UnderstandComplaint
- Act_RAG_RetrieveSimilarCases
- Observe_SummarizeEvidence
- Decide_DispatchDecision
- Confidence_Gating
- Human_Review_Escalation
- Response_Generator

## Required API endpoints

- GET `/api/team_info`
- GET `/api/agent_info`
- GET `/api/model_architecture` (PNG)
- POST `/api/execute` (main entry point)
- POST `/api/complaints` (structured intake)
- GET `/api/complaints_recent` (history)

## Supabase setup (primary database)

1) Create a Supabase project.
2) Run the schema SQL in the Supabase SQL editor:

```
scripts/supabase_schema.sql
```

3) Set environment variables (copy `.env.example` to `.env`):

```
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_COMPLAINTS_TABLE=complaints
SUPABASE_EXECUTIONS_TABLE=executions
```

Note: the service role key is server-only. Never expose it in the browser.

## Pinecone + embeddings

- Complaint embeddings are created from:
  `complaint_type | descriptor | location_type | borough`
- Metadata stored in Pinecone (no PII):
  `agency, complaint_type, descriptor, borough, created_date, status, open_data_channel_type`

Embedding + upsert pipeline:
```
backend\.venv\Scripts\python.exe scripts\embed_311_openai_compat.py --limit 2000
backend\.venv\Scripts\python.exe scripts\pinecone_upsert.py
```

## Required env vars

```
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=nyc-311-dispatch
PINECONE_HOST=...
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
LLMOD_API_KEY=...
LLMOD_BASE_URL=https://api.llmod.ai
EMBEDDING_MODEL=RPRTHPB-text-embedding-3-small
CHAT_MODEL=RPRTHPB-gpt-5-mini
```

## Run locally

```
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Open:
- `http://127.0.0.1:8000/` (citizen-facing UI)
- `http://127.0.0.1:8000/api/execute` (API)

## End-to-end flow

1) UI submits complaint -> `POST /api/complaints` (stored in Supabase).
2) UI calls `POST /api/execute` with `complaint_id`.
3) Agent runs RAG and returns decision + steps.
4) Execution is stored in Supabase and complaint status updated.

## Quick test

```
backend\.venv\Scripts\python.exe scripts\sanity_execute.py
```

## Deployment

Target: Render. Set all env vars in Render dashboard and deploy `backend.app.main:app`.
