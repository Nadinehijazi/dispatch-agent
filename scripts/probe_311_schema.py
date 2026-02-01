import requests
import certifi

BASE_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"

# grab 1 row to see actual keys
url = f"{BASE_URL}?$limit=1"
print("Probing:", url)

r = requests.get(url, verify=certifi.where(), timeout=60)
print("Status:", r.status_code)
print("Body:", r.text[:1000])  # first 1000 chars
r.raise_for_status()

row = r.json()[0]
print("\nKeys in dataset row:\n", sorted(row.keys()))
