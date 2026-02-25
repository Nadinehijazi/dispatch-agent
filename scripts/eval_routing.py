import argparse
import os
import random

import pandas as pd


DEFAULT_INPUT = "data/nyc_311_sample_locked.csv"


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


def build_complaint_text(row: pd.Series) -> str:
    parts = []
    for field in ["complaint_type", "descriptor", "location_type", "borough"]:
        value = row.get(field)
        if pd.notna(value) and str(value).strip():
            parts.append(str(value).strip())
    return " | ".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate top-agency match rate from Pinecone retrieval.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--top-k", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv()

    api_key = require_env("LLMOD_API_KEY")
    base_url = require_env("LLMOD_BASE_URL")
    model = require_env("EMBEDDING_MODEL")
    pinecone_key = require_env("PINECONE_API_KEY")
    index_name = require_env("PINECONE_INDEX_NAME")
    host = os.getenv("PINECONE_HOST")

    df = pd.read_csv(args.input)
    df["complaint_text"] = df.apply(build_complaint_text, axis=1)

    rng = random.Random(args.seed)
    sample = df.sample(n=min(args.n, len(df)), random_state=rng.randint(0, 1_000_000))

    from openai import OpenAI
    from pinecone import Pinecone

    client = OpenAI(api_key=api_key, base_url=base_url)
    pc = Pinecone(api_key=pinecone_key)
    index = pc.Index(host=host) if host else pc.Index(index_name)

    total = 0
    match = 0

    for _, row in sample.iterrows():
        text = str(row["complaint_text"])
        true_agency = row.get("agency")
        if not text or pd.isna(true_agency):
            continue

        emb = client.embeddings.create(model=model, input=[text]).data[0].embedding
        result = index.query(
            vector=emb,
            top_k=args.top_k,
            include_metadata=True,
            filter={"status": {"$eq": "Closed"}},
        )
        if not result.matches:
            continue
        top_agency = (result.matches[0].metadata or {}).get("agency")
        total += 1
        if top_agency == true_agency:
            match += 1

    rate = (match / total) if total else 0.0
    print(f"Eval samples: {total}")
    print(f"Top-agency match rate: {rate:.2%}")


if __name__ == "__main__":
    main()
