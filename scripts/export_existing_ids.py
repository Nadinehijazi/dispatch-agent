import os
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index(os.environ["PINECONE_INDEX_NAME"])

# WARNING: this only works if index size is reasonable
# We'll use query with dummy vector to get IDs in chunks

stats = index.describe_index_stats()
print("Index stats:", stats)

# If your index isn't huge, do this:
# (If it's large, we need pagination logic — tell me)

all_ids = []

# Quick trick: query everything with top_k large (only works if <= 10k)
res = index.query(
    vector=[0.0] * 1536,   # change 1536 to your embedding dimension
    top_k=5000,
    include_metadata=False
)

for match in res["matches"]:
    all_ids.append(match["id"])

import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(base_dir, "data")
os.makedirs(data_dir, exist_ok=True)

seen_path = os.path.join(data_dir, "seen_ids.txt")

with open(seen_path, "w", encoding="utf-8") as f:
    for _id in all_ids:
        f.write(_id + "\n")

print("Wrote", len(all_ids), "IDs to seen_ids.txt")