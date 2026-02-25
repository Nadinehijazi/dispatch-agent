import argparse
import json
import os
from typing import Iterable, List


DEFAULT_VECTORS = "data/nyc_311_embeddings_llmod.jsonl"
DEFAULT_MANIFEST = "data/nyc_311_embeddings_llmod_manifest.json"


def load_dotenv(path: str = "..env") -> None:
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
        description="Create Pinecone index (if missing) and upsert JSONL vectors.",
    )
    parser.add_argument("--vectors", default=DEFAULT_VECTORS)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--batch-size", type=int, default=100)
    return parser.parse_args()


def read_jsonl(path: str) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def batched(items: List[dict], batch_size: int) -> Iterable[List[dict]]:
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


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

    buffer: List[dict] = []
    upserted = 0
    for record in read_jsonl(args.vectors):
        buffer.append(record)
        if len(buffer) >= args.batch_size:
            index.upsert(vectors=buffer)
            upserted += len(buffer)
            buffer = []
            print(f"Upserted {upserted} vectors")

    if buffer:
        index.upsert(vectors=buffer)
        upserted += len(buffer)
        print(f"Upserted {upserted} vectors")


if __name__ == "__main__":
    main()
