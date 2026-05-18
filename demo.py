# demo.py
"""
Run this to see the full pipeline in action.
Demonstrates 3 scenarios: auto-approve, escalate, auto-reject.
"""
import time
import httpx  # pip install httpx

BASE = "http://localhost:8000"

def submit_and_poll(payload: dict, label: str):
    print(f"\n{'='*60}")
    print(f"Scenario: {label}")
    print(f"{'='*60}")

    r = httpx.post(f"{BASE}/claims/", json=payload)
    assert r.status_code == 202, r.text
    claim_id = r.json()["id"]
    print(f"Submitted. Claim ID: {claim_id}")

    # Poll until terminal state
    for _ in range(20):
        time.sleep(1)
        r = httpx.get(f"{BASE}/claims/{claim_id}")
        claim = r.json()
        status = claim["status"]
        print(f"  Status: {status}")
        if status in ("approved", "rejected", "escalated", "failed"):
            break

    print(f"\nFinal state: {claim['status']}")
    print(f"Risk level:  {claim['risk_level']} (score: {claim['risk_score']})")
    print(f"Decision:    {claim['decision']}")
    print(f"\nLLM reasoning:\n  {claim['llm_reasoning']}")
    if claim['llm_anomalies']:
        print(f"\nLLM anomalies:\n  {claim['llm_anomalies']}")

    print("\nAudit trail:")
    audit = httpx.get(f"{BASE}/claims/{claim_id}/audit").json()
    for entry in audit:
        print(f"  [{entry['timestamp']}] {entry['from']} → {entry['to']}")
        print(f"    actor: {entry['actor']} | {entry['reason'][:80]}")

    return claim_id

# Scenario 1: Clean low-value claim — should AUTO_APPROVE
submit_and_poll({
    "claimant_name": "Priya Sharma",
    "product_name":  "LG Washing Machine",
    "claim_amount":  450.00,
    "incident_date": "2025-03-01",
    "description":   "The washing machine stopped spinning during a normal cycle. "
                     "It makes a loud noise and the drum does not rotate. "
                     "The machine is 18 months old and has never had issues before.",
}, "Low-risk auto-approve")

# Scenario 2: High value + legal language — should ESCALATE
submit_and_poll({
    "claimant_name": "Vikram Mehta",
    "product_name":  "Samsung OLED TV",
    "claim_amount":  7200.00,
    "incident_date": "2025-02-10",
    "description":   "The TV suddenly stopped working and has a cracked screen. "
                     "This is the second time this has happened and I expect full "
                     "replacement. My lawyer has advised me to document this carefully. "
                     "I need this resolved immediately or I will take further action.",
}, "High-risk human escalation")

# Scenario 3: Waiting period violation — should fail validation + escalate/reject
submit_and_poll({
    "claimant_name": "Ananya Gupta",
    "product_name":  "Dyson Vacuum",
    "claim_amount":  600.00,
    "incident_date": "2025-04-30",  # recent date, within 30-day waiting period
    "description":   "The vacuum has completely stopped working after only 3 uses. "
                     "The motor makes a burning smell and shuts off after 10 seconds. "
                     "This is clearly a manufacturing defect.",
}, "Waiting period violation")