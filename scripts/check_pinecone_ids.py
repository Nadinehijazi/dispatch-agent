import os
import json
import random
from pinecone import Pinecone

# Load env vars manually if needed
from dotenv import load_dotenv
load_dotenv()

api_key = os.environ["PINECONE_API_KEY"]
index_name = os.environ["PINECONE_INDEX_NAME"]

pc = Pinecone(api_key=api_key)
index = pc.Index(index_name)

# Read IDs from your new embedding file
ids = []
with open("../data/nyc_311_embeddings_llmod.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        ids.append(json.loads(line)["id"])

res = index.fetch(ids=ids)
already = len(res.vectors)
missing = len(ids) - already
print("Total IDs checked:", len(ids))
print("Already in Pinecone:", already)
print("Not in Pinecone:", missing)
