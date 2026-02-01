import argparse
import json
import os
from dataclasses import dataclass
from typing import Iterable, List

import pandas as pd

DEFAULT_INPUT = "data/nyc_311_cleaned.csv"
DEFAULT_OUTPUT = "data/nyc_311_embeddings.jsonl"
DEFAULT_MANIFEST = "data/nyc_311_embeddings_manifest.json"

REQUIRED_COLS = [
    "unique_key",
    "complaint_text",
    "agency",
    "agency_name",
    "borough",
    "created_date",
    "status",
    "open_data_channel_type",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed NYC 311 complaint_text and write Pinecone-ready vectors.",
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--provider", choices=["sentence-transformers", "openai"], default="sentence-transformers")
    parser.add_argument("--model", default="all-MiniLM-L6-v2")
    parser.add_argument("--openai-model", default="text-embedding-3-small")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--device", default=None)
    parser.add_argument("--include-complaint-text", action="store_true")
    parser.set_defaults(include_complaint_text=True)
    return parser.parse_args()


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


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df


def select_subset(df: pd.DataFrame, start: int, limit: int) -> pd.DataFrame:
    if start < 0 or limit <= 0:
        raise ValueError("start must be >= 0 and limit must be > 0")
    end = start + limit
    return df.iloc[start:end].copy()


def build_metadata(row: pd.Series, include_complaint_text: bool) -> dict:
    metadata = {
        "agency": row["agency"],
        "agency_name": row["agency_name"],
        "borough": row["borough"],
        "created_date": row["created_date"],
        "status": row["status"],
        "open_data_channel_type": row["open_data_channel_type"],
    }
    if include_complaint_text:
        metadata["complaint_text"] = row["complaint_text"]
    return metadata


@dataclass
class Embedder:
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


@dataclass
class SentenceTransformersEmbedder(Embedder):
    model_name: str
    device: str | None = None

    def __post_init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        if self.device:
            self.model = SentenceTransformer(self.model_name, device=self.device)
        else:
            self.model = SentenceTransformer(self.model_name)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        vectors = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=False,
            show_progress_bar=False,
        )
        return [vec.tolist() for vec in vectors]


@dataclass
class OpenAIEmbedder(Embedder):
    model_name: str

    def __post_init__(self) -> None:
        from openai import OpenAI

        self.client = OpenAI()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        response = self.client.embeddings.create(
            model=self.model_name,
            input=texts,
        )
        return [item.embedding for item in response.data]


def batched(items: List[str], batch_size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def main() -> None:
    args = parse_args()
    load_dotenv()

    df = load_data(args.input)
    subset = select_subset(df, args.start, args.limit)

    texts = subset["complaint_text"].astype(str).tolist()
    ids = subset["unique_key"].astype(str).tolist()

    if args.provider == "sentence-transformers":
        embedder = SentenceTransformersEmbedder(args.model, device=args.device)
        model_used = args.model
    else:
        embedder = OpenAIEmbedder(args.openai_model)
        model_used = args.openai_model

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.manifest) or ".", exist_ok=True)

    total = len(texts)
    written = 0
    dims = None

    with open(args.output, "w", encoding="utf-8") as f:
        for batch_texts, batch_ids in zip(batched(texts, args.batch_size), batched(ids, args.batch_size)):
            vectors = embedder.embed_texts(batch_texts)
            if dims is None and vectors:
                dims = len(vectors[0])
            for row_idx, (vec, row_id) in enumerate(zip(vectors, batch_ids)):
                row = subset.iloc[written + row_idx]
                record = {
                    "id": row_id,
                    "values": vec,
                    "metadata": build_metadata(row, args.include_complaint_text),
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
        "provider": args.provider,
        "model": model_used,
        "dimensions": dims,
        "metadata_fields": [
            "agency",
            "agency_name",
            "borough",
            "created_date",
            "status",
            "open_data_channel_type",
        ] + (["complaint_text"] if args.include_complaint_text else []),
    }

    with open(args.manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Wrote vectors to: {args.output}")
    print(f"Wrote manifest to: {args.manifest}")


if __name__ == "__main__":
    main()
