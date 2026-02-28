import os
from typing import Any, Dict, List, Optional

import requests


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


def _client_config() -> Dict[str, str]:
    _load_dotenv()
    url = _require_env("SUPABASE_URL")
    key = _require_env("SUPABASE_SERVICE_ROLE_KEY")
    complaints_table = os.getenv("SUPABASE_COMPLAINTS_TABLE", "complaints")
    executions_table = os.getenv("SUPABASE_EXECUTIONS_TABLE", "executions")
    return {
        "url": url.rstrip("/"),
        "key": key,
        "complaints_table": complaints_table,
        "executions_table": executions_table,
    }


def _headers(api_key: str) -> Dict[str, str]:
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def insert_complaint(payload: Dict[str, Any]) -> str:
    cfg = _client_config()
    endpoint = f"{cfg['url']}/rest/v1/{cfg['complaints_table']}"
    resp = requests.post(endpoint, headers=_headers(cfg["key"]), json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data or "id" not in data[0]:
        raise RuntimeError("Supabase insert_complaint did not return id")
    return data[0]["id"]


def fetch_complaint(complaint_id: str) -> Optional[Dict[str, Any]]:
    cfg = _client_config()
    endpoint = f"{cfg['url']}/rest/v1/{cfg['complaints_table']}"
    params = {"id": f"eq.{complaint_id}", "limit": "1"}
    resp = requests.get(endpoint, headers=_headers(cfg["key"]), params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data[0] if data else None


def update_complaint_status(complaint_id: str, status: str) -> None:
    cfg = _client_config()
    endpoint = f"{cfg['url']}/rest/v1/{cfg['complaints_table']}"
    params = {"id": f"eq.{complaint_id}"}
    resp = requests.patch(
        endpoint,
        headers=_headers(cfg["key"]),
        params=params,
        json={"status": status},
        timeout=10,
    )
    resp.raise_for_status()


def insert_execution(payload: Dict[str, Any]) -> str:
    cfg = _client_config()
    endpoint = f"{cfg['url']}/rest/v1/{cfg['executions_table']}"
    resp = requests.post(endpoint, headers=_headers(cfg["key"]), json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data or "id" not in data[0]:
        raise RuntimeError("Supabase insert_execution did not return id")
    return data[0]["id"]


def list_recent_complaints(limit: int = 10) -> List[Dict[str, Any]]:
    cfg = _client_config()
    endpoint = f"{cfg['url']}/rest/v1/{cfg['complaints_table']}"
    params = {
        "select": "id,created_at,full_name,complaint_text,borough,status",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    resp = requests.get(endpoint, headers=_headers(cfg["key"]), params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()
