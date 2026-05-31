from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.db import get_db
from app.models.case_model import Case, Hearing
from typing import Optional

router = APIRouter()

@router.get("/backlog")
def get_backlog_stats(db: Session = Depends(get_db)):
    """
    Returns aggregate statistics for the backlog analytics dashboard.
    """
    total = db.query(Case).count()
    humanitarian = db.query(Case).filter(Case.humanitarian_flag == True).count()
    high_priority = db.query(Case).filter(Case.urgency_score > 70).count()
    legal_aid = db.query(Case).filter(Case.is_legal_aid_eligible == True).count()

    # Backlog by case type
    by_type = (
        db.query(Case.case_type, func.count(Case.id).label("count"))
        .group_by(Case.case_type)
        .all()
    )

    # Average urgency
    avg_urgency = db.query(func.avg(Case.urgency_score)).scalar() or 0.0

    return {
        "total_pending": total,
        "humanitarian_alerts": humanitarian,
        "high_priority": high_priority,
        "legal_aid_eligible": legal_aid,
        "average_urgency_score": round(float(avg_urgency), 2),
        "backlog_by_case_type": [{"type": r[0], "count": r[1]} for r in by_type],
    }

@router.get("/adjournment-risk")
def get_adjournment_risk(db: Session = Depends(get_db)):
    """
    Returns hearings with high adjournment risk.
    """
    high_risk = (
        db.query(Hearing)
        .filter(Hearing.adjournment_probability > 0.65)
        .order_by(Hearing.adjournment_probability.desc())
        .limit(20)
        .all()
    )
    return high_risk

@router.get("/pendency-distribution")
def get_pendency_distribution(db: Session = Depends(get_db)):
    """
    Groups cases by pendency ranges for the dashboard chart.
    """
    import datetime
    cases = db.query(Case.filing_date).all()
    now = datetime.datetime.utcnow()

    bands = {"<1 Year": 0, "1-5 Years": 0, "5-10 Years": 0, "10-20 Years": 0, ">20 Years": 0}
    for (fd,) in cases:
        if fd:
            years = (now - fd).days / 365
            if years < 1:       bands["<1 Year"] += 1
            elif years < 5:     bands["1-5 Years"] += 1
            elif years < 10:    bands["5-10 Years"] += 1
            elif years < 20:    bands["10-20 Years"] += 1
            else:               bands[">20 Years"] += 1

    return [{"band": k, "count": v} for k, v in bands.items()]
