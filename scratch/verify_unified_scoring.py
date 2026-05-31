import sys
import os

# Add workspace root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.priority_engine import compute_priority_score, compute_priority_breakdown, score_to_level
from app.database.db import SessionLocal
from app.models.case_model import Case

def test_priority_engine():
    print("=== STARTING PRIORITY ENGINE VERIFICATION ===")

    # Test Case 1: Article 21 Violation (Constitutional liberty floor)
    case_1 = {
        "title": "Petition regarding personal liberty",
        "summary": "The petitioner claims arbitrary action by local authorities violating Article 21 of the Constitution.",
        "case_type": "Writ Petition",
        "case_age_days": 10
    }
    score_1 = compute_priority_score(case_1)
    level_1 = score_to_level(score_1)
    print(f"Case 1 (Article 21): Score = {score_1}, Level = {level_1}")
    assert score_1 >= 86.0, f"Expected Critical floor >= 86.0, got {score_1}"
    assert level_1 == "Critical", f"Expected Critical, got {level_1}"
    print("✅ Case 1 passed.")

    # Test Case 2: Kidney Failure / Dialysis (Medical emergency floor)
    case_2 = {
        "title": "Bail request on medical grounds",
        "summary": "Petitioner suffers from kidney failure and requires dialysis three times a week in ICU.",
        "case_type": "Bail Matter",
        "case_age_days": 5
    }
    score_2 = compute_priority_score(case_2)
    level_2 = score_to_level(score_2)
    print(f"Case 2 (Kidney Failure / ICU): Score = {score_2}, Level = {level_2}")
    assert score_2 >= 86.0, f"Expected Critical floor >= 86.0, got {score_2}"
    assert level_2 == "Critical", f"Expected Critical, got {level_2}"
    print("✅ Case 2 passed.")

    # Test Case 3: Custodial Torture (Humanitarian / custody floor)
    case_3 = {
        "title": "Police torture complaint",
        "summary": "Allegations of custodial torture and third degree police violence while in custody.",
        "case_type": "Criminal Case",
        "case_age_days": 20
    }
    score_3 = compute_priority_score(case_3)
    level_3 = score_to_level(score_3)
    print(f"Case 3 (Custodial Torture): Score = {score_3}, Level = {level_3}")
    assert score_3 >= 86.0, f"Expected Critical floor >= 86.0, got {score_3}"
    assert level_3 == "Critical", f"Expected Critical, got {level_3}"
    print("✅ Case 3 passed.")

    # Test Case 4: Illegal Detention (Habeas corpus floor)
    case_4 = {
        "title": "Release from unlawful custody",
        "summary": "Habeas corpus petition challenging illegal detention of the petitioner without warrant.",
        "case_type": "Writ Petition",
        "case_age_days": 1
    }
    score_4 = compute_priority_score(case_4)
    level_4 = score_to_level(score_4)
    print(f"Case 4 (Illegal Detention): Score = {score_4}, Level = {level_4}")
    assert score_4 >= 86.0, f"Expected Critical floor >= 86.0, got {score_4}"
    assert level_4 == "Critical", f"Expected Critical, got {level_4}"
    print("✅ Case 4 passed.")

    # Test Case 5: Routine Commercial Contract (Low/Medium priority)
    case_5 = {
        "title": "Breach of supplier agreement",
        "summary": "Recovery of dues under commercial sales agreement between two vendors.",
        "case_type": "Civil Suit",
        "case_age_days": 30
    }
    score_5 = compute_priority_score(case_5)
    level_5 = score_to_level(score_5)
    print(f"Case 5 (Commercial Contract): Score = {score_5}, Level = {level_5}")
    assert score_5 < 60.0, f"Expected Medium/Low priority score < 60, got {score_5}"
    assert level_5 in ["Low", "Medium"], f"Expected Low or Medium, got {level_5}"
    print("✅ Case 5 passed.")

    print("🎉 ALL PRIORITY ENGINE VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_priority_engine()
