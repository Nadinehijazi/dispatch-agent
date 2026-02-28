import re
from typing import Optional
from typing import Dict, List

# assumes CATEGORY_KEYWORDS: Dict[str, List[str]] and contains_kw(text, kw) exist

def classify_category(text: str) -> str:
    t = (text or "").lower()

    # --- environmental / physical hazards (explicit emergency / hazard) ---
    environmental_keywords = [
        "gas smell", "strong gas smell", "gas leak", "natural gas", "rotten egg",
        "chemical smell", "chemical odor", "fumes", "vapors",
        "carbon monoxide", "co alarm",
        "smoke", "fire", "explosion",
        "sparking", "live wire", "downed wire",
    ]

    # --- vague-only language (should not become "safety" by itself) ---
    vague_only = [
        "feels off", "something weird", "not sure who handles", "not sure",
        "vibe", "weird", "strange", "odd", "maybe", "might be", "i think", "kinda", "sort of",
    ]

    # If it's vague AND there is no explicit hazard indicator -> unknown
    if any(v in t for v in vague_only) and not any(k in t for k in environmental_keywords):
        return "unknown"

    # --- public safety / suspicious / crime signals (classification label only) ---
    public_safety_keywords = [
        "suspicious", "loitering", "staring",
        "following", "harassing",
        "fight", "assault", "robbery",
        "breaking in", "break in",
        "weapon", "gun", "knife",
        "shots fired", "shooting", "gunfire", "stabbing", "stabbed",
    ]

    # --- property crime in progress (classification only) ---
    property_in_progress = (
        ("door" in t and any(w in t for w in ["handle", "knob"]) and any(
            x in t for x in ["try", "trying", "check", "checking", "jiggle", "pull"]))
        or ("car" in t and any(
            x in t for x in ["break", "breaking", "tamper", "tampering", "smash"]))
        or ("parked car" in t and any(
            x in t for x in ["look", "looking", "peering", "checking"]))
        or ("trying door handles" in t)
    )

    # Safety classification if we have explicit hazard OR clear public-safety/crime signals
    if any(k in t for k in environmental_keywords) or any(k in t for k in public_safety_keywords) or property_in_progress:
        return "safety"

    # Otherwise fall back to keyword scoring map
    scores: Dict[str, int] = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in kws if contains_kw(t, kw))

    best = max(scores, key=scores.get) if scores else "unknown"
    return best if scores.get(best, 0) > 0 else "unknown"

CATEGORY_KEYWORDS = {
    "noise": ["loud", "noise", "party", "music", "shouting"],
    "sanitation": ["trash", "garbage", "rats", "dumping", "litter"],    "parking": ["blocked", "parking", "car", "vehicle", "double parked", "tow"],
    "street": ["pothole", "streetlight", "traffic light", "sidewalk", "road"],
    "water": ["leak", "water", "sewer", "flood", "hydrant"],
    "safety": [
        "gun", "violence", "assault", "threat", "fight",
        "gas smell", "gas leak", "chemical smell", "chemical odor",
        "fumes", "vapors", "carbon monoxide", "co alarm"
    ],}

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


def contains_kw(t, kw):
    return re.search(rf"\b{re.escape(kw)}\b", t) is not None


def classify_category(text: str) -> str:
    t = (text or "").lower()

    # --- environmental / physical hazards (explicit emergency / hazard) ---
    environmental_keywords = [
        "gas smell", "strong gas smell", "gas leak", "natural gas", "rotten egg",
        "chemical smell", "chemical odor", "fumes", "vapors",
        "carbon monoxide", "co alarm",
        "smoke", "fire", "explosion",
        "sparking", "live wire", "downed wire",
    ]

    # --- vague-only language (should not become "safety" by itself) ---
    vague_only = [
        "feels off", "something weird", "not sure who handles", "not sure",
        "vibe", "weird", "strange", "odd", "maybe", "might be", "i think", "kinda", "sort of",
    ]

    # If it's vague AND there is no explicit hazard indicator -> unknown
    if any(v in t for v in vague_only) and not any(k in t for k in environmental_keywords):
        return "unknown"

    # --- public safety / suspicious / crime signals (classification label only) ---
    public_safety_keywords = [
        "suspicious", "loitering", "staring",
        "following", "harassing",
        "fight", "assault", "robbery",
        "breaking in", "break in",
        "weapon", "gun", "knife",
        "shots fired", "shooting", "gunfire", "stabbing", "stabbed",
    ]

    # --- property crime in progress (classification only) ---
    property_in_progress = (
        ("door" in t and any(w in t for w in ["handle", "knob"]) and any(
            x in t for x in ["try", "trying", "check", "checking", "jiggle", "pull"]))
        or ("car" in t and any(
            x in t for x in ["break", "breaking", "tamper", "tampering", "smash"]))
        or ("parked car" in t and any(
            x in t for x in ["look", "looking", "peering", "checking"]))
        or ("trying door handles" in t)
    )

    # Safety classification if we have explicit hazard OR clear public-safety/crime signals
    if any(k in t for k in environmental_keywords) or any(k in t for k in public_safety_keywords) or property_in_progress:
        return "safety"

    # Otherwise fall back to keyword scoring map
    scores: Dict[str, int] = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in kws if contains_kw(t, kw))

    best = max(scores, key=scores.get) if scores else "unknown"
    return best if scores.get(best, 0) > 0 else "unknown"

def estimate_urgency(text: str, category: str, time_24h: Optional[str]) -> str:
    """
    Deterministic severity scoring model.
    Urgency = function of hazard strength, not category alone.
    """

    t = (text or "").lower().strip()

    def has_any(phrases):
        return any(p in t for p in phrases)

    severity = 0

    # --- HIGH severity signals (life-threatening / explosion / weapons) ---
    high_signals = [
        "gas leak", "strong gas smell", "natural gas", "rotten egg",
        "carbon monoxide", "co alarm",
        "smoke", "fire", "explosion",
        "sparking", "live wire", "downed wire",
        "shooting", "shots fired", "gunfire",
        "stabbed", "stabbing",
        "unconscious", "not breathing", "can't breathe",
        "chest pain", "fainting"
    ]

    # --- MEDIUM severity signals (non-life-threatening but hazardous) ---
    medium_signals = [
        "chemical odor", "fumes", "vapors",
        "burning smell", "strong odor",
        "coughing", "dizzy", "vomiting", "headache",
        "weapon", "gun", "knife",
        "fight", "assault", "robbery",
        "blocking traffic", "swerving", "cars avoiding",
        "near crosswalk"
    ]

    # --- Nuisance / recurring signals ---
    nuisance_signals = [
        "every", "recurring", "again", "each weekend", "every weekend"
    ]

    # --- Vague language ---
    vague_signals = [
        "something weird", "feels off", "strange", "not sure",
        "maybe", "might be", "kinda", "sort of"
    ]

    property_crime = (
            ("door" in t and any(w in t for w in ["handle", "knob"]) and any(
                x in t for x in ["try", "trying", "check", "checking", "jiggle", "pull"]))
            or ("parked car" in t and any(x in t for x in ["look", "looking", "peering", "checking"]))
    )

    if property_crime:
        severity += 2

    # ---------------------------
    # Severity accumulation
    # ---------------------------

    if has_any(high_signals):
        severity += 3

    if has_any(medium_signals):
        severity += 2

    # Nighttime noise escalation
    if category == "noise":
        is_night = (
            "night" in t
            or (time_24h and (time_24h >= "22:00" or time_24h <= "05:00"))
        )
        if is_night:
            severity += 1

    if has_any(nuisance_signals):
        severity += 1

    # Penalize vague-only reports
    if has_any(vague_signals) and severity == 0:
        return "low"

    # ---------------------------
    # Map score → urgency
    # ---------------------------

    if severity >= 3:
        return "high"

    if severity >= 2:
        return "medium"

    return "low"