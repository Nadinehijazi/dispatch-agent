import argparse
import json
import os
from typing import Iterable, List

import pandas as pd


DEFAULT_INPUT = "data/nyc_311_sample_locked.csv"
DEFAULT_OUTPUT = "data/nyc_311_embeddings_llmod.jsonl"
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
        description="Embed NYC 311 complaint_text via OpenAI-compatible LLMOD endpoint.",
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=128)
    return parser.parse_args()


def batched(items: List[str], batch_size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def build_complaint_text(row: pd.Series) -> str:
    parts = []
    for field in ["complaint_type", "descriptor", "location_type", "borough"]:
        value = row.get(field)
        if pd.notna(value) and str(value).strip():
            parts.append(str(value).strip())
    return " | ".join(parts)


def build_metadata(row: pd.Series) -> dict:
    borough = row.get("borough")
    if pd.notna(borough) and str(borough).strip():
        borough = str(borough).strip().upper()
    metadata = {
        "agency": row.get("agency"),
        "created_date": row.get("created_date"),
        "status": row.get("status"),
        "open_data_channel_type": row.get("open_data_channel_type"),
        "complaint_type": row.get("complaint_type"),
        "descriptor": row.get("descriptor"),
        "borough": borough,
    }
    cleaned = {}
    for key, value in metadata.items():
        if pd.isna(value):
            continue
        cleaned[key] = value
    return cleaned


def main() -> None:
    args = parse_args()
    load_dotenv()

    api_key = require_env("LLMOD_API_KEY")
    base_url = require_env("LLMOD_BASE_URL")
    model = require_env("EMBEDDING_MODEL")

    df = pd.read_csv(args.input)
    df = df.iloc[args.start: args.start + args.limit].copy()

    df["complaint_text"] = df.apply(build_complaint_text, axis=1)
    texts = df["complaint_text"].astype(str).tolist()
    ids = df["unique_key"].astype(str).tolist()

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.manifest) or ".", exist_ok=True)

    dims = None
    total = len(texts)
    written = 0

    with open(args.output, "w", encoding="utf-8") as f:
        for batch_texts, batch_ids in zip(batched(texts, args.batch_size), batched(ids, args.batch_size)):
            response = client.embeddings.create(model=model, input=batch_texts)
            vectors = [item.embedding for item in response.data]
            if dims is None and vectors:
                dims = len(vectors[0])
            for row_idx, (vec, row_id) in enumerate(zip(vectors, batch_ids)):
                row = df.iloc[written + row_idx]
                record = {
                    "id": row_id,
                    "values": vec,
                    "metadata": build_metadata(row),
                }
                f.write(json.dumps(record))
                f.write("\n")
            written += len(batch_texts)
            print(f"Embedded {written}/{total} rows")

    manifest = {
        "input": args.input,
        "output": args.output,
        "rows_embedded": written,
        "start": args.start,
        "limit": args.limit,
        "provider": "llmod-openai-compat",
        "model": model,
        "dimensions": dims,
        "metadata_fields": list(build_metadata(df.iloc[0]).keys()) if len(df) else [],
    }

    with open(args.manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Wrote vectors to: {args.output}")
    print(f"Wrote manifest to: {args.manifest}")


if __name__ == "__main__":
    main()
