import os
import pandas as pd
import requests
import certifi
from io import StringIO
from urllib.parse import urlencode

BASE_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.csv"

COLUMNS = [
    "unique_key",
    "created_date",
    "status",
    "agency",
    "agency_name",
    "complaint_type",
    "descriptor",
    "location_type",
    "incident_zip",
    "incident_address",
    "street_name",
    "cross_street_1",
    "cross_street_2",
    "city",
    "borough",
    "latitude",
    "longitude",
    "open_data_channel_type",
]

WHERE = "created_date >= '2023-01-01T00:00:00.000' AND status = 'Closed'"

# ✅ safer paging settings
PAGE_SIZE = 2000          # smaller payload -> fewer timeouts
MAX_ROWS = 20000          # total rows you want
TIMEOUT = 180             # allow slow responses

OUT_PATH = "data/nyc_311_sample_locked.csv"
os.makedirs("data", exist_ok=True)

def fetch_page(offset: int, limit: int) -> pd.DataFrame:
    params = {
        "$select": ",".join(COLUMNS),
        "$where": WHERE,
        "$limit": limit,
        "$offset": offset,
        # ordering makes paging stable
        "$order": "created_date DESC",
    }
    url = f"{BASE_URL}?{urlencode(params)}"
    print(f"\nFetching offset={offset}, limit={limit}")
    resp = requests.get(url, verify=certifi.where(), timeout=TIMEOUT)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))

all_rows = []
offset = 0

while offset < MAX_ROWS:
    limit = min(PAGE_SIZE, MAX_ROWS - offset)
    df_page = fetch_page(offset, limit)

    # If API returns empty, we reached the end of available rows
    if df_page.empty:
        print("No more rows returned by API.")
        break

    all_rows.append(df_page)
    offset += len(df_page)

    print(f"Downloaded so far: {offset:,} rows")

df = pd.concat(all_rows, ignore_index=True).drop_duplicates(subset=["unique_key"])

print(f"\nFinal rows after dedup: {len(df):,}")
df.to_csv(OUT_PATH, index=False)
print(f"Saved to: {OUT_PATH}")
