"""
Seeds the database with policy rules and 3 demo claims.
Run once after first startup: python seed_data.py
"""
from app.database import SessionLocal, create_tables
from app.models.policy import PolicyRule
from app.models.claim import Claim
from app.core.enums import ClaimStatus

POLICY_RULES = [
    {
        "rule_name":              "standard_electronics",
        "product_category":       "electronics",
        "max_claim_amount":       10000.0,
        "min_days_before_claim":  30,
    },
    {
        "rule_name":              "standard_appliances",
        "product_category":       "appliances",
        "max_claim_amount":       8000.0,
        "min_days_before_claim":  30,
    },
    {
        "rule_name":              "global_ceiling",
        "product_category":       None,   # applies to all
        "max_claim_amount":       15000.0,
        "min_days_before_claim":  14,
    },
]

DEMO_CLAIMS = [
    {
        "claimant_name": "Priya Sharma",
        "product_name":  "LG Washing Machine",
        "claim_amount":  450.0,
        "incident_date": "2025-01-15",
        "description": (
            "The washing machine stopped spinning during a normal cycle. "
            "It makes a loud grinding noise and the drum does not rotate. "
            "The machine is 18 months old and has never had issues before. "
            "I believe this is a mechanical defect."
        ),
    },
    {
        "claimant_name": "Vikram Mehta",
        "product_name":  "Samsung OLED TV",
        "claim_amount":  7200.0,
        "incident_date": "2025-02-01",
        "description": (
            "The TV suddenly stopped working and the screen has cracked internally. "
            "This is the second time this has happened. I expect full replacement. "
            "My lawyer has told me to document this carefully. "
            "I need this resolved immediately or I will take further legal action."
        ),
    },
    {
        "claimant_name": "Ananya Gupta",
        "product_name":  "Dyson Vacuum Cleaner",
        "claim_amount":  600.0,
        "incident_date": "2025-04-28",   # recent — will violate waiting period
        "description": (
            "The vacuum completely stopped working after only three uses. "
            "The motor makes a burning smell and shuts off after 10 seconds. "
            "This is clearly a manufacturing defect from the factory."
        ),
    },
]


def seed():
    create_tables()
    db = SessionLocal()

    try:
        # Seed policy rules (skip if already exist)
        for rule_data in POLICY_RULES:
            exists = db.query(PolicyRule).filter_by(
                rule_name=rule_data["rule_name"]
            ).first()
            if not exists:
                db.add(PolicyRule(**rule_data))
                print(f"  [seed] PolicyRule: {rule_data['rule_name']}")

        # Seed demo claims
        for claim_data in DEMO_CLAIMS:
            db.add(Claim(**claim_data))
            print(f"  [seed] Claim: {claim_data['claimant_name']}")

        db.commit()
        print("\n[seed] Done. Database seeded.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()