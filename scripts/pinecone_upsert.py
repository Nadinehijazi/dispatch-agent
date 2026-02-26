import argparse
import json
import os
from typing import Iterable, List, Dict, Set

DEFAULT_VECTORS = "data/nyc_311_embeddings_llmod.jsonl"
DEFAULT_MANIFEST = "data/nyc_311_embeddings_llmod_manifest.json"


def load_dotenv(path: str = ".env") -> None:
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


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required .env var: {name}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Pinecone index (if missing) and upsert JSONL vectors safely.",
    )
    parser.add_argument("--vectors", default=DEFAULT_VECTORS)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--preflight-sample", type=int, default=500,
                        help="How many IDs to check with fetch() before upsert. 0 = skip preflight.")
    parser.add_argument("--skip-existing", action="store_true",
                        help="If set, do NOT upsert vectors whose IDs already exist in Pinecone.")
    return parser.parse_args()


def read_jsonl(path: str) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def ensure_index(pc, index_name: str, dimension: int) -> None:
    existing = {idx["name"] for idx in pc.list_indexes().get("indexes", [])}
    if index_name in existing:
        return

    host = os.getenv("PINECONE_HOST")
    cloud = os.getenv("PINECONE_CLOUD")
    region = os.getenv("PINECONE_REGION")
    environment = os.getenv("PINECONE_ENVIRONMENT")

    if host and not (cloud or region or environment):
        raise ValueError(
            "PINECONE_HOST is set but index is missing. "
            "Provide PINECONE_CLOUD + PINECONE_REGION (serverless) or PINECONE_ENVIRONMENT (pod)."
        )

    if environment:
        from pinecone import PodSpec
        spec = PodSpec(environment=environment)
    else:
        if not cloud or not region:
            raise ValueError("Missing PINECONE_CLOUD or PINECONE_REGION for serverless index creation.")
        from pinecone import ServerlessSpec
        spec = ServerlessSpec(cloud=cloud, region=region)

    pc.create_index(name=index_name, dimension=dimension, metric="cosine", spec=spec)


def chunk_list(xs: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def preflight_existing_ids(index, ids: List[str], sample: int) -> Set[str]:
    """
    Returns a set of IDs that already exist in Pinecone, using index.fetch().
    We'll check up to `sample` IDs (fetch supports batches; we'll do chunks).
    """
    if sample <= 0:
        return set()

    to_check = ids[: min(sample, len(ids))]
    existing: Set[str] = set()

    # fetch has payload limits; keep chunks modest
    for chunk in chunk_list(to_check, 100):
        res = index.fetch(ids=chunk)
        vectors = res.get("vectors", {}) if isinstance(res, dict) else getattr(res, "vectors", {})
        if vectors:
            existing.update(vectors.keys())

    return existing


def main() -> None:
    args = parse_args()
    load_dotenv()

    api_key = require_env("PINECONE_API_KEY")
    index_name = require_env("PINECONE_INDEX_NAME")
    host = os.getenv("PINECONE_HOST")

    if not os.path.exists(args.manifest):
        raise FileNotFoundError(f"Manifest not found: {args.manifest}")
    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    dimension = manifest.get("dimensions")
    if not dimension:
        raise ValueError("Manifest missing 'dimensions'.")

    from pinecone import Pinecone

    pc = Pinecone(api_key=api_key)
    ensure_index(pc, index_name, int(dimension))

    index = pc.Index(host=host) if host else pc.Index(index_name)

    # --- Stats before ---
    before = index.describe_index_stats()
    print("Index stats BEFORE upsert:")
    print(before)

    # --- Load JSONL into memory (keeps things simple & debuggable) ---
    records: List[Dict] = list(read_jsonl(args.vectors))
    print(f"JSONL records found: {len(records)}")

    if not records:
        print("Nothing to upsert. Exiting.")
        return

    ids = [r["id"] for r in records if "id" in r]
    print(f"IDs found in file: {len(ids)} (showing first 5): {ids[:5]}")

    # --- Preflight: detect existing IDs in Pinecone ---
    existing_ids = preflight_existing_ids(index, ids, args.preflight_sample)
    checked = min(args.preflight_sample, len(ids)) if args.preflight_sample > 0 else 0
    if checked > 0:
        print(f"Preflight checked IDs: {checked}")
        print(f"Already in Pinecone (within checked sample): {len(existing_ids)}")
        print(f"Not in Pinecone (within checked sample): {checked - len(existing_ids)}")
    else:
        print("Preflight skipped (--preflight-sample 0).")

    # --- Optionally skip existing IDs (only safe if you want count to increase) ---
    if args.skip_existing and existing_ids:
        existing_set = existing_ids
        before_len = len(records)
        records = [r for r in records if r.get("id") not in existing_set]
        print(f"skip-existing enabled: filtered {before_len - len(records)} records; remaining {len(records)}")

    if not records:
        print("After filtering, nothing new to upsert. Exiting.")
        return

    # --- Upsert batches ---
    upserted = 0
    buffer: List[Dict] = []
    for r in records:
        buffer.append(r)
        if len(buffer) >= args.batch_size:
            index.upsert(vectors=buffer)
            upserted += len(buffer)
            buffer = []
            print(f"Upserted {upserted} vectors")

    if buffer:
        index.upsert(vectors=buffer)
        upserted += len(buffer)
        print(f"Upserted {upserted} vectors")

    # --- Stats after ---
    after = index.describe_index_stats()
    print("Index stats AFTER upsert:")
    print(after)


if __name__ == "__main__":
    main()