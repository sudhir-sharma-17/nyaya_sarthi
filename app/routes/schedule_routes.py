from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.db import get_db
from app.models.case_model import Case
from core.priority_engine import compute_priority_score_from_orm, score_to_level
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter()

# ── Pydantic Request Models ──

class PostponeRequest(BaseModel):
    case_id: int
    postponed_until: str  # YYYY-MM-DD
    reason: str

class EvidenceRequest(BaseModel):
    case_id: int
    evidence_deadline: str  # YYYY-MM-DD
    evidence_notes: str

class ReadinessRequest(BaseModel):
    case_id: int
    evidence_uploaded: Optional[bool] = None
    documents_verified: Optional[bool] = None
    parties_notified: Optional[bool] = None
    investigation_completed: Optional[bool] = None

class AssignSlotRequest(BaseModel):
    case_id: int
    hearing_date: str  # YYYY-MM-DD
    hearing_time: str  # Morning Session (10 AM - 1 PM) or Afternoon Session (2 PM - 5 PM)
    court_room: str
    judge_name: str

class UpdateStatusRequest(BaseModel):
    case_id: int
    status: str

class SimDateRequest(BaseModel):
    days: int  # 1, 7, 30, or 0 to reset

class EmergencyOverrideRequest(BaseModel):
    case_id: int
    is_bail_matter: Optional[bool] = None
    is_child_protection: Optional[bool] = None
    is_medical_emergency: Optional[bool] = None
    is_domestic_violence: Optional[bool] = None

# ── Helper Functions ──

def parse_date(date_val) -> Optional[datetime]:
    if not date_val:
        return None
    if isinstance(date_val, datetime):
        return date_val
    try:
        dt_str = str(date_val).split()[0]  # Get YYYY-MM-DD
        return datetime.strptime(dt_str, "%Y-%m-%d")
    except Exception:
        return None

def get_sim_date(db: Session) -> datetime.date:
    try:
        row = db.execute(text("SELECT value FROM system_settings WHERE key = 'current_sim_date'")).fetchone()
        if row:
            return datetime.strptime(row[0], "%Y-%m-%d").date()
    except Exception as e:
        print(f"Error reading current_sim_date: {e}")
    # Default fallback
    return datetime.utcnow().date()

def set_sim_date(db: Session, new_date: datetime.date):
    db.execute(
        text("UPDATE system_settings SET value = :val WHERE key = 'current_sim_date'"),
        {"val": new_date.strftime("%Y-%m-%d")}
    )
    db.commit()

def calculate_priority_key(case) -> tuple:
    """
    Returns a sort key tuple for hearing queue ordering.
    Uses the centralized priority_engine as the single source of truth.
    """
    is_emergency = bool(
        getattr(case, "humanitarian_flag", False) or
        getattr(case, "is_bail_matter", False) or
        getattr(case, "is_child_protection", False) or
        getattr(case, "is_medical_emergency", False) or
        getattr(case, "is_domestic_violence", False)
    )
    # Single source of truth – delegate to centralized engine
    priority_score = compute_priority_score_from_orm(case)
    age = getattr(case, "case_age_days", 0) or 0
    return (is_emergency, priority_score, age)

# ── API Endpoints ──

@router.get("/sim_date")
def get_simulation_date(db: Session = Depends(get_db)):
    """Retrieve the current simulated court date."""
    sim_date = get_sim_date(db)
    return {"sim_date": sim_date.strftime("%Y-%m-%d")}

@router.post("/sim_date")
def advance_simulation_date(req: SimDateRequest, db: Session = Depends(get_db)):
    """Advance the court simulation date and auto-update case status."""
    if req.days == 0:
        new_date = datetime.utcnow().date()
    else:
        current = get_sim_date(db)
        new_date = current + timedelta(days=req.days)
        
    set_sim_date(db, new_date)
    
    # Auto-resume adjourned/postponed cases if their postponement date has arrived
    postponed_cases = db.query(Case).filter(
        Case.is_active == True,
        Case.status == "Adjourned / Postponed"
    ).all()
    
    resumed_count = 0
    for case in postponed_cases:
        p_date = parse_date(case.postponed_until)
        if p_date and p_date.date() <= new_date:
            case.status = "Scheduled"
            case.postponed_until = None
            case.postponement_reason = None
            resumed_count += 1
            
    # Recalculate case age and priority scores for all active cases relative to the new simulation date
    active_cases = db.query(Case).filter(Case.is_active == True).all()
    for case in active_cases:
        if case.filing_date:
            fd = case.filing_date
            fd_date = fd.date() if hasattr(fd, "date") else fd
            case.case_age_days = max((new_date - fd_date).days, 0)
        else:
            case.case_age_days = 0
        case.priority_score = compute_priority_score_from_orm(case)
        case.priority_level = score_to_level(case.priority_score)
        
    db.commit()
    
    return {
        "message": f"Date advanced to {new_date.strftime('%Y-%m-%d')}",
        "new_sim_date": new_date.strftime("%Y-%m-%d"),
        "resumed_cases_count": resumed_count
    }

@router.get("/queue")
def get_hearing_queue(db: Session = Depends(get_db)):
    """
    Returns the ordered list of eligible cases for hearing.
    Excludes Resolved, Closed, and active Postponed cases.
    """
    sim_date = get_sim_date(db)
    
    # Fetch all active cases
    cases = db.query(Case).filter(
        Case.is_active == True,
        Case.status != "Resolved",
        Case.status != "Closed"
    ).all()
    
    queue_list = []
    
    for case in cases:
        # Check if currently postponed
        p_date = parse_date(case.postponed_until)
        if case.status == "Adjourned / Postponed" and p_date and p_date.date() > sim_date:
            # Case is paused in postponement, skip scheduling queue
            continue
            
        # Determine readiness
        is_ready = bool(
            case.evidence_uploaded and
            case.documents_verified and
            case.parties_notified and
            case.investigation_completed
        )
        
        is_emergency, score, age = calculate_priority_key(case)
        
        queue_list.append({
            "id": case.id,
            "case_number": case.case_number,
            "title": case.title,
            "status": case.status,
            "case_type": case.case_type,
            "priority_level": case.priority_level,
            "priority_score": score,
            "is_emergency": is_emergency,
            "is_ready": is_ready,
            "adjournment_count": case.adjournment_count or 0,
            "case_age_days": age,
            # Readiness checklists
            "evidence_uploaded": bool(case.evidence_uploaded),
            "documents_verified": bool(case.documents_verified),
            "parties_notified": bool(case.parties_notified),
            "investigation_completed": bool(case.investigation_completed),
            "evidence_deadline": case.evidence_deadline.strftime("%Y-%m-%d") if case.evidence_deadline else None,
            "evidence_notes": case.evidence_notes,
            # Postponement details
            "postponed_until": case.postponed_until.strftime("%Y-%m-%d") if case.postponed_until else None,
            "postponement_reason": case.postponement_reason,
            # Assigned Slot
            "hearing_date": case.hearing_date.strftime("%Y-%m-%d") if case.hearing_date else None,
            "hearing_time": case.hearing_time,
            "court_room": case.court_room,
            "judge_name": case.judge_name,
            # Urgent tags
            "is_bail_matter": bool(case.is_bail_matter),
            "is_child_protection": bool(case.is_child_protection),
            "is_medical_emergency": bool(case.is_medical_emergency),
            "is_domestic_violence": bool(case.is_domestic_violence),
        })
        
    # Sort queue: Emergency overrides first, then priority score descending, then case age descending
    queue_list.sort(key=lambda x: (x["is_emergency"], x["priority_score"], x["case_age_days"]), reverse=True)
    
    return queue_list

@router.get("/slots")
def get_daily_slots(date_str: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Retrieve hearings scheduled for a specific date (default: simulation date)."""
    if not date_str:
        q_date = get_sim_date(db)
    else:
        try:
            q_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            q_date = get_sim_date(db)
            
    cases = db.query(Case).filter(
        Case.is_active == True,
        Case.status != "Resolved",
        Case.status != "Closed"
    ).all()
    
    slots_data = []
    for c in cases:
        if c.hearing_date:
            h_date = parse_date(c.hearing_date)
            if h_date and h_date.date() == q_date:
                slots_data.append({
                    "id": c.id,
                    "case_number": c.case_number,
                    "title": c.title,
                    "status": c.status,
                    "hearing_time": c.hearing_time or "Morning Session (10 AM - 1 PM)",
                    "court_room": c.court_room or "Court Room 1",
                    "judge_name": c.judge_name or "Hon'ble Judge",
                    "priority_level": c.priority_level,
                    "is_ready": bool(c.evidence_uploaded and c.documents_verified and c.parties_notified and c.investigation_completed)
                })
                
    return {
        "date": q_date.strftime("%Y-%m-%d"),
        "hearings": slots_data
    }

@router.post("/assign_slot")
def assign_hearing_slot(req: AssignSlotRequest, db: Session = Depends(get_db)):
    """Assign case to a specific hearing slot."""
    case = db.query(Case).filter(Case.id == req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    try:
        case.hearing_date = datetime.strptime(req.hearing_date, "%Y-%m-%d")
        case.hearing_time = req.hearing_time
        case.court_room = req.court_room
        case.judge_name = req.judge_name
        case.status = "Scheduled"
        db.commit()
        return {"status": "success", "message": f"Successfully scheduled case {case.case_number}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update_case_status")
def update_case_status(req: UpdateStatusRequest, db: Session = Depends(get_db)):
    """Manually update the status of a case."""
    case = db.query(Case).filter(Case.id == req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    case.status = req.status
    if req.status in ["Resolved", "Closed"]:
        # Free slot details
        case.hearing_date = None
        case.hearing_time = None
        case.court_room = None
        
    db.commit()
    return {"status": "success", "message": f"Case status updated to {req.status}"}

@router.post("/postpone")
def postpone_case(req: PostponeRequest, db: Session = Depends(get_db)):
    """Postpone a case, free its hearing slot, and increment adjournment count."""
    case = db.query(Case).filter(Case.id == req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    try:
        case.status = "Adjourned / Postponed"
        case.postponed_until = datetime.strptime(req.postponed_until, "%Y-%m-%d")
        case.postponement_reason = req.reason
        case.adjournment_count = (case.adjournment_count or 0) + 1
        
        # Free current scheduling slot
        case.hearing_date = None
        case.hearing_time = None
        case.court_room = None
        
        db.commit()
        return {"status": "success", "message": f"Case postponed until {req.postponed_until} due to: {req.reason}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/request_evidence")
def request_evidence(req: EvidenceRequest, db: Session = Depends(get_db)):
    """Pause case and set an evidence collection deadline."""
    case = db.query(Case).filter(Case.id == req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    try:
        case.status = "Awaiting Evidence"
        case.evidence_deadline = datetime.strptime(req.evidence_deadline, "%Y-%m-%d")
        case.evidence_notes = req.evidence_notes
        case.evidence_uploaded = False  # Reset upload flag to pending
        
        # Free hearing slot while evidence is being collected
        case.hearing_date = None
        case.hearing_time = None
        case.court_room = None
        
        db.commit()
        return {"status": "success", "message": f"Evidence requested with deadline {req.evidence_deadline}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify_readiness")
def verify_readiness(req: ReadinessRequest, db: Session = Depends(get_db)):
    """Toggle readiness flags for a case."""
    case = db.query(Case).filter(Case.id == req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    if req.evidence_uploaded is not None:
        case.evidence_uploaded = req.evidence_uploaded
    if req.documents_verified is not None:
        case.documents_verified = req.documents_verified
    if req.parties_notified is not None:
        case.parties_notified = req.parties_notified
    if req.investigation_completed is not None:
        case.investigation_completed = req.investigation_completed
        
    db.commit()
    return {"status": "success", "message": "Readiness checklist updated."}

@router.post("/emergency_override")
def emergency_override(req: EmergencyOverrideRequest, db: Session = Depends(get_db)):
    """Override emergency flags for fast-track scheduling."""
    case = db.query(Case).filter(Case.id == req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    if req.is_bail_matter is not None:
        case.is_bail_matter = req.is_bail_matter
    if req.is_child_protection is not None:
        case.is_child_protection = req.is_child_protection
    if req.is_medical_emergency is not None:
        case.is_medical_emergency = req.is_medical_emergency
    if req.is_domestic_violence is not None:
        case.is_domestic_violence = req.is_domestic_violence
        
    db.commit()
    return {"status": "success", "message": "Emergency overrides updated."}
