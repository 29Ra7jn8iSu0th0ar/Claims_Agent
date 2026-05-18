import json
import google.generativeai as genai
from app.config import settings

# Configure once at module load
genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel(settings.gemini_model)

SYSTEM_PROMPT = """You are an insurance claims analyst assistant helping human reviewers.

Your ONLY job is to:
1. Summarize the claim clearly
2. Surface specific anomalies or concerns worth investigating  
3. Write a concise note for the human reviewer

You do NOT approve or reject claims.
You do NOT set risk scores.
You NEVER fabricate facts not present in the input.

Respond ONLY with valid JSON using exactly these keys:
- "summary": one sentence summarizing the claim
- "anomalies": list of strings (specific concerns, empty list if none)
- "reviewer_note": 2-3 sentences for the human reviewer
"""


def build_prompt(claim, validation_result: dict) -> str:
    return f"""{SYSTEM_PROMPT}

Analyze this insurance claim:

Claimant: {claim.claimant_name}
Product:  {claim.product_name}
Amount:   ${claim.claim_amount:.2f}
Incident: {claim.incident_date}
Description: {claim.description}

Validation result:
- Passed: {validation_result['passed']}
- Failures: {json.dumps(validation_result['failures'], indent=2)}
- Warnings: {json.dumps(validation_result['warnings'], indent=2)}
- Extracted signals: {json.dumps(claim.extracted_data, indent=2)}

Respond ONLY with valid JSON. No markdown, no backticks, just the JSON object."""


def analyze_claim(claim, validation_result: dict) -> dict:
    try:
        response = model.generate_content(
            build_prompt(claim, validation_result),
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048,
            ),
        )

        raw = response.text.strip()

        # Strip ALL variations of markdown code fences
        # gemini-2.5-flash sometimes wraps in ```json ... ```
        if "```" in raw:
            # Extract content between first ``` and last ```
            parts = raw.split("```")
            # parts[1] contains "json\n{...}" or just "{..."
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]  # remove the word "json"
            raw = raw.strip()

        # Find JSON object boundaries as last resort
        # handles cases where there's text before or after the JSON
        if not raw.startswith("{"):
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]

        parsed = json.loads(raw)
        return {
            "summary":       parsed.get("summary", ""),
            "anomalies":     parsed.get("anomalies", []),
            "reviewer_note": parsed.get("reviewer_note", ""),
            "llm_success":   True,
        }

    except Exception as e:
        return {
            "summary":       "LLM analysis unavailable",
            "anomalies":     [],
            "reviewer_note": f"Automated analysis could not complete: {type(e).__name__}",
            "llm_success":   False,
            "error":         str(e),
        }




# def analyze_claim(claim, validation_result: dict) -> dict:
#     try:
#         response = model.generate_content(
#             build_prompt(claim, validation_result),
#             generation_config=genai.GenerationConfig(
#                 temperature=0.1,
#                 max_output_tokens=2048,
#             ),
#         )

#         raw = response.text.strip()
#         print("=== GEMINI RAW RESPONSE ===")
#         print(repr(raw))        # repr() shows hidden characters exactly
#         print("=== END GEMINI RESPONSE ===")

#         if "```" in raw:
#             parts = raw.split("```")
#             raw = parts[1]
#             if raw.startswith("json"):
#                 raw = raw[4:]
#             raw = raw.strip()

#         if not raw.startswith("{"):
#             start = raw.find("{")
#             end   = raw.rfind("}") + 1
#             if start != -1 and end > start:
#                 raw = raw[start:end]

#         parsed = json.loads(raw)
#         return {
#             "summary":       parsed.get("summary", ""),
#             "anomalies":     parsed.get("anomalies", []),
#             "reviewer_note": parsed.get("reviewer_note", ""),
#             "llm_success":   True,
#         }

#     except Exception as e:
#         print("=== GEMINI ERROR ===")
#         print(f"Error type: {type(e).__name__}")
#         print(f"Error message: {str(e)}")
#         print("===================")
#         return {
#             "summary":       "LLM analysis unavailable",
#             "anomalies":     [],
#             "reviewer_note": f"Automated analysis could not complete: {type(e).__name__}",
#             "llm_success":   False,
#             "error":         str(e),
#         }