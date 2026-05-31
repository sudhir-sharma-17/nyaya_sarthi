from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.case_model import Case, Document
from core.intelligence import intelligence_engine
from core.analytics import analytics_engine
from core.priority_engine import compute_priority_score_from_orm, score_to_level
from core.engine import engine_room
from typing import List, Optional
import uuid
import json
from datetime import datetime

router = APIRouter()

def _serialize_bench(value) -> str:
    """Coerce bench (list | str | None) to a plain comma-separated string for SQLite."""
    if value is None:
        return "Not Available"
    if isinstance(value, list):
        cleaned = [str(v).strip() for v in value if str(v).strip()]
        return ", ".join(cleaned) if cleaned else "Not Available"
    s = str(value).strip()
    return s if s else "Not Available"

@router.post("/")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    content = await file.read()
    extracted_data = await intelligence_engine.extract_case_info(content, file.filename)
    
    if "error" in extracted_data:
        raise HTTPException(status_code=400, detail=extracted_data["error"])
        
    # Case Classification & Priority Scoring
    case_type = extracted_data.get("case_type_inferred", "General")
    extracted_data["case_type"] = case_type
    
    priority_data = analytics_engine.calculate_priority_score(extracted_data, extracted_data.get("full_text", ""))
    
    raw_case_num = extracted_data.get("case_number_extracted")
    if not raw_case_num or str(raw_case_num).lower() in ["unknown", "not detected", "none", ""]:
        raw_case_num = "No ID"
        
    case_number = f"{raw_case_num} | {file.filename}"
    
    # Check for existing case to prevent IntegrityError
    existing_case = db.query(Case).filter(Case.case_number == case_number).first()
    
    if existing_case:
        # Update existing record
        existing_case.title = extracted_data.get("case_title")
        existing_case.court_name = extracted_data.get("court_name")
        existing_case.bench = _serialize_bench(extracted_data.get("bench"))
        existing_case.case_type = case_type
        existing_case.petitioner = extracted_data.get("petitioner")
        existing_case.respondent = extracted_data.get("respondent")
        existing_case.summary = extracted_data.get("summary") or extracted_data.get("legal_summary")
        existing_case.legal_issue = extracted_data.get("core_legal_issue") or extracted_data.get("legal_issue")
        existing_case.relief_sought = extracted_data.get("relief_sought")
        existing_case.urgency_score = priority_data["urgency"]
        existing_case.backlog_score = priority_data["backlog"]
        existing_case.priority_level = priority_data["level"]
        existing_case.reasoning = priority_data["explanation"]
        existing_case.is_active = True
        existing_case.extraction_method = extracted_data.get("extraction_method")
        existing_case.status = "Processed"
        case_to_save = existing_case
        # Unified priority score – computed after all fields are set
        existing_case.priority_score = compute_priority_score_from_orm(existing_case)
    else:
        new_case = Case(
            case_number=case_number,
            title=extracted_data.get("case_title"),
            court_name=extracted_data.get("court_name"),
            bench=_serialize_bench(extracted_data.get("bench")),
            case_type=case_type,
            petitioner=extracted_data.get("petitioner"),
            respondent=extracted_data.get("respondent"),
            summary=extracted_data.get("summary") or extracted_data.get("legal_summary"),
            legal_issue=extracted_data.get("core_legal_issue") or extracted_data.get("legal_issue"),
            relief_sought=extracted_data.get("relief_sought"),
            urgency_score=priority_data["urgency"],
            backlog_score=priority_data["backlog"],
            confidence_score=extracted_data.get("confidence_score", 0),
            priority_level=priority_data["level"],
            reasoning=priority_data["explanation"],
            humanitarian_flag=analytics_engine.evaluate_humanitarian(extracted_data),
            extracted_statutes=json.dumps(extracted_data.get("acts", []) + extracted_data.get("sections", [])),
            citations=json.dumps(extracted_data.get("citations", [])),
            case_age_days=extracted_data.get("case_age_days", 0),
            extraction_method=extracted_data.get("extraction_method"),
            raw_content=json.dumps(extracted_data),
            status="Processed",
            is_active=True
        )
        db.add(new_case)
        case_to_save = new_case
        # Unified priority score – computed after all fields are set on the ORM object
        new_case.priority_score = compute_priority_score_from_orm(new_case)

    # Handle Dates & Case Age
    from dateutil.relativedelta import relativedelta
    
    f_date = extracted_data.get("filing_date")
    j_date = extracted_data.get("judgment_date")
    h_date = extracted_data.get("hearing_date")
    
    parsed_dates = {}
    for k, v in [("filing_date", f_date), ("judgment_date", j_date), ("hearing_date", h_date)]:
        if v and str(v).lower() not in ["not available", "none", "unknown", ""]:
            try:
                dt = datetime.strptime(str(v), "%Y-%m-%d")
                parsed_dates[k] = dt
                setattr(case_to_save, k, dt)
            except:
                setattr(case_to_save, k, None)
        else:
            setattr(case_to_save, k, None)

    # Compute Precise Case Age
    from app.routes.schedule_routes import get_sim_date
    sim_date = get_sim_date(db)
    sim_datetime = datetime(sim_date.year, sim_date.month, sim_date.day)

    base_date = parsed_dates.get("filing_date")
    if base_date:
        diff = relativedelta(sim_datetime, base_date)
        age_str = f"{diff.years} years, {diff.months} months, {diff.days} days"
        case_to_save.case_age_days = max((sim_datetime - base_date).days, 0)
        extracted_data["formatted_age"] = age_str
    else:
        case_to_save.case_age_days = 0
        extracted_data["formatted_age"] = "Not Available"

    case_to_save.raw_content = json.dumps(extracted_data)

    db.commit()
    db.refresh(case_to_save)
    
    # Save to vector store for semantic search/clustering (non-critical)
    try:
        engine_room.add_to_vector_store(case_to_save.id, case_to_save.summary or case_to_save.title, extracted_data)
    except Exception as ve:
        print(f"Vector store warning (non-critical): {ve}")
    
    return {
        "message": "Success", 
        "case_id": case_to_save.id, 
        "case_number": case_number,
        "extraction_method": extracted_data.get("extraction_method", "Unknown"),
        "extracted_length": extracted_data.get("extracted_length", 0),
        "text_preview": extracted_data.get("text_preview", ""),
        "confidence_score": extracted_data.get("confidence_score", 0)
    }


@router.post("/bulk")
async def upload_bulk_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    results = []
    processed_cases = []
    import asyncio
    for file in files:
        content = await file.read()
        try:
            # 1. Advanced Extraction
            extracted_data = await intelligence_engine.extract_case_info(content, file.filename)
            if "error" in extracted_data:
                results.append({"file": file.filename, "error": extracted_data["error"]})
                continue
                
            # 2. Case Classification & Priority Scoring
            # Use the AI-inferred case type from the primary extraction step
            case_type = extracted_data.get("case_type_inferred", "General")

            
            # 3. Priority & Backlog Scoring
            extracted_data["case_type"] = case_type
            priority_data = analytics_engine.calculate_priority_score(extracted_data, extracted_data.get("full_text", ""))
            
            raw_case_num = extracted_data.get("case_number_extracted")
            if not raw_case_num or str(raw_case_num).lower() in ["unknown", "not detected", "none", ""]:
                raw_case_num = "No ID"
                
            # GUARANTEE UNIQUENESS: Append filename to prevent multi-file uploads of the same case from overwriting each other.
            # The frontend's sanitize_metadata_field will automatically strip the filename out for clean display.
            case_number = f"{raw_case_num} | {file.filename}"
            
            # 4. Save to DB
            # Check for existing case to prevent IntegrityError
            existing_case = db.query(Case).filter(Case.case_number == case_number).first()
            
            if existing_case:
                # Update existing record
                existing_case.title = extracted_data.get("case_title")
                existing_case.court_name = extracted_data.get("court_name")
                existing_case.bench = _serialize_bench(extracted_data.get("bench"))
                existing_case.case_type = case_type
                existing_case.petitioner = extracted_data.get("petitioner")
                existing_case.respondent = extracted_data.get("respondent")
                existing_case.summary = extracted_data.get("summary") or extracted_data.get("legal_summary")
                existing_case.legal_issue = extracted_data.get("core_legal_issue") or extracted_data.get("legal_issue")
                existing_case.relief_sought = extracted_data.get("relief_sought")
                existing_case.urgency_score = priority_data["urgency"]
                existing_case.backlog_score = priority_data["backlog"]
                existing_case.priority_level = priority_data["level"]
                existing_case.reasoning = priority_data["explanation"]
                existing_case.is_active = True
                existing_case.extraction_method = extracted_data.get("extraction_method")
                existing_case.status = "Processed"
                case_to_save = existing_case
                existing_case.priority_score = compute_priority_score_from_orm(existing_case)
            else:
                new_case = Case(
                    case_number=case_number,
                    title=extracted_data.get("case_title"),
                    court_name=extracted_data.get("court_name"),
                    bench=_serialize_bench(extracted_data.get("bench")),
                    case_type=case_type,
                    petitioner=extracted_data.get("petitioner"),
                    respondent=extracted_data.get("respondent"),
                    summary=extracted_data.get("summary") or extracted_data.get("legal_summary"),
                    legal_issue=extracted_data.get("core_legal_issue") or extracted_data.get("legal_issue"),
                    relief_sought=extracted_data.get("relief_sought"),
                    urgency_score=priority_data["urgency"],
                    backlog_score=priority_data["backlog"],
                    confidence_score=extracted_data.get("confidence_score", 0),
                    priority_level=priority_data["level"],
                    reasoning=priority_data["explanation"],
                    humanitarian_flag=analytics_engine.evaluate_humanitarian(extracted_data),
                    extracted_statutes=json.dumps(extracted_data.get("acts", []) + extracted_data.get("sections", [])),
                    citations=json.dumps(extracted_data.get("citations", [])),
                    case_age_days=extracted_data.get("case_age_days", 0),
                    extraction_method=extracted_data.get("extraction_method"),
                    raw_content=json.dumps(extracted_data),
                    status="Processed",
                    is_active=True
                )
                db.add(new_case)
                case_to_save = new_case
                new_case.priority_score = compute_priority_score_from_orm(new_case)

            # Handle Dates & Case Age
            from dateutil.relativedelta import relativedelta
            
            f_date = extracted_data.get("filing_date")
            j_date = extracted_data.get("judgment_date")
            h_date = extracted_data.get("hearing_date")
            
            # Map strings to datetime objects
            parsed_dates = {}
            for k, v in [("filing_date", f_date), ("judgment_date", j_date), ("hearing_date", h_date)]:
                if v and str(v).lower() not in ["not available", "none", "unknown", ""]:
                    try:
                        dt = datetime.strptime(str(v), "%Y-%m-%d")
                        parsed_dates[k] = dt
                        setattr(case_to_save, k, dt)
                    except:
                        setattr(case_to_save, k, None)
                else:
                    # Crucially, overwrite old buggy dates with None if not available
                    setattr(case_to_save, k, None)

            # Compute Precise Case Age
            # Strictly use Filing Date ONLY as per rules
            from app.routes.schedule_routes import get_sim_date
            sim_date = get_sim_date(db)
            sim_datetime = datetime(sim_date.year, sim_date.month, sim_date.day)

            base_date = parsed_dates.get("filing_date")
            if base_date:
                diff = relativedelta(sim_datetime, base_date)
                age_str = f"{diff.years} years, {diff.months} months, {diff.days} days"
                case_to_save.case_age_days = max((sim_datetime - base_date).days, 0) # Keep days for sorting
                # Store the formatted string in a temporary attribute or metadata
                extracted_data["formatted_age"] = age_str
            else:
                case_to_save.case_age_days = 0
                extracted_data["formatted_age"] = "Not Available"

            case_to_save.raw_content = json.dumps(extracted_data)

            db.commit()
            db.refresh(case_to_save)


            
            # Add to vector store
            try:
                engine_room.add_to_vector_store(case_to_save.id, case_to_save.summary or case_to_save.title, extracted_data)
            except Exception as ve:
                print(f"Vector store warning: {ve}")
                
            processed_cases.append(case_to_save)
            results.append({
                "file": file.filename, 
                "case_number": case_number,
                "case_id": case_to_save.id,
                "status": "success",
                "case_type": case_type,
                "urgency_score": priority_data["urgency"]
            })
            
            # Intelligent Pacing: Prevent API Rate Limits from silently failing final files in batch
            await asyncio.sleep(2)
        except Exception as e:
            results.append({"file": file.filename, "error": str(e)})
            
    # 5. Offload Semantic Clustering to Background
    if processed_cases:
        background_tasks.add_task(perform_background_clustering, db)
            
    return {"processed": len(results), "results": results}

async def perform_background_clustering(db: Session):
    """Heavy semantic clustering moved out of request cycle to prevent timeouts."""
    try:
        # Re-cluster all processed cases or pending cases
        all_pending = db.query(Case).filter(Case.status == "Processed").all()
        if len(all_pending) >= 2:
            texts = [f"{c.title} {c.summary} {c.legal_issue}" for c in all_pending]
            ids = [c.id for c in all_pending]
            embeddings = engine_room.get_embeddings(texts)
            clusters = engine_room.cluster_cases(embeddings, ids)
            
            for cluster_id, member_ids in clusters.items():
                # Get a label for the cluster based on members
                representative_cases = [db.query(Case).filter(Case.id == mid).first() for mid in member_ids]
                summaries = [c.summary for c in representative_cases if c.summary]
                cluster_info = await intelligence_engine.summarize_cluster(summaries)
                
                for mid in member_ids:
                    case_to_update = db.query(Case).filter(Case.id == mid).first()
                    if case_to_update:
                        case_to_update.cluster_id = str(cluster_id)
                        case_to_update.cluster_label = cluster_info.get("label", "Legal Cluster")
                db.commit()
    except Exception as ce:
        print(f"Background Clustering Error: {ce}")

@router.post("/cases/{case_id}/reprocess")
async def reprocess_case(case_id: int, db: Session = Depends(get_db)):
    """Manually trigger AI re-analysis for a specific case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    try:
        # 1. Parse existing raw content to find full text
        import json, ast
        raw_str = case.raw_content or "{}"
        raw = {}
        try: raw = json.loads(raw_str)
        except: raw = ast.literal_eval(raw_str)
        
        text = raw.get("full_text", "")
        if not text:
            return {"status": "error", "message": "No source text found for reprocessing."}
            
        # 2. Re-run Intelligence Engine
        extracted_data = await intelligence_engine.extract_case_info(text.encode(), case.case_number)
        
        # 3. Re-run Analytics Engine
        priority_data = analytics_engine.calculate_priority_score(extracted_data, text)
        case_type = extracted_data.get("case_type_inferred", "General")
        
        # 4. Update Database Record
        case.title = extracted_data.get("case_title")
        case.court_name = extracted_data.get("court_name")
        case.bench = _serialize_bench(extracted_data.get("bench"))
        case.case_type = case_type
        case.petitioner = extracted_data.get("petitioner")
        case.respondent = extracted_data.get("respondent")
        case.summary = extracted_data.get("summary") or extracted_data.get("legal_summary")
        case.legal_issue = extracted_data.get("core_legal_issue") or extracted_data.get("legal_issue")
        case.relief_sought = extracted_data.get("relief_sought")
        
        # --- Date Updates & Case Age ---
        import dateparser
        for date_key in ["filing_date", "judgment_date", "hearing_date"]:
            val = extracted_data.get(date_key)
            if val and val != "Not Available":
                parsed = dateparser.parse(str(val))
                if parsed: setattr(case, date_key, parsed)
        
        # Re-calculate case age if dates changed relative to active simulated date
        from app.routes.schedule_routes import get_sim_date
        sim_date = get_sim_date(db)
        sim_datetime = datetime(sim_date.year, sim_date.month, sim_date.day)

        if case.filing_date:
            case.case_age_days = max((sim_datetime - case.filing_date).days, 0)
        else:
            case.case_age_days = 0

        case.urgency_score = priority_data["urgency"]
        case.backlog_score = priority_data["backlog"]
        case.confidence_score = extracted_data.get("confidence_score", 0)
        case.priority_level = priority_data["level"]
        case.reasoning = priority_data["explanation"]
        case.humanitarian_flag = analytics_engine.evaluate_humanitarian(extracted_data)
        case.extracted_statutes = json.dumps(extracted_data.get("acts", []) + extracted_data.get("sections", []))
        case.citations = json.dumps(extracted_data.get("citations", []))
        case.raw_content = json.dumps(extracted_data)
        # Refresh the unified priority score after all fields updated
        case.priority_score = compute_priority_score_from_orm(case)
        
        db.commit()
        return {"status": "success", "message": f"Successfully reprocessed case: {case.title}"}
        
    except Exception as e:
        print(f"Reprocessing failed: {e}")
        return {"status": "error", "message": str(e)}

@router.delete("/cases/{case_id}")
async def delete_case(case_id: int, db: Session = Depends(get_db)):
    """Soft-delete a specific case (hide from registry)."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    try:
        case.is_active = False
        db.commit()
        return {"status": "success", "message": f"Successfully deleted case ID: {case_id}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cases/{case_id}/undo")
async def undo_delete_case(case_id: int, db: Session = Depends(get_db)):
    """Restore a soft-deleted case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    try:
        case.is_active = True
        db.commit()
        return {"status": "success", "message": f"Successfully restored case ID: {case_id}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cases/clear/all")
async def clear_all_cases(db: Session = Depends(get_db)):
    """Soft-delete all cases from the database registry."""
    try:
        db.query(Case).update({Case.is_active: False})
        db.commit()
        return {"status": "success", "message": "All cases have been removed from the registry."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
