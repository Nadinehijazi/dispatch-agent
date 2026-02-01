import re
from typing import Optional


CATEGORY_KEYWORDS = {
    "noise": ["loud", "noise", "party", "music", "shouting"],
    "sanitation": ["trash", "garbage", "rats", "smell", "dumping", "litter"],
    "parking": ["blocked", "parking", "car", "vehicle", "double parked", "tow"],
    "street": ["pothole", "streetlight", "traffic light", "sidewalk", "road"],
    "water": ["leak", "water", "sewer", "flood", "hydrant"],
    "safety": ["gun", "violence", "assault", "threat", "fight"],
}

AGENCY_MAP = {
    "noise": "Noise Control / Non-emergency Police",
    "sanitation": "Sanitation Department",
    "parking": "Parking Enforcement",
    "street": "Public Works / DOT",
    "water": "Water & Sewer Department",
    "safety": "Emergency Services / Police",
    "unknown": "311 Triage (Unknown)",
}

def extract_time(text: str) -> Optional[str]:
    # matches "2am", "2 am", "14:30", "2:15pm"
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text, re.IGNORECASE)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or "00")
        ampm = m.group(3).lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"
    m2 = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if m2:
        return f"{int(m2.group(1)):02d}:{int(m2.group(2)):02d}"
    return None

def extract_location(text: str) -> Optional[str]:
    # very lightweight heuristic: "in <Word...>" or known NYC boroughs (adapt later)
    boroughs = ["brooklyn", "manhattan", "queens", "bronx", "staten island"]
    for b in boroughs:
        if re.search(rf"\b{re.escape(b)}\b", text, re.IGNORECASE):
            return b.title()
    m = re.search(r"\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b", text)
    if m:
        return m.group(1).strip()
    return None

def extract_recurrence(text: str) -> Optional[str]:
    patterns = [
        r"\bevery day\b",
        r"\bdaily\b",
        r"\bevery weekend\b",
        r"\bevery week\b",
        r"\bevery night\b",
        r"\bagain\b",
        r"\brecurring\b",
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return re.sub(r"\\b", "", p).replace("\\", "")
    return None

def classify_category(text: str) -> str:
    t = text.lower()
    scores = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in kws if kw in t)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"

def estimate_urgency(text: str, category: str, time_24h: Optional[str]) -> str:
    t = text.lower()
    # safety always high
    if category == "safety":
        return "high"
    # nighttime noise recurring -> medium
    if category == "noise":
        if "night" in t or (time_24h and (time_24h >= "22:00" or time_24h <= "05:00")):
            if "every" in t or "recurring" in t or "again" in t:
                return "medium"
    # default
    return "low"
