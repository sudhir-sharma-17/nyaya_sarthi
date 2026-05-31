from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.db import Base

class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_number = Column(String, unique=True, index=True)
    title = Column(String)
    court_name = Column(String)
    case_type = Column(String)
    filing_date = Column(DateTime, nullable=True, default=None)
    status = Column(String, default="Pending")
    is_active = Column(Boolean, default=True)
    
    # Scheduling & Readiness Details
    evidence_notes = Column(Text)
    evidence_deadline = Column(DateTime)
    evidence_uploaded = Column(Boolean, default=False)
    documents_verified = Column(Boolean, default=False)
    parties_notified = Column(Boolean, default=False)
    investigation_completed = Column(Boolean, default=False)
    postponed_until = Column(DateTime)
    postponement_reason = Column(String)
    
    # Emergency Overrides
    is_bail_matter = Column(Boolean, default=False)
    is_child_protection = Column(Boolean, default=False)
    is_medical_emergency = Column(Boolean, default=False)
    is_domestic_violence = Column(Boolean, default=False)
    
    # Assigned Session Details
    hearing_time = Column(String)
    court_room = Column(String)
    judge_name = Column(String)
    
    # Parties
    petitioner = Column(String)
    respondent = Column(String)
    bench = Column(String)

    
    # Urgency & Triage
    urgency_score = Column(Float, default=0.0)
    backlog_score = Column(Float, default=0.0)
    priority_score = Column(Float, default=0.0)   # MASTER UNIFIED SCORE (0–100)
    priority_level = Column(String, default="Low") # Critical, High, Medium, Low
    confidence_score = Column(Float, default=0.0)
    reasoning = Column(Text)
    humanitarian_flag = Column(Boolean, default=False)
    constitutional_flag = Column(Boolean, default=False)
    
    # Dates & Age
    case_age_days = Column(Integer, default=0)
    last_hearing_date = Column(DateTime)
    hearing_date = Column(DateTime)
    judgment_date = Column(DateTime)
    inactivity_days = Column(Integer, default=0)
    adjournment_count = Column(Integer, default=0)
    
    # Clustering
    cluster_id = Column(String)
    cluster_label = Column(String)
    
    # Content
    summary = Column(Text)
    legal_issue = Column(Text)
    relief_sought = Column(Text)
    clustering_compatibility = Column(Text)
    scheduling_compatibility = Column(Text)
    raw_content = Column(Text)
    extracted_statutes = Column(Text) 
    citations = Column(Text)
    parties_involved = Column(Text)
    extraction_method = Column(String)
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = relationship("Document", back_populates="case")
    hearings = relationship("Hearing", back_populates="case")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"))
    file_name = Column(String)
    file_type = Column(String) # FIR, Petition, Judgment
    content = Column(Text)
    upload_date = Column(DateTime, default=datetime.utcnow)
    
    case = relationship("Case", back_populates="documents")

class Hearing(Base):
    __tablename__ = "hearings"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"))
    scheduled_date = Column(DateTime)
    judge_name = Column(String)
    court_room = Column(String)
    status = Column(String, default="Scheduled") # Scheduled, Completed, Adjourned
    adjournment_probability = Column(Float, default=0.0)
    
    case = relationship("Case", back_populates="hearings")
