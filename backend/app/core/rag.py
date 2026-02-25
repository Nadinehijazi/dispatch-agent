import os
from typing import Any, Dict, List


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required .env var: {name}")
    return value


def _build_query_text(parsed: Dict[str, Any]) -> str:
    if parsed.get("complaint_text"):
        return str(parsed["complaint_text"])
    parts = []
    if parsed.get("category"):
        parts.append(f"category: {parsed['category']}")
    if parsed.get("location"):
        parts.append(f"location: {parsed['location']}")
    if parsed.get("time_24h"):
        parts.append(f"time: {parsed['time_24h']}")
    if parsed.get("recurrence"):
        parts.append(f"recurrence: {parsed['recurrence']}")
    return " | ".join(parts) if parts else "unknown complaint"


def _embed_texts(texts: List[str]) -> List[List[float]]:
    _load_dotenv()
    api_key = _require_env("LLMOD_API_KEY")
    base_url = _require_env("LLMOD_BASE_URL")
    model = _require_env("EMBEDDING_MODEL")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def retrieve_similar_cases(parsed: Dict[str, Any], top_k: int = 3) -> List[Dict[str, Any]]:
    _load_dotenv()
    api_key = _require_env("PINECONE_API_KEY")
    index_name = _require_env("PINECONE_INDEX_NAME")
    host = os.getenv("PINECONE_HOST")

    from pinecone import Pinecone

    query_text = _build_query_text(parsed)
    vector = _embed_texts([query_text])[0]

    pc = Pinecone(api_key=api_key)
    index = pc.Index(host=host) if host else pc.Index(index_name)

    filters = {}
    if parsed.get("borough"):
        filters["borough"] = {"$eq": parsed["borough"]}
    if parsed.get("status"):
        filters["status"] = {"$eq": parsed["status"]}
    else:
        filters["status"] = {"$eq": "Closed"}

    query_kwargs = {
        "vector": vector,
        "top_k": top_k,
        "include_metadata": True,
    }
    if filters:
        query_kwargs["filter"] = filters

    result = index.query(**query_kwargs)

    cases = []
    for match in result.matches or []:
        cases.append(
            {
                "id": match.id,
                "score": match.score,
                "metadata": match.metadata or {},
            }
        )
    return cases


def summarize_evidence(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    agencies = {}
    for c in cases:
        agency = (c.get("metadata") or {}).get("agency")
        if agency:
            agencies[agency] = agencies.get(agency, 0) + 1

    top_cases = []
    top_score = None
    for c in cases:
        meta = c.get("metadata") or {}
        score = c.get("score")
        if score is not None:
            top_score = score if top_score is None else max(top_score, score)
        top_cases.append(
            {
                "id": c.get("id"),
                "score": c.get("score"),
                "agency": meta.get("agency"),
                "complaint_type": meta.get("complaint_type"),
                "descriptor": meta.get("descriptor"),
                "status": meta.get("status"),
                "created_date": meta.get("created_date"),
            }
        )

    summary = "No similar cases found." if not cases else "Retrieved similar historical cases from Pinecone."
    if agencies:
        summary += f" Top agencies: {', '.join(sorted(agencies.keys()))}."

    return {
        "top_cases": top_cases,
        "evidence_summary": summary,
        "agency_counts": agencies,
        "total_matches": len(cases),
        "top_score": top_score,
    }
