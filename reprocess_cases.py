import asyncio
import json
import sqlite3
from core.intelligence import IntelligenceEngine
from core.analytics import AnalyticsEngine
from app.models.case_model import Case
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Database setup
SQLALCHEMY_DATABASE_URL = f"sqlite:///./court_ai.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

intelligence_engine = IntelligenceEngine()
analytics_engine = AnalyticsEngine()

async def reprocess_all():
    db = SessionLocal()
    cases = db.query(Case).all()
    print(f"Reprocessing {len(cases)} cases...")
    
    for c in cases:
        print(f"Analyzing: {c.title or c.case_number}...")
        try:
            # Robust parsing for raw_content
            raw = {}
            raw_str = c.raw_content or "{}"
            try:
                import ast
                raw = json.loads(raw_str)
            except:
                try: raw = ast.literal_eval(raw_str)
                except: pass
                
            text = raw.get('full_text', '')
            if not text:
                print(f"⚠️ No text for {c.id}, skipping.")
                continue
            
            # Re-run extraction
            # Pass text directly as bytes
            extracted = await intelligence_engine.extract_case_info(text.encode(), c.case_number)
            
            # Re-run analytics
            priority_data = analytics_engine.calculate_priority_score(extracted, text)
            
            # Update case
            c.title = extracted.get("case_title")
            c.summary = extracted.get("summary")
            c.legal_issue = extracted.get("core_legal_issue")
            c.relief_sought = extracted.get("relief_sought")
            c.urgency_score = priority_data["urgency"]
            c.backlog_score = priority_data["backlog"]
            c.priority_score = priority_data["score"]
            c.priority_level = priority_data["level"]
            c.reasoning = priority_data["explanation"]
            c.raw_content = json.dumps(extracted)
            
            db.commit()
            print(f"✅ Success: {c.title}")
        except Exception as e:
            print(f"❌ Failed: {c.id} - {e}")
            
    db.close()

if __name__ == "__main__":
    asyncio.run(reprocess_all())
