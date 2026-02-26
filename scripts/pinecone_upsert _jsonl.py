import argparse
import json
import os
import time
from typing import List, Dict, Any

def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

def require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise ValueError(f"Missing required env var: {name}")
    return v

def batched(items: List[Any], batch_size: int):
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]

def read_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Bad JSON on line {line_no}: {e}") from e

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonl", required=True, help="Path to embeddings JSONL")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-retries", type=int, default=5)
    args = parser.parse_args()

    load_dotenv()

    pinecone_api_key = require_env("PINECONE_API_KEY")
    index_name = require_env("PINECONE_INDEX_NAME")

    # pip install pinecone
    from pinecone import Pinecone

    pc = Pinecone(api_key=pinecone_api_key)
    index = pc.Index(index_name)

    batch: List[Dict[str, Any]] = []
    uploaded = 0

    for rec in read_jsonl(args.jsonl):
        # minimal validation
        if "id" not in rec or "values" not in rec:
            continue
        batch.append({
            "id": str(rec["id"]),
            "values": rec["values"],
            "metadata": rec.get("metadata", {})
        })

        if len(batch) >= args.batch_size:
            for attempt in range(args.max_retries):
                try:
                    index.upsert(vectors=batch, namespace=args.namespace)
                    uploaded += len(batch)
                    print(f"Upserted {uploaded} vectors...")
                    batch = []
                    break
                except Exception as e:
                    wait = 2 ** attempt
                    print(f"Upsert failed (attempt {attempt+1}/{args.max_retries}): {e}")
                    print(f"Retrying in {wait}s...")
                    time.sleep(wait)
            else:
                raise RuntimeError("Upsert failed too many times.")

    # flush remainder
    if batch:
        index.upsert(vectors=batch, namespace=args.namespace)
        uploaded += len(batch)
        print(f"Upserted {uploaded} vectors total.")

if __name__ == "__main__":
    main()