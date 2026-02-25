import os
from typing import Any, Dict, List, Optional
from functools import lru_cache

# Optional: keep dotenv loader, but run only once
_DOTENV_LOADED = False


def _load_dotenv_once(path: str = ".env") -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
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


def _get_env(name: str) -> Optional[str]:
    _load_dotenv_once()
    v = os.getenv(name)
    return v if v and str(v).strip() else None


def rag_available() -> bool:
    """Return True if we can actually run RAG end-to-end."""
    return bool(_get_env("PINECONE_API_KEY") and _get_env("PINECONE_INDEX_NAME")
                and _get_env("LLMOD_API_KEY") and _get_env("LLMOD_BASE_URL") and _get_env("EMBEDDING_MODEL"))


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


@lru_cache(maxsize=256)
def _embed_one(text: str) -> List[float]:
    """Cache embeddings so repeated tests don't burn budget."""
    api_key = _get_env("LLMOD_API_KEY")
    base_url = _get_env("LLMOD_BASE_URL")
    model = _get_env("EMBEDDING_MODEL")
    if not (api_key and base_url and model):
        raise ValueError("Embeddings unavailable: missing LLMOD_* env vars")

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.embeddings.create(model=model, input=[text])
    return resp.data[0].embedding


def retrieve_similar_cases(parsed: Dict[str, Any], top_k: int = 3) -> Dict[str, Any]:
    """
    Returns:
      {"ok": True, "cases": [...]} OR {"ok": False, "cases": [], "error": "...", "skipped": True}
    """
    api_key = _get_env("PINECONE_API_KEY")
    index_name = _get_env("PINECONE_INDEX_NAME")
    host = _get_env("PINECONE_HOST")

    # If missing config: skip gracefully
    if not api_key or not index_name:
        return {"ok": False, "skipped": True, "cases": [], "error": "Pinecone not configured"}

    try:
        query_text = _build_query_text(parsed)
        vector = _embed_one(query_text)

        from pinecone import Pinecone
        pc = Pinecone(api_key=api_key)
        index = pc.Index(host=host) if host else pc.Index(index_name)

        filters = {}
        if parsed.get("borough"):
            filters["borough"] = {"$eq": parsed["borough"]}
        # default status filter
        filters["status"] = {"$eq": parsed.get("status") or "Closed"}

        query_kwargs = {"vector": vector, "top_k": top_k, "include_metadata": True}
        if filters:
            query_kwargs["filter"] = filters

        result = index.query(**query_kwargs)

        cases = []
        for match in result.matches or []:
            cases.append({"id": match.id, "score": match.score, "metadata": match.metadata or {}})

        return {"ok": True, "cases": cases}
    except Exception as e:
        # Don't crash the whole agent; return error inside response
        return {"ok": False, "skipped": False, "cases": [], "error": str(e)}


def summarize_evidence(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    agencies: Dict[str, int] = {}
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