from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

host = os.environ.get("PINECONE_HOST", "").strip()
if host.startswith("https://"):
    host = host.replace("https://", "")
if host.startswith("http://"):
    host = host.replace("http://", "")

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index(host=host)

stats = index.describe_index_stats().to_dict()
print(stats)