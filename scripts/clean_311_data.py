import pandas as pd

IN_PATH = "data/nyc_311_sample_locked.csv"
OUT_PATH = "data/nyc_311_cleaned.csv"

df = pd.read_csv(IN_PATH)

print(f"Loaded rows: {len(df):,}")

# 1. Drop unusable rows
df = df.dropna(subset=["complaint_type", "agency"])
print(f"After dropping missing complaint/agency: {len(df):,}")

# 2. Normalize text fields
TEXT_COLS = [
    "complaint_type",
    "descriptor",
    "location_type",
    "borough",
]

for col in TEXT_COLS:
    df[col] = (
        df[col]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.strip()
    )

# 3. Build embedding-ready text
def build_complaint_text(row):
    parts = []
    parts.append(f"problem: {row['complaint_type']}")
    if row["descriptor"]:
        parts.append(f"details: {row['descriptor']}")
    if row["location_type"]:
        parts.append(f"location type: {row['location_type']}")
    if row["borough"]:
        parts.append(f"borough: {row['borough']}")
    return ". ".join(parts)

df["complaint_text"] = df.apply(build_complaint_text, axis=1)

# 4. Keep only needed columns for RAG pipeline
FINAL_COLS = [
    "unique_key",
    "complaint_text",
    "agency",
    "agency_name",
    "borough",
    "created_date",
    "status",
    "open_data_channel_type",
]

df_final = df[FINAL_COLS]

df_final.to_csv(OUT_PATH, index=False)

print(f"Saved cleaned data to: {OUT_PATH}")
print("Sample complaint_text:")
print(df_final["complaint_text"].head(3).tolist())
