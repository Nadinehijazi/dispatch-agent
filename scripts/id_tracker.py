import os

def load_seen(path="data/seen_ids.txt") -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def append_seen(ids: list[str], path="data/seen_ids.txt") -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for _id in ids:
            f.write(f"{_id}\n")