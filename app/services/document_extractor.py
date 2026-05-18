# # app/services/document_extractor.py
# """
# Extracts structured fields from raw claim description text.
# This is intentionally a mix: regex/rules first, LLM fallback for
# complex fields. Never let the LLM make up numbers — only use it
# to classify or summarize, never to extract amounts or dates.
# """
# # app/services/document_extractor.py
# import re
# from datetime import datetime

# DAMAGE_TYPE_KEYWORDS = {
#     "physical_damage": ["broken", "cracked", "shattered", "damaged", "fell", "dropped"],
#     "water_damage":    ["water", "flood", "leak", "soaked", "wet", "spill"],
#     "electrical":      ["electrical", "surge", "short circuit", "sparks", "burnt", "overheated"],
#     "theft":           ["stolen", "theft", "burglar", "missing", "took"],
#     "manufacturing":   ["defect", "malfunction", "stopped working", "factory", "never worked"],
# }

# # Specific phrases only — avoids false positives like "never happened before"
# REPEAT_CLAIM_PHRASES = [
#     "second time",
#     "happened again",
#     "previous claim",
#     "already claimed",
#     "claimed before",
#     "this before",
# ]


# def extract_claim_fields(description: str, incident_date: str) -> dict:
#     desc_lower = description.lower()

#     # 1. Damage type classification
#     detected_types = [
#         dtype for dtype, keywords in DAMAGE_TYPE_KEYWORDS.items()
#         if any(k in desc_lower for k in keywords)
#     ]

#     # 2. Urgency and fraud signal flags
#     urgency_flags = []

#     if any(w in desc_lower for w in ["urgent", "emergency", "immediately", "critical"]):
#         urgency_flags.append("claimant_urgency_language")

#     if any(w in desc_lower for w in ["lawyer", "attorney", "legal action", "sue"]):
#         urgency_flags.append("legal_threat")

#     if any(phrase in desc_lower for phrase in REPEAT_CLAIM_PHRASES):
#         urgency_flags.append("repeat_claim_language")

#     # 3. Days since incident
#     days_since_incident = None
#     try:
#         incident = datetime.strptime(incident_date, "%Y-%m-%d")
#         days_since_incident = (datetime.utcnow() - incident).days
#     except ValueError:
#         pass

#     # 4. Word count
#     word_count = len(description.split())

#     return {
#         "damage_types":           detected_types or ["unclassified"],
#         "urgency_flags":          urgency_flags,
#         "days_since_incident":    days_since_incident,
#         "description_word_count": word_count,
#         "extracted_at":           datetime.utcnow().isoformat(),
#     }








# app/services/document_extractor.py
import re
from datetime import datetime

DAMAGE_TYPE_KEYWORDS = {
    "physical_damage": ["broken", "cracked", "shattered", "damaged", "fell", "dropped"],
    "water_damage":    ["water", "flood", "leak", "soaked", "wet", "spill"],
    "electrical":      ["electrical", "surge", "short circuit", "sparks", "burnt", "overheated"],
    "theft":           ["stolen", "theft", "burglar", "missing", "took"],
    "manufacturing":   ["defect", "malfunction", "stopped working", "factory", "never worked"],
}

REPEAT_CLAIM_PHRASES = [
    "second time",
    "happened again",
    "previous claim",
    "already claimed",
    "claimed before",
    "this before",
]

# Word-boundary patterns — prevents "sue" matching inside "issue"
LEGAL_THREAT_PATTERNS = [
    r'\blawyer\b',
    r'\battorney\b',
    r'\blegal action\b',
    r'\bsue\b',
    r'\bsuing\b',
    r'\blawsuit\b',
]


def extract_claim_fields(description: str, incident_date: str) -> dict:
    desc_lower = description.lower()

    # 1. Damage type classification
    detected_types = [
        dtype for dtype, keywords in DAMAGE_TYPE_KEYWORDS.items()
        if any(k in desc_lower for k in keywords)
    ]

    # 2. Urgency and fraud signal flags
    urgency_flags = []

    if any(w in desc_lower for w in ["urgent", "emergency", "immediately", "critical"]):
        urgency_flags.append("claimant_urgency_language")

    # Regex with word boundaries — fixes false positive on "issue" → "sue"
    if any(re.search(p, desc_lower) for p in LEGAL_THREAT_PATTERNS):
        urgency_flags.append("legal_threat")

    if any(phrase in desc_lower for phrase in REPEAT_CLAIM_PHRASES):
        urgency_flags.append("repeat_claim_language")

    # 3. Days since incident
    days_since_incident = None
    try:
        incident = datetime.strptime(incident_date, "%Y-%m-%d")
        days_since_incident = (datetime.utcnow() - incident).days
    except ValueError:
        pass

    # 4. Word count
    word_count = len(description.split())

    return {
        "damage_types":           detected_types or ["unclassified"],
        "urgency_flags":          urgency_flags,
        "days_since_incident":    days_since_incident,
        "description_word_count": word_count,
        "extracted_at":           datetime.utcnow().isoformat(),
    }