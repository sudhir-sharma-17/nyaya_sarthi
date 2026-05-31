import sys
import os

# Add workspace root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.intelligence import IntelligenceEngine

def run_test():
    engine = IntelligenceEngine()
    
    # --------------------------------------------------
    # Test case 1: Standard Karnataka High Court & clean Bench
    # --------------------------------------------------
    text1 = """
    IN THE HIGH COURT OF KARNATAKA AT BENGALURU
    Court No. 3
    Page 1 of 5
    
    PETITIONER:
    RAMESH KUMAR
    
    RESPONDENT:
    State of Karnataka
    
    Bench: Justice A.K. Sharma, Justice P. Reddy
    
    Author: Justice A.K. Sharma
    """
    
    print("=== TEST CASE 1 ===")
    cleaned1 = engine._clean_text(text1)
    meta1 = engine._extract_structured_metadata(cleaned1)
    print("Petitioner:", meta1["petitioner"])
    print("Respondent:", meta1["respondent"])
    print("Bench:", meta1["bench"])
    print("Author:", meta1["author_judge"])
    print("Court:", meta1["court_name"])
    
    assert meta1["petitioner"] == "RAMESH KUMAR"
    assert meta1["respondent"] == "State of Karnataka"
    assert meta1["bench"] == "A.K. Sharma, P. Reddy"
    assert meta1["author_judge"] == "A.K. Sharma"
    assert meta1["court_name"] == "High Court of Karnataka"
    print("✅ TEST CASE 1 PASSED")
    
    # --------------------------------------------------
    # Test case 2: Unmapped Court header must return Not Available
    # --------------------------------------------------
    text2 = """
    HIGH COURT OF DELHI
    
    PETITIONER:
    SURESH SINGH
    
    RESPONDENT:
    Union of India
    
    CORAM:
    N.L. Untwalia, J.
    P.N. Bhagwati, J.
    """
    
    print("\n=== TEST CASE 2 ===")
    cleaned2 = engine._clean_text(text2)
    meta2 = engine._extract_structured_metadata(cleaned2)
    print("Petitioner:", meta2["petitioner"])
    print("Respondent:", meta2["respondent"])
    print("Bench:", meta2["bench"])
    print("Author (Fallback to first Bench judge):", meta2["author_judge"])
    print("Court (Should be Not Available under strict rules):", meta2["court_name"])
    
    assert meta2["petitioner"] == "SURESH SINGH"
    assert meta2["respondent"] == "Union of India"
    assert meta2["bench"] == "N.L. Untwalia, P.N. Bhagwati"
    assert meta2["author_judge"] == "N.L. Untwalia"
    assert meta2["court_name"] == "Not Available"
    print("✅ TEST CASE 2 PASSED")

    # --------------------------------------------------
    # Test case 3: BEFORE pattern / Supreme Court of India
    # --------------------------------------------------
    text3 = """
    IN THE SUPREME COURT OF INDIA
    
    Appellant:
    Anil Ambani
    
    Respondent:
    SEBI
    
    BEFORE:
    Hon'ble Justice N.L. Untwalia
    Hon'ble Justice P.N. Bhagwati
    """
    
    print("\n=== TEST CASE 3 ===")
    cleaned3 = engine._clean_text(text3)
    meta3 = engine._extract_structured_metadata(cleaned3)
    print("Petitioner:", meta3["petitioner"])
    print("Respondent:", meta3["respondent"])
    print("Bench:", meta3["bench"])
    print("Author (Fallback to first Bench judge):", meta3["author_judge"])
    print("Court:", meta3["court_name"])
    
    assert meta3["petitioner"] == "Anil Ambani"
    assert meta3["respondent"] == "SEBI"
    assert meta3["bench"] == "N.L. Untwalia, P.N. Bhagwati"
    assert meta3["author_judge"] == "N.L. Untwalia"
    assert meta3["court_name"] == "Supreme Court of India"
    print("✅ TEST CASE 3 PASSED")

    # --------------------------------------------------
    # Test case 4: NO Bench-to-Author fallback (Must return Not Available)
    # --------------------------------------------------
    text4 = """
    PETITIONER:
    A
    
    RESPONDENT:
    B
    
    Author: Justice N.L. Untwalia
    """
    
    print("\n=== TEST CASE 4 ===")
    cleaned4 = engine._clean_text(text4)
    meta4 = engine._extract_structured_metadata(cleaned4)
    print("Petitioner:", meta4["petitioner"])
    print("Respondent:", meta4["respondent"])
    print("Bench (Should be Not Available):", meta4["bench"])
    print("Author:", meta4["author_judge"])
    print("Court:", meta4["court_name"])
    
    assert meta4["author_judge"] == "N.L. Untwalia"
    assert meta4["bench"] == "Not Available"
    assert meta4["court_name"] == "Not Available"
    print("✅ TEST CASE 4 PASSED")

    # --------------------------------------------------
    # Test case 5: Explicit COURT: label pattern
    # --------------------------------------------------
    text5 = """
    COURT: High Court of Judicature at Bombay
    
    Petitioner:
    X
    
    Respondent:
    Y
    
    PRESENT:
    Justice A.K. Sharma
    """
    
    print("\n=== TEST CASE 5 ===")
    cleaned5 = engine._clean_text(text5)
    meta5 = engine._extract_structured_metadata(cleaned5)
    print("Court (Exactly extracted):", meta5["court_name"])
    print("Bench:", meta5["bench"])
    
    assert meta5["court_name"] == "High Court of Judicature at Bombay"
    assert meta5["bench"] == "A.K. Sharma"
    print("✅ TEST CASE 5 PASSED")

    # --------------------------------------------------
    # Test case 6: High Court of Andhra Pradesh pattern
    # --------------------------------------------------
    text6 = """
    IN THE HIGH COURT OF ANDHRA PRADESH AT AMARAVATI
    
    Petitioner:
    P
    
    Respondent:
    R
    """
    
    print("\n=== TEST CASE 6 ===")
    cleaned6 = engine._clean_text(text6)
    meta6 = engine._extract_structured_metadata(cleaned6)
    print("Court:", meta6["court_name"])
    
    assert meta6["court_name"] == "High Court of Andhra Pradesh"
    print("✅ TEST CASE 6 PASSED")

if __name__ == "__main__":
    run_test()
