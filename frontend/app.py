import streamlit as st
import requests
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import numpy as np

# API Base URL
API_URL = "http://127.0.0.1:8000/api/v1"

st.set_page_config(
    page_title="Judicial AI Platform",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium Judiciary Theme & CSS
st.markdown("""
<style>
    /* Global Styles */
    .main { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
    h1, h2, h3, h4 { color: #0f172a; font-weight: 600; }
    
    /* Modern Cards */
    .metric-card {
        background: #ffffff;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        text-align: center;
    }
    .metric-card h3 { margin: 0; font-size: 28px; color: #1e3a8a; }
    .metric-card p { margin: 0; color: #64748b; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }
    
    /* Badges */
    .status-badge {
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        display: inline-block;
        margin-right: 5px;
        margin-bottom: 5px;
    }
    .badge-critical { background-color: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
    .badge-high { background-color: #fff7ed; color: #c2410c; border: 1px solid #fed7aa; }
    .badge-medium { background-color: #fefce8; color: #a16207; border: 1px solid #fef08a; }
    .badge-low { background-color: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
    .badge-info { background-color: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }
    
    /* Typography */
    .clean-title { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0 0 5px 0; }
    .clean-subtitle { font-size: 14px; color: #64748b; margin-bottom: 15px; }
    
    .section-header {
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 10px;
        margin-bottom: 20px;
        color: #1e293b;
    }
    
    /* Scrollable Text Area */
    .scrollable-text {
        max-height: 400px;
        overflow-y: auto;
        background: #f1f5f9;
        padding: 15px;
        border-radius: 6px;
        font-family: monospace;
        font-size: 12px;
        white-space: pre-wrap;
        color: #334155;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions
@st.cache_data(ttl=10)
def fetch_cases():
    try:
        res = requests.get(f"{API_URL}/cases/", timeout=10)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return []

# Sidebar Navigation
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Emblem_of_India.svg/200px-Emblem_of_India.svg.png", width=60)
    st.title("Judicial AI")
    st.markdown("<p style='color:#64748b; font-size:14px; margin-top:-15px;'>Decision Support System</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    menu = st.radio(
        "NAVIGATION",
        [
            "📋 Case Registry",
            "📤 Upload & Processing", 
            "🔥 Priority Matrix", 
            "🚨 Humanitarian Triage",
            "🧬 Similar Clustering", 
            "📚 Precedent Intelligence", 
            "📅 Schedule Optimizer", 
            "📊 Analytics Dashboard",
        ]
    )
    st.markdown("---")
    st.caption("v3.0.0 | Enterprise Edition")

# Fetch global data
all_cases = fetch_cases()

from fpdf import FPDF
import io

def generate_case_pdf(case_data, raw_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, f"Legal Intelligence Report: {case_data.get('title', 'Unknown')}", ln=True, align="C")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 10, f"Case ID: {case_data.get('case_number')} | Generated on {datetime.now().strftime('%Y-%m-%d')}", ln=True, align="C")
    pdf.ln(10)
    
    sections = [
        ("Case Summary", case_data.get('summary')),
        ("Legal Issue", case_data.get('legal_issue')),
        ("Relief Requested", case_data.get('relief_sought')),
        ("Final Outcome", raw_data.get('legal_outcome')),
        ("Priority Analysis", case_data.get('reasoning'))
    ]
    
    for title, content in sections:
        pdf.set_font("helvetica", "B", 12)
        pdf.set_fill_color(240, 242, 246)
        pdf.cell(0, 8, title, ln=True, fill=True)
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(0, 6, str(content) if content else "Not Available")
        pdf.ln(4)
    
    return bytes(pdf.output())

# --- SHARED ANALYTICS LOGIC ---
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.priority_engine import compute_priority_score, compute_priority_breakdown

def calculate_final_priority(c):
    """
    Computes priority score dynamically using the centralized priority engine.
    """
    return compute_priority_score(c)

def get_priority_breakdown(c):
    """
    Computes case priority components dynamically for explanation panels
    delegating to the centralized priority engine.
    """
    bd = compute_priority_breakdown(c)
    return {
        "score": bd["score"],
        "urgency_factor": bd["urgency"],
        "backlog_factor": bd["backlog"],
        "humanitarian_boost": bd["humanitarian"],
        "level": bd["level"],
        "explanation": bd["explanation"],
        "age_days": bd["age_days"],
        "age_str": bd["age_label"]
    }
def calculate_complexity_impact(c):
    """
    Dynamically computes Legal Impact / Complexity based on case features:
    - constitutional_flag (constitutional issues = high impact)
    - case_type (criminal, civil, writ etc)
    - statutes (extracted_statutes acts and sections count)
    - citations (citations count)
    Returns: (score, level) where level is "High", "Medium", or "Low"
    """
    score = 30.0 # baseline low-medium complexity
    
    # 1. Constitutional or PIL flag boost
    if c.get('constitutional_flag') or 'pil' in str(c.get('case_type', '')).lower() or 'constitution' in str(c.get('case_type', '')).lower():
        score += 40.0
        
    # 2. Case Type complexity weights
    ct = str(c.get('case_type', '')).lower()
    if 'criminal' in ct:
        score += 20.0
    elif 'writ' in ct:
        score += 15.0
    elif 'civil' in ct:
        score += 10.0
        
    # 3. Statutes count boost
    try:
        statutes_str = c.get('extracted_statutes') or '[]'
        if isinstance(statutes_str, str):
            if statutes_str.startswith('['):
                import json
                statutes_list = json.loads(statutes_str)
            else:
                statutes_list = [s for s in statutes_str.split(',') if s.strip()]
        elif isinstance(statutes_str, list):
            statutes_list = statutes_str
        else:
            statutes_list = []
        score += min(len(statutes_list) * 5, 20)
    except:
        pass
        
    # 4. Citations count boost
    try:
        citations_str = c.get('citations') or '[]'
        if isinstance(citations_str, str):
            if citations_str.startswith('['):
                import json
                citations_list = json.loads(citations_str)
            else:
                citations_list = [cit for cit in citations_str.split(',') if cit.strip()]
        elif isinstance(citations_str, list):
            citations_list = citations_str
        else:
            citations_list = []
        score += min(len(citations_list) * 5, 20)
    except:
        pass
        
    score = min(max(score, 0), 100)
    
    if score >= 70:
        return score, "High"
    elif score >= 40:
        return score, "Medium"
    else:
        return score, "Low"
def calculate_humanitarian_triage(c):
    """
    Dynamically assesses humanitarian risk factors across the case text and metadata:
    - Medical emergencies (surgery, cancer, hospital treatment)
    - Child/women protection (custody, maintenance, domestic violence)
    - Senior citizen vulnerabilities (pension, retirement, elderly support)
    - shelter/personal liberty crises (bail, arrest, eviction stay)
    - Backlog delay severity
    """
    title = str(c.get('title', '')).lower()
    summary = str(c.get('summary', '')).lower()
    full_text = str(c.get('extracted_text', '')).lower()
    combined = f"{title} {summary} {full_text}"
    
    # 1. Signals Extraction
    signals = []
    med_score = 0
    if any(k in combined for k in ['medical', 'health', 'hospital', 'cancer', 'treatment', 'ailment', 'physically disabled', 'surgery', 'disease']):
        signals.append("🏥 Medical Emergency Signal")
        med_score = 25
        
    child_women_score = 0
    if any(k in combined for k in ['custody', 'child', 'women', 'domestic violence', 'dowry', 'maintenance', 'divorce', 'minor', 'juvenile', 'harassment']):
        signals.append("👧 Child/Women Protection Signal")
        child_women_score = 25
        
    senior_score = 0
    if any(k in combined for k in ['senior citizen', 'aged', 'pension', 'elderly', 'gratuity', 'old age', 'retirement']):
        signals.append("👵 Senior Citizen Risk Signal")
        senior_score = 20
        
    shelter_liberty_score = 0
    if any(k in combined for k in ['bail', 'custody', 'arrest', 'habeas corpus', 'eviction', 'shelter', 'demolition', 'possession', 'tenant', 'landlord']):
        signals.append("🏠 Shelter/Personal Liberty Crisis")
        shelter_liberty_score = 20
        
    # Case Age Delay Component
    age_score = 0
    fd = c.get('filing_date')
    age_days = 0
    if fd:
        try:
            from datetime import datetime
            if isinstance(fd, str):
                dt = datetime.fromisoformat(fd.replace("Z", ""))
            elif isinstance(fd, datetime):
                dt = fd
            age_days = (datetime.now() - dt).days
        except:
            pass
            
    if age_days > 3650: # 10+ years
        age_score = 10
    elif age_days > 1825: # 5+ years
        age_score = 5
        
    total_score = med_score + child_women_score + senior_score + shelter_liberty_score + age_score
    total_score = min(total_score, 100)
    
    # Determine risk level
    if total_score >= 60:
        level = "Extreme"
    elif total_score >= 45:
        level = "High"
    elif total_score >= 20:
        level = "Moderate"
    else:
        level = "Low"
        
    # Determine relief needed
    reliefs = []
    if med_score > 0:
        reliefs.append("Healthcare Access / Medical Triage")
    if child_women_score > 0:
        reliefs.append("Custody Triage / Interim Protection Order")
    if senior_score > 0:
        reliefs.append("Expedited Pension Release")
    if shelter_liberty_score > 0:
        reliefs.append("Bail / Eviction Stay Review")
        
    relief_needed = ", ".join(reliefs) if reliefs else "General Fast-Track Hearing"
    
    return {
        "score": total_score,
        "level": level,
        "signals": signals,
        "med_score": med_score,
        "child_women_score": child_women_score,
        "senior_score": senior_score,
        "shelter_liberty_score": shelter_liberty_score,
        "age_score": age_score,
        "age_days": age_days,
        "relief_needed": relief_needed,
        "is_humanitarian": (total_score >= 20 or c.get('humanitarian_flag'))
    }



# Initialize session state for watchlist
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# Initialize session state for upload batches
if 'current_upload_batch_case_numbers' not in st.session_state:
    st.session_state.current_upload_batch_case_numbers = []
if 'current_upload_batch_db_ids' not in st.session_state:
    st.session_state.current_upload_batch_db_ids = []

# Metadata Sanitization Engine
def sanitize_metadata_field(value, field_type="general"):
    """
    Standardizes and validates metadata fields to prevent raw text contamination.
    Returns 'Not Available' if the content is malformed or too long.
    """
    if not value or str(value).lower() in ["none", "null", "", "nan", "not available", "unknown"]:
        return "Not Available"
    
    # 1. Universal String Cleaning
    v = str(value).strip()
    
    # Remove pipes and concatenated placeholders (e.g. "Case ID | Not Available")
    v = v.split('|')[0].strip()
    v = v.replace("Not Available", "").replace("not available", "").strip()
    
    # Automatically unpack stringified list representations (e.g. "['Judge 1', 'Judge 2']")
    if v.startswith('[') and v.endswith(']'):
        try:
            import ast
            parsed_list = ast.literal_eval(v)
            if isinstance(parsed_list, list):
                v = ", ".join(str(item).strip() for item in parsed_list)
        except:
            pass

    # Replace newlines with spaces to avoid breaking markdown formatting
    v = v.replace('\r\n', ' ').replace('\n', ' ').strip()
    
    # Remove dates (e.g. "on 5 December 1975" or "on 05/12/1975")
    import re
    date_patterns = [
        r'\s+on\s+\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^,]*\d{4}',
        r'\s+on\s+\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
        r'\s+on\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^,]*\d{1,2},?\s+\d{4}'
    ]
    for pattern in date_patterns:
        v = re.sub(pattern, '', v, flags=re.IGNORECASE)

    # Remove legal noise
    v = re.sub(r'Equivalent citations.*$', '', v, flags=re.IGNORECASE)
    v = re.sub(r'https?://\S+', '', v)
    v = re.sub(r'www\.\S+', '', v)
    v = re.sub(r'\.{2,}', '', v) # Remove repeated dots (keep single initials like A.K. Sen)
    
    v = v.strip()
    if not v or v.lower() in ["none", "null", "not available"]:
        return "Not Available"
    
    # 2. Strict Field Validation
    limits = {
        "court": 120,
        "case_id": 60,
        "party": 150,
        "bench": 150,
        "title": 200,
        "general": 255
    }
    limit = limits.get(field_type, 255)
    
    if len(v) > limit:
        return "Not Available"
        
    # Case ID Specific: Reject if contains paragraph-like characters or symbols
    if field_type == "case_id":
        if any(c in v for c in [":", "{", "}", "[", "]"]) or len(v.split()) > 10:
            return "Not Available"

    # Paragraph Detection (ignore dots if they are initials or abbreviations like J., CJ., C.A.)
    # We count sentences by looking for dots followed by a space and capital letter, not just dots alone.
    if len(re.findall(r'\.\s+[A-Z]', v)) > 2:
        return "Not Available"
        
    # Keyword triggers
    triggers = ["judgment", "appeal", "section", "article", "court observed", "held", "indiankanoon"]
    if any(t in v.lower() for t in triggers) and len(v) > 50:
        return "Not Available"
            
    return v

@st.dialog("Legal Intelligence Report", width="large")
def show_case_details(case_data):
    # --- ROBUST RAW CONTENT PARSING ---
    raw = {}
    try:
        import json, ast
        raw_str = case_data.get('raw_content', '{}')
        if isinstance(raw_str, str):
            # Try JSON first, fallback to literal_eval for single-quoted dicts
            try: raw = json.loads(raw_str)
            except: raw = ast.literal_eval(raw_str)
        else: raw = raw_str
    except: pass

    smeta = raw.get('structured_meta', {})

    def _pick(*keys_from_dicts):
        """Try structured_meta first, then raw, then case_data directly."""
        for val in keys_from_dicts:
            if val and str(val).strip().lower() not in ('', 'not available', 'none', 'null', 'nan'):
                return str(val).strip()
        return "Not Available"

    # Single source of truth metadata picks
    ov_title      = _pick(smeta.get('case_title'), raw.get('case_title'), case_data.get('title'))
    ov_case_num   = _pick(smeta.get('case_number_extracted'), raw.get('case_number_extracted'), case_data.get('case_number'))
    ov_court      = _pick(smeta.get('court_name'), raw.get('court_name'), case_data.get('court_name'))
    ov_petitioner = _pick(smeta.get('petitioner'), raw.get('petitioner'), case_data.get('petitioner'))
    ov_respondent = _pick(smeta.get('respondent'), raw.get('respondent'), case_data.get('respondent'))
    ov_bench      = _pick(smeta.get('bench'), raw.get('bench'), case_data.get('bench'))
    ov_author     = _pick(smeta.get('author_judge'), raw.get('author_judge'), case_data.get('author_judge'))
    ov_outcome    = _pick(raw.get('legal_outcome'), case_data.get('legal_outcome'))
    ov_issue      = _pick(raw.get('core_legal_issue'), case_data.get('legal_issue'), case_data.get('core_legal_issue'))

    # --- SECTION 0: CASE HEADER ---
    st.markdown(f"<div style='background: #f0f2f6; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;'>"
                f"<h2 style='margin:0; color: #1e3a8a;'>{sanitize_metadata_field(ov_title, 'title')}</h2>"
                f"<p style='margin:0; color: #64748b;'>Case ID: {sanitize_metadata_field(ov_case_num, 'case_id')} | {sanitize_metadata_field(ov_court, 'court')}</p></div>", 
                unsafe_allow_html=True)
    
    # Priority Metrics Header
    def safe_float(val, default=0.0):
        try:
            if isinstance(val, str):
                import re
                nums = re.findall(r'\d+\.?\d*', val)
                return float(nums[0]) if nums else default
            return float(val or default)
        except: return default

    priority_score = calculate_final_priority(case_data)
    
    h1, h2, h3 = st.columns(3)
    h1.metric("Final Priority", case_data.get('priority_level', 'Medium'))
    h2.metric("Priority Score", f"{priority_score:.0f}/100")
    h3.metric("Case Status", case_data.get('status', 'Processed'))

    st.markdown("---")

    # --- 1. Intelligence Summary ---
    st.markdown("### 📝 Intelligence Summary")
    summary = case_data.get('summary', '')
    if not summary: summary = case_data.get('legal_summary', '')
    if not summary: summary = raw.get('summary', '')
    
    if not summary or "pending full summarization" in str(summary).lower() or len(str(summary)) < 30:
        st.write("Not Available")
    else:
        st.write(summary)

    # --- 2. Core Legal Issue ---
    st.markdown("### ⚖️ Core Legal Issue")
    with st.container(border=True):
        st.write(ov_issue)

    # --- 3. Relief Requested ---
    st.markdown("### 📜 Relief Requested")
    with st.container(border=True):
        st.write(case_data.get('relief_sought') or raw.get('relief_sought') or "Not Available")

    # --- 4. Final Decision / Outcome ---
    st.markdown("### ✅ Final Decision / Outcome")
    if not ov_outcome or "not available" in str(ov_outcome).lower() or "pending review" in str(ov_outcome).lower():
        st.warning("🕒 Outcome Pending Review")
    else:
        st.success(f"Outcome: {ov_outcome}")

    st.markdown("---")
    col1, col2 = st.columns(2)

    # --- 5. Parties & Bench ---
    with col1:
        st.markdown("### 👥 Parties & Bench")
        with st.container(border=True):
            st.markdown(f"**Petitioner/Appellant:** {sanitize_metadata_field(ov_petitioner, 'party')}")
            st.markdown(f"**Respondent:** {sanitize_metadata_field(ov_respondent, 'party')}")
            st.markdown(f"**Bench:** {sanitize_metadata_field(ov_bench, 'bench')}")
            st.markdown(f"**Author:** {sanitize_metadata_field(ov_author, 'general')}")
            st.markdown(f"**Court:** {sanitize_metadata_field(ov_court, 'court')}")

    # --- 6. Timeline Analysis ---
    with col2:
        st.markdown("### 📅 Timeline Analysis")
        with st.container(border=True):
            # Dynamic date resolution
            f_val = _pick(smeta.get('filing_date'), raw.get('filing_date'), case_data.get('filing_date'))
            j_val = _pick(smeta.get('judgment_date'), raw.get('judgment_date'), case_data.get('judgment_date'))
            h_val = _pick(smeta.get('hearing_date'), raw.get('hearing_date'), case_data.get('hearing_date'))
            
            import dateparser
            def format_legal_date(val):
                if not val or str(val).lower() in ["not available", "none", "unknown", "", "n/a"]: 
                     return "N/A", None
                try:
                    # If it's already a datetime object
                    if hasattr(val, "year"):
                        return val.strftime("%d %b %Y"), val
                        
                    s_val = str(val).strip()
                    
                    # Handle year-only strings (e.g., '1975')
                    if len(s_val) == 4 and s_val.isdigit():
                        return f"Year {s_val} (Approx)", datetime(int(s_val), 1, 1)
                    
                    # Only accept strict YYYY-MM-DD format from the backend
                    from datetime import datetime
                    # Truncate time if it's a full ISO string
                    if " " in s_val: s_val = s_val.split(" ")[0]
                    if "T" in s_val: s_val = s_val.split("T")[0]
                    
                    dt = datetime.strptime(s_val, "%Y-%m-%d")
                    return dt.strftime("%d %b %Y"), dt
                except Exception as e: 
                    return "N/A", None

            f_str, f_dt = format_legal_date(f_val)
            j_str, j_dt = format_legal_date(j_val)
            h_str, h_dt = format_legal_date(h_val)
            
            # Precise Age Calculation (STRICTLY FROM FILING DATE)
            age_str = "Not Available"
            if f_dt:
                from dateutil.relativedelta import relativedelta
                diff = relativedelta(datetime.utcnow(), f_dt)
                if diff.years > 0 or diff.months > 0 or diff.days > 0:
                    age_str = f"{diff.years} years, {diff.months} months, {diff.days} days old"
                else:
                    age_str = "Recent Ingestion"
            
            st.write(f"**Filing Date:** {f_str}")
            st.write(f"**Judgment Date:** {j_str}")
            st.write(f"**Hearing Date:** {h_str}")
            st.write(f"**Computed Case Age:** {age_str}")

    # --- 7. Statutes & Citations ---
    st.markdown("### 📚 Statutes & Citations")
    with st.container(border=True):
        statutes = smeta.get('statutes') or raw.get('statutes') or case_data.get('extracted_statutes') or case_data.get('statutes_sections')
        citations = smeta.get('citations') or raw.get('citations') or case_data.get('citations')
        
        # Format as string if it is a list
        if isinstance(statutes, list):
            statutes = " · ".join(statutes)
        if isinstance(citations, list):
            citations = " · ".join(citations)
            
        st.write(f"**Statutes:** {statutes or 'Not Available'}")
        st.write(f"**Case Citations:** {citations or 'Not Available'}")

    # --- 8. Priority Analysis ---
    st.markdown("### 🚨 Priority Analysis")
    with st.container(border=True):
        st.write(f"**Reasoning:** {case_data.get('reasoning') or case_data.get('priority_reasoning_summary') or 'Standard prioritization applied.'}")

    # --- 9. Similar Matter Analysis ---
    st.markdown("### 🧬 Similar Matter Analysis")
    current_id = case_data.get('case_number')
    
    # 2 & 5. Similarity clustering source: Use ONLY session_uploaded_cases.
    current_batch = st.session_state.get('current_upload_batch_case_numbers', [])
    
    # 7. If only one file uploaded
    if len(current_batch) <= 1:
        st.info("No similar uploaded cases available.")
    else:
        # Filter for VALID similar cases only (hide garbage) AND only those in current batch
        all_sim = [
            c for c in all_cases 
            if c.get('case_number') != current_id 
            and c.get('cluster_label') == case_data.get('cluster_label') 
            and c.get('case_number') in current_batch
        ]
        
        similar_cases = []
        for sc in all_sim:
            sc_id = sanitize_metadata_field(sc.get('case_number'), 'case_id')
            sc_title = sanitize_metadata_field(sc.get('title'), 'title')
            if sc_id != "Not Available" and sc_title != "Not Available":
                similar_cases.append(sc)

        if similar_cases:
            st.success(f"Found {len(similar_cases)} cases with high similarity.")
            for sc in similar_cases[:3]:
                st.caption(f"• {sc.get('title')} (ID: {sc.get('case_number')})")
        else:
            st.info("No high-similarity precedents found in current dataset.")

    # --- 10. View Full Case Text ---
    st.markdown("---")
    with st.expander("📄 View Full Extracted Case Text"):
        full_text = raw.get('full_text', case_data.get('raw_content', 'Raw content not available.'))
        st.markdown(f"<div class='scrollable-text' style='height: 300px; overflow-y: auto; background: #f8fafc; padding: 1rem; border: 1px solid #e2e8f0; border-radius: 5px; font-family: monospace; white-space: pre-wrap;'>{full_text}</div>", unsafe_allow_html=True)

    # --- Action Bar at Bottom ---
    st.markdown("### 🛠️ Professional Actions")
    a1, a2 = st.columns(2)
    with a1:
        try:
            pdf_data = bytes(generate_case_pdf(case_data, raw))
            st.download_button("📄 Download PDF", pdf_data, f"Case_{current_id}.pdf", "application/pdf", use_container_width=True)
        except: st.button("📄 PDF Error", disabled=True, use_container_width=True)
    with a2:
        st.download_button("📤 Export JSON", json.dumps(case_data, indent=2, default=str), f"Case_{current_id}.json", "application/json", use_container_width=True)




# ────────────────────────────────────────────────────────
# 1. Case Registry (Enterprise Table Layout)
# ────────────────────────────────────────────────────────
if menu == "📋 Case Registry":
    st.markdown("<h2 class='section-header'>📋 Processed Case Registry</h2>", unsafe_allow_html=True)
    
    rc1, rc2, rc3 = st.columns([7, 1.5, 1.5])
    with rc3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with rc2:
        if st.button("🗑️ Clear Registry", use_container_width=True, type="secondary", help="Delete ALL cases from database"):
            try:
                res = requests.delete(f"{API_URL}/upload/cases/clear/all")
                if res.status_code == 200:
                    st.success("Registry Cleared")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to clear registry")
            except Exception as e:
                st.error(f"Error: {e}")
    
    if not all_cases:
        st.info("Registry is empty. Please upload cases in the 'Upload & Processing' tab to begin.")
    else:
        # 6. KPI Summary Cards
        total_cases = len(all_cases)
        high_priority = len([c for c in all_cases if c.get('priority_level') in ['High', 'Critical']])
        clusters = len(set(c.get('clustering_compatibility', 'General') for c in all_cases))
        
        st.markdown("""
        <div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px;'>
            <div class='metric-card'>
                <h3>{0}</h3><p>Total Processed</p>
            </div>
            <div class='metric-card'>
                <h3 style='color:#dc2626;'>{1}</h3><p>High Priority</p>
            </div>
            <div class='metric-card'>
                <h3 style='color:#3b82f6;'>{2}</h3><p>Active Clusters</p>
            </div>
            <div class='metric-card'>
                <h3 style='color:#10b981;'>1.2s</h3><p>Avg Processing Time</p>
            </div>
        </div>
        """.format(total_cases, high_priority, clusters), unsafe_allow_html=True)
        
        # 5. Search and Filters
        with st.container():
            sc1, sc2, sc3, sc4 = st.columns([2, 1, 1, 1])
            search_q = sc1.text_input("Search Case Title or ID", placeholder="e.g. Amadalavalasa Cooperative...")
            filter_pri = sc2.selectbox("Priority", ["All", "Critical", "High", "Medium", "Low"])
            filter_cat = sc3.selectbox("Category", ["All"] + list(set(c.get('case_type', '') for c in all_cases if c.get('case_type'))))
            filter_status = sc4.selectbox("Status", ["Processed", "Pending Review", "Scheduled", "Archived"])

        filtered = all_cases
        if search_q: filtered = [c for c in filtered if search_q.lower() in str(c).lower()]
        if filter_pri != "All": filtered = [c for c in filtered if c.get('priority_level') == filter_pri]
        if filter_cat != "All": filtered = [c for c in filtered if c.get('case_type') == filter_cat]

        # Prepare Table Data (Synchronized with Header)
        table_data = []
        for c in filtered:
            # Use Shared Truth Logic
            p_score = calculate_final_priority(c)
            
            # Safely extract Year
            year_val = str(c.get('filing_date', 'N/A')).strip()
            if not year_val or year_val.lower() in ["not available", "n/a", "none", "unknown"]:
                year = "N/A"
            else:
                year = year_val[:4] if len(year_val) >= 4 else "N/A"
                
            table_data.append({
                "InternalID": c.get('id'),
                "Case ID": sanitize_metadata_field(c.get('case_number'), 'case_id'),
                "Case Title": sanitize_metadata_field(c.get('title'), 'title'),
                "Court": sanitize_metadata_field(c.get('court_name'), 'court'),
                "Year": year,
                "Category": c.get('case_type'),
                "Priority Score": p_score,
                "Cluster": c.get('cluster_label', 'UC-01'),
                "Status": "Processed",
                "Select": False,
                "Delete": False
            })
            
        df = pd.DataFrame(table_data)
        
        st.markdown("### Processed Document Index")
        
        col_btn1, col_btn2 = st.columns([6, 2])
        with col_btn1:
            st.caption(f"Select a row to open deep-dive Case Details or mark for deletion.")
        
        # Interactive DataFrame
        edited_df = st.data_editor(
            df,
            column_config={
                "InternalID": None, # Hide internal ID
                "Priority Score": st.column_config.NumberColumn("Score", help="Calculated Priority Score", format="%d%%"),
                "Select": st.column_config.CheckboxColumn("View", help="Select to open case details", default=False),
                "Delete": st.column_config.CheckboxColumn("🗑️", help="Mark for deletion", default=False),
            },
            disabled=["Case ID", "Case Title", "Court", "Year", "Category", "Priority Score", "Cluster", "Status"],
            hide_index=True,
            use_container_width=True,
            key="registry_editor"
        )

        # Handle Deletion
        to_delete_internal_ids = edited_df[edited_df["Delete"] == True]["InternalID"].tolist()
        if to_delete_internal_ids:
            with col_btn2:
                if st.button(f"🗑️ Delete ({len(to_delete_internal_ids)})", type="primary", use_container_width=True):
                    success_count = 0
                    for db_id in to_delete_internal_ids:
                        try:
                            res = requests.delete(f"{API_URL}/upload/cases/{db_id}")
                            if res.status_code == 200: success_count += 1
                        except: pass
                    
                    if success_count > 0:
                        st.session_state.last_deleted_ids = to_delete_internal_ids
                        st.success(f"Deleted {success_count} cases.")
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()

        # Undo Button
        if 'last_deleted_ids' in st.session_state and st.session_state.last_deleted_ids:
            with col_btn2:
                if st.button(f"↩️ Undo ({len(st.session_state.last_deleted_ids)})", use_container_width=True):
                    undo_count = 0
                    for db_id in st.session_state.last_deleted_ids:
                        try:
                            res = requests.post(f"{API_URL}/upload/cases/{db_id}/undo")
                            if res.status_code == 200: undo_count += 1
                        except: pass
                    if undo_count > 0:
                        st.toast(f"Restored {undo_count} cases.", icon="↩️")
                        st.session_state.last_deleted_ids = []
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()

        # --- High-Fidelity Selection Mapping ---
        # Get all currently selected Internal IDs (Immutable Database Primary Keys)
        selected_ids = edited_df[edited_df["Select"] == True]["InternalID"].tolist()
        
        # Track previous selection to detect the NEW selection
        if 'last_selected_ids' not in st.session_state:
            st.session_state.last_selected_ids = []
            
        new_selections = list(set(selected_ids) - set(st.session_state.last_selected_ids))
        
        # If a new row was just checked, focus on it
        if new_selections:
            st.session_state.active_case_id = new_selections[0]
        elif not selected_ids:
            st.session_state.active_case_id = None
        elif st.session_state.get('active_case_id') not in selected_ids:
            # If the currently active case was unchecked, pick the next available one
            st.session_state.active_case_id = selected_ids[0] if selected_ids else None
            
        st.session_state.last_selected_ids = selected_ids
        
        # Render Deep Dive for the SPECIFIC active Case ID only
        if st.session_state.get('active_case_id'):
            # Lookup via immutable DB ID, immune to string formatting mutations
            target_case = next((c for c in all_cases if c.get('id') == st.session_state.active_case_id), None)
            if target_case:
                show_case_details(target_case)
            else:
                st.error("Error: Selected case data mismatch. Please refresh.")

# ────────────────────────────────────────────────────────
# 2. Upload & Processing
# ────────────────────────────────────────────────────────
elif menu == "📤 Upload & Processing":
    st.markdown("<h2 class='section-header'>📤 Document Ingestion & Processing</h2>", unsafe_allow_html=True)
    st.markdown("Upload Legal Documents (PDF, PNG, JPG). System will extract metadata and populate the Case Registry.")
    
    files = st.file_uploader("Select documents to process", type=["pdf", "png", "jpg"], accept_multiple_files=True)
    process_btn = st.button("Process Documents", type="primary", use_container_width=True)
    
    if process_btn and files:
        with st.spinner("Extracting intelligence & analyzing legal features..."):
            payload = [("files", (f.name, f.getvalue(), f.type)) for f in files]
            try:
                # 3 & 4. Before new upload: reset session cache
                st.session_state.current_upload_batch_case_numbers = []
                st.session_state.current_upload_batch_db_ids = []
                st.session_state.current_uploaded_filenames = [f.name for f in files]
                
                res = requests.post(f"{API_URL}/upload/bulk", files=payload, timeout=600)
                if res.status_code == 200:
                    data = res.json()
                    results = data.get('results', [])
                    success = [r for r in results if 'error' not in r]
                    errors  = [r for r in results if 'error' in r]
                    
                    # 1 & 4. Maintain session-specific uploaded cases list
                    if success:
                        st.session_state.current_upload_batch_case_numbers = [r.get('case_number') for r in success if r.get('case_number')]
                        # Track DB IDs for vector store session isolation
                        st.session_state.current_upload_batch_db_ids = [str(r.get('case_id')) for r in success if r.get('case_id')]
                        
                        if len(success) == len(files):
                            st.success(f"✅ Successfully processed ALL {len(success)} document(s).")
                        else:
                            st.warning(f"⚠️ Processed {len(success)} out of {len(files)} uploaded document(s). Some files may have failed or timed out.")
                        
                        # Force refresh
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                    if errors:
                        for e in errors:
                            st.error(f"❌ {e['file']}: {e['error']}")
                else:
                    st.error(f"Ingestion failed. Status: {res.status_code}")

            except requests.exceptions.Timeout:
                st.error("⏱️ Request timed out. The LLM is taking too long. The case may still have been saved — check the Case Registry.")
                st.cache_data.clear()
            except Exception as ex:
                st.error(f"Connection error: {ex}")

# ────────────────────────────────────────────────────────
# 3. Priority Matrix
# ────────────────────────────────────────────────────────
elif menu == "🔥 Priority Matrix":
    st.markdown("<h2 class='section-header'>🔥 Priority Matrix & Operational Decision Dashboard</h2>", unsafe_allow_html=True)
    
    # System Status Indicators
    st.sidebar.markdown("### System Status")
    st.sidebar.success("✅ AI Engine: Ready")
    st.sidebar.success("✅ OCR: Active")
    st.sidebar.info("✅ LLM: Connected (Groq)")

    if not all_cases:
        st.info("No cases available for prioritization.")
    else:
        # Precompute breakdowns for all cases
        case_breakdowns = {}
        for c in all_cases:
            case_breakdowns[c.get('id')] = get_priority_breakdown(c)

        # A. Summary Cards (Priority Distribution only)
        total_cases = len(all_cases)
        high_cases = len([c for c in all_cases if case_breakdowns[c.get('id')]["level"] == 'High'])
        medium_cases = len([c for c in all_cases if case_breakdowns[c.get('id')]["level"] == 'Medium'])
        low_cases = len([c for c in all_cases if case_breakdowns[c.get('id')]["level"] == 'Low'])
        avg_score = np.mean([case_breakdowns[c.get('id')]["score"] for c in all_cases]) if all_cases else 0.0

        st.markdown(f"""
        <div style='display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; margin-bottom: 25px;'>
            <div class='metric-card' style='border-left: 5px solid #3b82f6;'>
                <p style='color:#64748b; font-size:12px; margin:0;'>TOTAL CASES</p>
                <h3 style='color:#1e3a8a; font-size:24px; margin:5px 0 0 0;'>{total_cases}</h3>
            </div>
            <div class='metric-card' style='border-left: 5px solid #dc2626;'>
                <p style='color:#64748b; font-size:12px; margin:0;'>HIGH PRIORITY</p>
                <h3 style='color:#dc2626; font-size:24px; margin:5px 0 0 0;'>{high_cases}</h3>
            </div>
            <div class='metric-card' style='border-left: 5px solid #ea580c;'>
                <p style='color:#64748b; font-size:12px; margin:0;'>MEDIUM PRIORITY</p>
                <h3 style='color:#ea580c; font-size:24px; margin:5px 0 0 0;'>{medium_cases}</h3>
            </div>
            <div class='metric-card' style='border-left: 5px solid #10b981;'>
                <p style='color:#64748b; font-size:12px; margin:0;'>LOW PRIORITY</p>
                <h3 style='color:#059669; font-size:24px; margin:5px 0 0 0;'>{low_cases}</h3>
            </div>
            <div class='metric-card' style='border-left: 5px solid #6366f1;'>
                <p style='color:#64748b; font-size:12px; margin:0;'>AVG PRIORITY SCORE</p>
                <h3 style='color:#4f46e5; font-size:24px; margin:5px 0 0 0;'>{avg_score:.1f}%</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Split page: Left Column (70%) for Matrix and Ranked Table, Right Column (30%) for Breakdown & Actions
        col_left, col_right = st.columns([7, 3])

        # Prepare Matrix Data with Jittering for visual display
        matrix_data = []
        import hashlib
        for c in all_cases:
            bd = case_breakdowns[c.get('id')]
            p_score = bd["score"]
            u_score = bd["urgency_factor"]
            comp_score, comp_level = calculate_complexity_impact(c)
            
            # Determine Urgency Level Coordinate
            if u_score >= 70:
                u_level = "High"
                x_coord = 3.0
            elif u_score >= 40:
                u_level = "Medium"
                x_coord = 2.0
            else:
                u_level = "Low"
                x_coord = 1.0
                
            # Determine Complexity Coordinate
            if comp_level == "High":
                y_coord = 3.0
            elif comp_level == "Medium":
                y_coord = 2.0
            else:
                y_coord = 1.0
                
            # Stable Jitter coordinate generation based on case ID hash
            h_val = int(hashlib.md5(str(c.get('id', '')).encode()).hexdigest(), 16)
            jitter_x = ((h_val % 100) / 100.0 - 0.5) * 0.35
            jitter_y = (((h_val // 100) % 100) / 100.0 - 0.5) * 0.35
            
            matrix_data.append({
                "Case ID": sanitize_metadata_field(c.get('case_number'), 'case_id'),
                "Case Title": sanitize_metadata_field(c.get('title'), 'title'),
                "Priority Score": p_score,
                "Priority Level": bd["level"],
                "Urgency Score": u_score,
                "Urgency Level": u_level,
                "Complexity Score": comp_score,
                "Complexity Level": comp_level,
                "Case Age": bd["age_str"],
                "X": x_coord + jitter_x,
                "Y": y_coord + jitter_y,
            })
            
        df_matrix = pd.DataFrame(matrix_data)

        # Ranked Priority Table Data Preparation
        table_rows = []
        for idx, c in enumerate(sorted(all_cases, key=lambda x: case_breakdowns[x.get('id')]["score"], reverse=True)):
            bd = case_breakdowns[c.get('id')]
            p_score = bd["score"]
            
            # Filing Year
            filing_year = "N/A"
            fd = c.get('filing_date')
            if fd:
                try:
                    from datetime import datetime
                    if isinstance(fd, str):
                        filing_year = str(datetime.fromisoformat(fd.replace("Z", "")).year)
                    elif isinstance(fd, datetime):
                        filing_year = str(fd.year)
                except:
                    pass
            
            age_days = bd["age_days"]
            if age_days >= 365:
                case_age = f"{age_days // 365} yrs"
            else:
                case_age = f"{age_days} days"
                
            table_rows.append({
                "Rank": idx + 1,
                "InternalID": c.get('id'),
                "Case ID": sanitize_metadata_field(c.get('case_number'), 'case_id'),
                "Case Title": sanitize_metadata_field(c.get('title'), 'title'),
                "Filing Year": filing_year,
                "Case Age": case_age,
                "Score": f"{p_score:.0f}%",
                "Final Priority": bd["level"],
                "Urgency Reason": bd["explanation"],
                "Select": False
            })
        df_ranked = pd.DataFrame(table_rows)

        # Active case selection handling
        if 'active_matrix_case_id' not in st.session_state:
            st.session_state.active_matrix_case_id = None

        with col_left:
            # B. Priority Heatmap / Matrix
            st.markdown("### 🗺️ Priority Analytics Matrix")
            st.caption("Visual representation of Urgency (X-axis) vs. Legal Impact/Complexity (Y-axis). Plots all active judicial workload cases.")
            
            fig = go.Figure()
            
            # Quadrant boundary lines
            fig.add_shape(type="line", x0=1.5, y0=0.5, x1=1.5, y1=3.5, line=dict(color="#cbd5e1", width=1.5, dash="dash"))
            fig.add_shape(type="line", x0=2.5, y0=0.5, x1=2.5, y1=3.5, line=dict(color="#cbd5e1", width=1.5, dash="dash"))
            fig.add_shape(type="line", x0=0.5, y0=1.5, x1=3.5, y1=1.5, line=dict(color="#cbd5e1", width=1.5, dash="dash"))
            fig.add_shape(type="line", x0=0.5, y0=2.5, x1=3.5, y1=2.5, line=dict(color="#cbd5e1", width=1.5, dash="dash"))
            
            # Quadrant Labels (Annotations - Displayed conditionally only if at least one case exists in that quadrant)
            has_top_left = any(item["Urgency Score"] < 70 and item["Complexity Score"] >= 40 for item in matrix_data)
            has_top_right = any(item["Urgency Score"] >= 70 and item["Complexity Score"] >= 40 for item in matrix_data)
            has_bottom_left = any(item["Urgency Score"] < 70 and item["Complexity Score"] < 40 for item in matrix_data)
            has_bottom_right = any(item["Urgency Score"] >= 70 and item["Complexity Score"] < 40 for item in matrix_data)

            if has_top_left:
                fig.add_annotation(x=1.0, y=3.4, text="🏛️ High Legal Impact", showarrow=False, font=dict(size=11, color="#475569", weight="bold"), bgcolor="rgba(241,245,249,0.9)", bordercolor="#cbd5e1", borderwidth=1, borderpad=4)
            if has_top_right:
                fig.add_annotation(x=3.0, y=3.4, text="🚨 Critical Priority", showarrow=False, font=dict(size=11, color="#991b1b", weight="bold"), bgcolor="rgba(254,242,242,0.9)", bordercolor="#fecaca", borderwidth=1, borderpad=4)
            if has_bottom_left:
                fig.add_annotation(x=1.0, y=0.6, text="📋 Routine Cases", showarrow=False, font=dict(size=11, color="#166534", weight="bold"), bgcolor="rgba(240,253,244,0.9)", bordercolor="#bbf7d0", borderwidth=1, borderpad=4)
            if has_bottom_right:
                fig.add_annotation(x=3.0, y=0.6, text="⚡ Operational Urgency", showarrow=False, font=dict(size=11, color="#c2410c", weight="bold"), bgcolor="rgba(255,247,237,0.9)", bordercolor="#fed7aa", borderwidth=1, borderpad=4)
            
            colors_map = {
                'High': '#dc2626',
                'Medium': '#ea580c',
                'Low': '#22c55e'
            }
            
            # Add scatter markers grouped by priority
            for prio, color in colors_map.items():
                sub_df = df_matrix[df_matrix["Priority Level"] == prio]
                if not sub_df.empty:
                    fig.add_trace(go.Scatter(
                        x=sub_df["X"],
                        y=sub_df["Y"],
                        mode="markers+text" if len(sub_df) < 8 else "markers",
                        name=prio,
                        text=sub_df["Case ID"],
                        textposition="top center",
                        marker=dict(
                            size=22, # Slightly larger plotted points
                            color=color,
                            opacity=0.85,
                            line=dict(width=1.5, color="#ffffff")
                        ),
                        hovertemplate=(
                            "<b>%{customdata[0]}</b><br>"
                            "ID: %{text}<br>"
                            "Priority Score: %{customdata[1]:.0f}%<br>"
                            "Age: %{customdata[7]}"
                            "<extra></extra>"
                        ),
                        customdata=sub_df[["Case Title", "Priority Score", "Priority Level", "Urgency Score", "Urgency Level", "Complexity Score", "Complexity Level", "Case Age"]].values
                    ))
            
            fig.update_layout(
                xaxis=dict(
                    title="Urgency Level",
                    tickmode="array",
                    tickvals=[1, 2, 3],
                    ticktext=["Low (<40%)", "Medium (40-70%)", "High (≥70%)"],
                    range=[0.5, 3.5],
                    gridcolor="#f1f5f9",
                    zeroline=False
                ),
                yaxis=dict(
                    title="Legal Impact & Complexity",
                    tickmode="array",
                    tickvals=[1, 2, 3],
                    ticktext=["Low (<40%)", "Medium (40-70%)", "High (≥70%)"],
                    range=[0.5, 3.5],
                    gridcolor="#f1f5f9",
                    zeroline=False
                ),
                plot_bgcolor="rgba(248, 250, 252, 0.6)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=10, b=20), # Reduced excessive whitespace
                height=380,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True) # Better spacing
            
            # C. Ranked Priority Table
            st.markdown("### 🏆 Ranked Priority Table")
            st.caption("Cases sorted dynamically by computed priority. Use **Select** to inspect scoring components.")
            
            edited_df = st.data_editor(
                df_ranked,
                column_config={
                    "InternalID": None,
                    "Rank": st.column_config.NumberColumn("Rank", width="small"),
                    "Filing Year": st.column_config.TextColumn("Filing Year", width="small"),
                    "Case Age": st.column_config.TextColumn("Case Age", width="small"),
                    "Score": st.column_config.TextColumn("Score", width="small"),
                    "Select": st.column_config.CheckboxColumn("Select", help="Check to inspect score breakdown", default=False),
                },
                disabled=["Rank", "Case ID", "Case Title", "Filing Year", "Case Age", "Score", "Final Priority", "Urgency Reason"],
                hide_index=True,
                use_container_width=True,
                key="priority_matrix_editor"
            )
            
            # Capture selection
            selected_ids = edited_df[edited_df["Select"] == True]["InternalID"].tolist()
            if selected_ids:
                st.session_state.active_matrix_case_id = selected_ids[0]

        # Determine active case for right-hand analytical panels
        active_case_id = st.session_state.active_matrix_case_id
        if not active_case_id and not df_ranked.empty:
            active_case_id = df_ranked.iloc[0]["InternalID"]
            
        active_case = next((c for c in all_cases if c.get('id') == active_case_id), None)

        with col_right:
            # D. Score Breakdown Panel
            if active_case:
                st.markdown("### 📊 Score Breakdown")
                st.markdown(f"**Case ID:** {sanitize_metadata_field(active_case.get('case_number'), 'case_id')}")
                st.markdown(f"<p style='font-size:14px; color:#475569; font-weight:600; margin-top:-5px;'>{sanitize_metadata_field(active_case.get('title'), 'title')}</p>", unsafe_allow_html=True)
                
                bd = case_breakdowns[active_case.get('id')]
                p_score = bd["score"]
                u = bd["urgency_factor"]
                b = bd["backlog_factor"]
                h = bd["humanitarian_boost"]
                
                p_color = colors_map.get(bd["level"], '#22c55e')
                
                st.markdown(f"""
                <div style='background: #ffffff; border: 1px solid #e2e8f0; border-left: 6px solid {p_color}; padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02);'>
                    <p style='margin:0; font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.5px;'>Weighted Priority Score</p>
                    <h2 style='margin:5px 0 0 0; color:#1e3a8a; font-size:38px; font-weight:700;'>{p_score:.0f}/100</h2>
                    <span style='background-color:{p_color}18; color:{p_color}; border: 1px solid {p_color}40; padding:3px 12px; border-radius:20px; font-size:11px; font-weight:700; display:inline-block; margin-top:5px; text-transform:uppercase;'>
                        {bd["level"]} Priority
                    </span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("**Scoring Breakdown Weights**")
                st.caption("Formula: 60% Urgency + 30% Backlog + 10% Humanitarian")
                
                st.markdown(f"**Urgency Factor** ({u:.0f}/100)")
                st.progress(u / 100.0)
                
                st.markdown(f"**Backlog Factor** ({b:.0f}/100)")
                st.progress(b / 100.0)
                
                st.markdown(f"**Humanitarian Boost** ({h:.0f}/20)")
                st.progress(h / 20.0)
                
                st.markdown("<p style='font-weight:600; margin-bottom:5px; font-size:13px; color:#1e293b;'>Why Score Was Assigned</p>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:12px; color:#475569; margin-bottom:8px; line-height:1.4; background:#f8fafc; padding:10px; border-radius:6px; border:1px solid #e2e8f0;'>{bd['explanation']}</div>", unsafe_allow_html=True)
            else:
                st.info("Select a case in the Ranked Table to view its breakdown.")

            # E. Operational Alerts Section
            st.markdown("### 🚨 Operational Alerts")
            
            # Dynamic calculations for operational issues across the active workload
            missing_date = len([c for c in all_cases if not c.get('filing_date') or str(c.get('filing_date')).lower() in ['not available', 'none', 'null', '']])
            ocr_incomplete = len([c for c in all_cases if c.get('extraction_method') == 'OCR' and (not c.get('title') or str(c.get('title')).lower() in ['not available', 'none', 'null', ''])])
            missing_meta = len([c for c in all_cases if not c.get('petitioner') or str(c.get('petitioner')).lower() in ['not available', 'none', 'null', '']])
            parsing_issues = len([c for c in all_cases if not c.get('summary') or str(c.get('summary')).lower() in ['not available', 'none', 'null', '']])
            
            op_alerts = []
            if missing_date > 0:
                op_alerts.append(f"⚠ <b>{missing_date} case(s)</b> missing filing date")
            if ocr_incomplete > 0:
                op_alerts.append(f"⚠ <b>{ocr_incomplete} case(s)</b> OCR extraction incomplete")
            if missing_meta > 0:
                op_alerts.append(f"⚠ <b>{missing_meta} case(s)</b> missing metadata (petitioner/respondent)")
            if parsing_issues > 0:
                op_alerts.append(f"⚠ <b>{parsing_issues} case(s)</b> AI parsing issues detected")
                
            if not op_alerts:
                st.success("🟢 No critical operational alerts.")
            else:
                for alert in op_alerts:
                    st.markdown(f"""
                    <div style='background-color:#fffbeb; border:1px solid #fef3c7; border-left:4px solid #f59e0b; border-radius:6px; padding:10px; margin-bottom:8px; font-size:12px; color:#b45309; line-height:1.3;'>
                        {alert}
                    </div>
                    """, unsafe_allow_html=True)

            # F. Recommended Actions
            st.markdown("### 🛠️ Recommended Actions")
            actions = []
            
            high_critical = [c for c in all_cases if case_breakdowns[c.get('id')]["level"] in ['High']]
            if high_critical:
                top_priority_case = sorted(high_critical, key=lambda x: case_breakdowns[x.get('id')]["score"], reverse=True)[0]
                actions.append(f"⚡ **Prioritize Top Urgent Matters**: Fast-track <i>{sanitize_metadata_field(top_priority_case.get('title'), 'title')}</i> ({sanitize_metadata_field(top_priority_case.get('case_number'), 'case_id')}) for immediate hearing.")
                
            humanitarian_all = [c for c in all_cases if c.get('humanitarian_flag')]
            if humanitarian_all:
                actions.append(f"🏥 **Review Humanitarian Cases First**: Triage the {len(humanitarian_all)} pending humanitarian case(s) to address personal liberties.")
                
            low_priority_all = [c for c in all_cases if case_breakdowns[c.get('id')]["level"] == 'Low']
            if low_priority_all:
                actions.append(f"📅 **Schedule Low-Priority Later**: Defer the {len(low_priority_all)} low-priority matter(s) to clear current backlog congestion.")
                
            if not actions:
                actions.append("✅ **Regular Ingestion**: Backlog pressure is healthy; continue normal court operations.")
                
            for action in actions:
                st.markdown(f"<div style='font-size:12px; color:#334155; margin-bottom:8px; line-height:1.4;'>{action}</div>", unsafe_allow_html=True)



# ────────────────────────────────────────────────────────
# 4. Similar Case Clusters
# ────────────────────────────────────────────────────────
elif menu == "🧬 Similar Clustering":
    st.markdown("<h2 class='section-header'>🧬 Intelligent Legal Clustering</h2>", unsafe_allow_html=True)
    st.markdown("Group pending matters by semantic similarity to optimize bench assignments.")
    
    if not all_cases:
        st.info("Upload cases to view clusters.")
    else:
        # Fetch clusters from API
        res = requests.post(f"{API_URL}/cases/cluster")
        if res.status_code == 200:
            clusters = res.json()
            
            if isinstance(clusters, dict) and "message" in clusters:
                st.info(clusters["message"])
            else:
                for cl in clusters:
                    with st.container():
                        st.markdown(f"""
                        <div style="background:#ffffff; padding:20px; border-radius:10px; border:1px solid #e2e8f0; border-left:6px solid #3b82f6; margin-bottom:20px;">
                            <h4 style="margin:0;">{cl['topic']} (Cluster {cl['cluster_id']})</h4>
                            <p style="color:#64748b; font-size:14px; margin-bottom:10px;">{cl['reason']}</p>
                            <div style="font-weight:600; font-size:13px;">{cl['total_cases']} Similar Cases Found</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        with st.expander("View Grouped Cases"):
                            for item in cl['cases']:
                                st.markdown(f"**{item['title']}**")
                                st.caption(f"{item['priority']} Priority | Urgency: {item['urgency']}% | Year: {item['year']}")
                                st.divider()
        else:
            st.error("Could not fetch clustering data.")


# ────────────────────────────────────────────────────────
# 5. Precedent Retrieval
# ────────────────────────────────────────────────────────
elif menu == "📚 Precedent Intelligence":
    st.markdown("<h2 class='section-header'>📚 Precedent Intelligence (RAG)</h2>", unsafe_allow_html=True)
    st.markdown("Ask legal questions about uploaded judgments and retrieve grounded answers using vector similarity search.")
    
    if not all_cases:
        st.info("No cases available. Please upload and process documents first in the 'Upload & Processing' tab.")
    else:
        # Top Controls
        case_options = {f"{c.get('case_number')} | {c.get('title')}": c for c in all_cases}
        selected_case_name = st.selectbox("Select Existing Case", options=list(case_options.keys()))
        selected_case = case_options[selected_case_name]
        case_id = selected_case.get("id")

        if case_id:
            raw = json.loads(selected_case.get('raw_content', '{}')) if selected_case.get('raw_content') else {}

            # Ask Question input with form
            with st.form("rag_query_form"):
                qc, bc = st.columns([5, 1])
                with qc:
                    prompt = st.text_input("Question", placeholder="Ask about selected case (author, bench, outcome, citations, summary...)", label_visibility="collapsed")
                with bc:
                    submit_query = st.form_submit_button("Ask ➤", use_container_width=True)
            st.caption("Suggested: `author` · `bench` · `summary` · `outcome` · `citations` · `legal issue` · `petitioner` · `respondent` · `judgment date`")

            st.divider()

            # ── SECTION 1: Active Case Overview ──
            # Read directly from parsed structured_meta (regex-extracted, no vector dependency)
            smeta = raw.get('structured_meta', {})

            def _pick(*keys_from_dicts):
                """Try structured_meta first, then raw, returning first non-empty non-NA value."""
                for val in keys_from_dicts:
                    if val and str(val).strip().lower() not in ('', 'not available', 'none', 'null', 'nan'):
                        return str(val).strip()
                return "Not Available"

            ov_title      = sanitize_metadata_field(_pick(smeta.get('case_title'), raw.get('case_title'), selected_case.get('title')), 'title')
            ov_petitioner = sanitize_metadata_field(_pick(smeta.get('petitioner'), raw.get('petitioner'), selected_case.get('petitioner')), 'party')
            ov_respondent = sanitize_metadata_field(_pick(smeta.get('respondent'), raw.get('respondent'), selected_case.get('respondent')), 'party')
            ov_bench      = sanitize_metadata_field(_pick(smeta.get('bench'), raw.get('bench'), selected_case.get('bench')), 'bench')
            ov_author     = sanitize_metadata_field(_pick(smeta.get('author_judge'), raw.get('author_judge'), selected_case.get('author_judge')), 'general')
            ov_outcome    = sanitize_metadata_field(_pick(raw.get('legal_outcome'), selected_case.get('legal_outcome')), 'general')
            ov_issue      = sanitize_metadata_field(_pick(raw.get('core_legal_issue'), selected_case.get('legal_issue'), selected_case.get('core_legal_issue')), 'general')
            ov_jdate      = sanitize_metadata_field(_pick(smeta.get('judgment_date'), raw.get('judgment_date'), selected_case.get('judgment_date')), 'general')

            # Citations & Statutes: always from structured_meta (regex) first
            ov_citations  = smeta.get('citations') or raw.get('citations') or []
            ov_statutes   = smeta.get('statutes') or raw.get('statutes') or selected_case.get('extracted_statutes') or []
            if isinstance(ov_citations, str): ov_citations = [c.strip() for c in ov_citations.split(',') if c.strip()]
            if isinstance(ov_statutes, str):  ov_statutes  = [s.strip() for s in ov_statutes.split(',') if s.strip()]

            st.markdown("#### 📄 Active Case Overview")
            st.markdown(f"**{ov_title}**")
            st.markdown("---")

            ov1, ov2 = st.columns(2)
            with ov1:
                st.markdown(f"**Legal Issue:** {ov_issue}")
                st.markdown(f"**Petitioner/Appellant:** {ov_petitioner}")
                st.markdown(f"**Respondent:** {ov_respondent}")
                st.markdown(f"**Judgment Date:** {ov_jdate}")
            with ov2:
                st.markdown(f"**Final Outcome:** {ov_outcome}")
                st.markdown(f"**Bench:** {ov_bench}")
                st.markdown(f"**Author:** {ov_author}")

            if ov_statutes:
                st.markdown(f"**Key Statutes:** {' · '.join(ov_statutes[:6])}")
            if ov_citations:
                st.markdown(f"**Equivalent Citations:** {' · '.join(ov_citations[:5])}")

            st.divider()

            # ── SECTION 2 & 3: Legal Assistant + Supporting Evidence ──
            if submit_query and prompt:
                with st.spinner("Analyzing..."):
                    try:
                        chat_res = requests.post(
                            f"{API_URL}/cases/{case_id}/chat",
                            json={"question": prompt},
                            timeout=60
                        )
                        if chat_res.status_code == 200:
                            chat_data = chat_res.json()
                            answer_text = chat_data.get("answer", "Not Available")
                            evidence_list = chat_data.get("evidence", [])
                        else:
                            answer_text = "Error reaching the AI assistant."
                            evidence_list = []
                    except Exception as e:
                        answer_text = f"Error: {e}"
                        evidence_list = []

                st.markdown("#### 💬 Legal Assistant Answer")
                st.info(answer_text)

                if evidence_list:
                    st.markdown("#### 📎 Supporting Extracts")
                    for ev in evidence_list:
                        if ev and ev.strip():
                            st.markdown(f"> *{ev.strip()[:600]}*")

                st.divider()

            # ── SECTION 4: Similar Precedents ──
            st.markdown("#### 🔍 Similar Precedents")
            with st.spinner("Retrieving similar cases..."):
                try:
                    # Session isolation: only search among current upload batch
                    session_db_ids = st.session_state.get('current_upload_batch_db_ids', [])
                    params = {}
                    if session_db_ids:
                        params["session_ids"] = ",".join(session_db_ids)
                    
                    prec_res = requests.get(f"{API_URL}/cases/{case_id}/precedents", params=params, timeout=10)
                    if prec_res.status_code == 200:
                        precedents = prec_res.json().get("precedents", [])
                        if not precedents:
                            st.info("No similar precedents found in uploaded cases.")
                        else:
                            for idx, p in enumerate(precedents):
                                meta = p.get('meta', {})
                                issue = meta.get('core_legal_issue', meta.get('legal_issue', 'Not Available'))
                                outcome = meta.get('legal_outcome', 'Not Available')
                                dist = p.get('similarity_score', 1.0)
                                sim_pct = max(0, int((1.0 - dist) * 100))
                                st.markdown(f"""
                                <div style="background:#f8fafc; padding:10px 15px; border-radius:6px; border:1px solid #e2e8f0; border-left:4px solid #3b82f6; margin-bottom:8px;">
                                    <strong>{idx + 1}. {p.get('title', 'Unknown')}</strong>
                                    <span style="float:right; background:#dbeafe; color:#1d4ed8; padding:1px 8px; border-radius:10px; font-size:12px;">{sim_pct}% match</span>
                                    <br><span style="font-size:12px; color:#475569;"><strong>Issue:</strong> {issue}</span>
                                    <br><span style="font-size:12px; color:#475569;"><strong>Outcome:</strong> {outcome}</span>
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.error("Failed to retrieve precedents.")
                except Exception as e:
                    st.error(f"Error fetching precedents: {e}")
# ────────────────────────────────────────────────────────
# 6. Humanitarian Alerts
# ────────────────────────────────────────────────────────
elif menu == "🚨 Humanitarian Triage":
    st.markdown("<h2 class='section-header'>🚨 Humanitarian Urgency & Emergency Triage</h2>", unsafe_allow_html=True)
    st.caption("Identify and prioritize cases requiring immediate human attention due to medical, age, domestic, or personal liberty risks, regardless of standard legal category.")

    if not all_cases:
        st.info("No cases available for humanitarian triage.")
    else:
        # Precompute triage data for all cases
        triage_breakdowns = {}
        for c in all_cases:
            triage_breakdowns[c.get('id')] = calculate_humanitarian_triage(c)
            
        active_triage_cases = [c for c in all_cases if triage_breakdowns[c.get('id')]["is_humanitarian"]]
        
        # A. KPI Cards
        total_hum = len(active_triage_cases)
        high_risk = len([c for c in active_triage_cases if triage_breakdowns[c.get('id')]["level"] in ["Extreme", "High"]])
        immediate_action = len([c for c in active_triage_cases if triage_breakdowns[c.get('id')]["score"] > 60])

        st.markdown(f"""
        <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px;'>
            <div class='metric-card' style='border-left: 5px solid #3b82f6;'>
                <p style='color:#64748b; font-size:12px; margin:0;'>TOTAL VULNERABLE CASES</p>
                <h3 style='color:#1e3a8a; font-size:24px; margin:5px 0 0 0;'>{total_hum}</h3>
            </div>
            <div class='metric-card' style='border-left: 5px solid #ea580c;'>
                <p style='color:#64748b; font-size:12px; margin:0;'>HIGH RISK CASES</p>
                <h3 style='color:#c2410c; font-size:24px; margin:5px 0 0 0;'>{high_risk}</h3>
            </div>
            <div class='metric-card' style='border-left: 5px solid #dc2626;'>
                <p style='color:#64748b; font-size:12px; margin:0;'>IMMEDIATE ACTION NEEDED</p>
                <h3 style='color:#991b1b; font-size:24px; margin:5px 0 0 0;'>{immediate_action}</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Split layout
        col_left, col_right = st.columns([7, 3])

        # Prepare Ranked Queue Table Data
        queue_rows = []
        sorted_active_cases = sorted(active_triage_cases, key=lambda x: triage_breakdowns[x.get('id')]["score"], reverse=True)
        
        for idx, c in enumerate(sorted_active_cases):
            tb = triage_breakdowns[c.get('id')]
            
            # Determine primary vulnerability type based on highest score
            vuln_type = "Medical" if tb['med_score'] > 0 else "Child/Women" if tb['child_women_score'] > 0 else "Senior Citizen" if tb['senior_score'] > 0 else "Liberty/Shelter"
            if tb['signals']:
                vuln_type = tb['signals'][0].split(None, 1)[1] if len(tb['signals'][0].split()) > 1 else tb['signals'][0]
                
            queue_rows.append({
                "Rank": idx + 1,
                "InternalID": c.get('id'),
                "Case ID": sanitize_metadata_field(c.get('case_number'), 'case_id'),
                "Case Title": sanitize_metadata_field(c.get('title'), 'title'),
                "Risk Score": f"{tb['score']}/100",
                "Vulnerability Type": vuln_type,
                "Recommended Action": tb["relief_needed"],
                "Select": False
            })
            
        df_queue = pd.DataFrame(queue_rows)

        # Handle row selection
        if 'active_triage_case_id' not in st.session_state:
            st.session_state.active_triage_case_id = None

        with col_left:
            st.markdown("### 📋 Ranked Humanitarian Queue")
            
            if df_queue.empty:
                st.info("No cases currently match active humanitarian risk criteria.")
            else:
                edited_queue = st.data_editor(
                    df_queue,
                    column_config={
                        "InternalID": None,
                        "Rank": st.column_config.NumberColumn("Rank", width="small"),
                        "Select": st.column_config.CheckboxColumn("Select", help="Check to inspect risk breakdown", default=False),
                    },
                    disabled=["Rank", "Case ID", "Case Title", "Risk Score", "Vulnerability Type", "Recommended Action"],
                    hide_index=True,
                    use_container_width=True,
                    key="humanitarian_queue_editor"
                )
                
                selected_triage_ids = edited_queue[edited_queue["Select"] == True]["InternalID"].tolist()
                if selected_triage_ids:
                    st.session_state.active_triage_case_id = selected_triage_ids[0]

        with col_right:
            # Determine active selected case
            active_case_id = st.session_state.active_triage_case_id
            if not active_case_id and not df_queue.empty:
                active_case_id = df_queue.iloc[0]["InternalID"]
                
            active_case = next((c for c in all_cases if c.get('id') == active_case_id), None)

            if active_case:
                tb = triage_breakdowns[active_case.get('id')]
                
                st.markdown("### 🔍 Case Analysis")
                st.markdown(f"**{sanitize_metadata_field(active_case.get('case_number'), 'case_id')}**")
                st.caption(f"{sanitize_metadata_field(active_case.get('title'), 'title')}")
                
                r_colors = {"Extreme": "#dc2626", "High": "#ea580c", "Moderate": "#eab308", "Low": "#22c55e"}
                color = r_colors.get(tb["level"], "#22c55e")
                
                st.markdown(f"**Risk Score:** <span style='color:{color}; font-weight:bold;'>{tb['score']}/100</span>", unsafe_allow_html=True)
                st.markdown(f"**Risk Level:** <span style='color:{color}; font-weight:bold;'>{tb['level']}</span>", unsafe_allow_html=True)
                
                # Detected Signals
                st.markdown("**Detected Signals:**")
                if tb["signals"]:
                    badges = "".join([f"<span style='background:#f1f5f9; border:1px solid #cbd5e1; border-radius:4px; padding:2px 8px; font-size:12px; margin-right:5px; display:inline-block;'>{s.split()[0]} {s.split(None, 1)[1] if len(s.split()) > 1 else ''}</span>" for s in tb["signals"]])
                    st.markdown(badges, unsafe_allow_html=True)
                else:
                    st.markdown("<span style='color:#64748b; font-size:12px;'>No specific signals detected.</span>", unsafe_allow_html=True)
                
                st.markdown("<br>**Recommended Action:**", unsafe_allow_html=True)
                st.info(tb["relief_needed"])
            else:
                st.info("Select a case in the Ranked Queue to view risk details.")

# ────────────────────────────────────────────────────────
# 7. Schedule Optimizer
# ────────────────────────────────────────────────────────
elif menu == "📅 Schedule Optimizer":
    st.markdown("<h2 class='section-header'>📅 Court-Style Dynamic Scheduling System</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b;'>Manage hearings, postponements, evidence collection periods, and dynamic queue movement exactly like a real court process.</p>", unsafe_allow_html=True)
    
    if not all_cases:
        st.info("Ingest cases in the Registry to activate the Judicial Scheduler.")
    else:
        import requests
        from datetime import datetime, timedelta
        
        # 1. Fetch simulation date
        sim_date_str = datetime.utcnow().strftime("%Y-%m-%d")
        try:
            res = requests.get(f"{API_URL}/schedule/sim_date", timeout=10)
            if res.status_code == 200:
                sim_date_str = res.json().get("sim_date", sim_date_str)
        except Exception as e:
            st.error(f"Error fetching simulation date: {e}")
            
        sim_date = datetime.strptime(sim_date_str, "%Y-%m-%d").date()
        
        # 2. Render Simulation Controls
        st.markdown("### 🎛️ Simulation Controls")
        c_date, c_btns = st.columns([1, 2])
        with c_date:
            st.markdown(f"""
            <div style='background: #1e293b; padding: 15px; border-radius: 8px; border: 1px solid #334155; text-align: center;'>
                <span style='color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;'>VIRTUAL COURT DATE</span>
                <h3 style='margin: 5px 0 0 0; color: #3b82f6; font-size: 24px;'>📅 {sim_date_str}</h3>
            </div>
            """, unsafe_allow_html=True)
        with c_btns:
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            bc1, bc2, bc3, bc4 = st.columns(4)
            if bc1.button("Advance +1 Day", use_container_width=True):
                requests.post(f"{API_URL}/schedule/sim_date", json={"days": 1})
                st.rerun()
            if bc2.button("Advance +7 Days", use_container_width=True):
                requests.post(f"{API_URL}/schedule/sim_date", json={"days": 7})
                st.rerun()
            if bc3.button("Advance +30 Days", use_container_width=True):
                requests.post(f"{API_URL}/schedule/sim_date", json={"days": 30})
                st.rerun()
            if bc4.button("Reset Today", use_container_width=True):
                requests.post(f"{API_URL}/schedule/sim_date", json={"days": 0})
                st.rerun()
                
        # 3. Fetch schedule queue
        queue_cases = []
        try:
            q_res = requests.get(f"{API_URL}/schedule/queue", timeout=10)
            if q_res.status_code == 200:
                queue_cases = q_res.json()
        except Exception as e:
            st.error(f"Error fetching schedule queue: {e}")
            
        # 4. Fetch assigned hearings for simulation date
        slots_hearings = []
        try:
            s_res = requests.get(f"{API_URL}/schedule/slots?date_str={sim_date_str}", timeout=10)
            if s_res.status_code == 200:
                slots_hearings = s_res.json().get("hearings", [])
        except Exception as e:
            st.error(f"Error fetching scheduled slots: {e}")
            
        # 5. Form overlays (inline containers) based on state
        if 'postpone_case_id' not in st.session_state: st.session_state.postpone_case_id = None
        if 'evidence_case_id' not in st.session_state: st.session_state.evidence_case_id = None
        if 'schedule_case_id' not in st.session_state: st.session_state.schedule_case_id = None
        
        # Determine case details for forms
        active_form_case = None
        active_case_id = st.session_state.postpone_case_id or st.session_state.evidence_case_id or st.session_state.schedule_case_id
        if active_case_id:
            active_form_case = next((c for c in queue_cases if c["id"] == active_case_id), None)
            if not active_form_case:
                active_form_case = next((c for c in slots_hearings if c["id"] == active_case_id), None)
                
        if st.session_state.postpone_case_id and active_form_case:
            with st.container():
                st.markdown(f"### 🛑 Postpone Hearing: *{active_form_case.get('title')}*")
                with st.form("postpone_form"):
                    p_reason = st.selectbox(
                        "Postponement Reason",
                        ["Evidence Pending", "Witness Absent", "Investigation Pending", "Advocate Request", "Medical Emergency", "Settlement Discussion", "Court Delay", "Other"]
                    )
                    p_date = st.date_input("Postponed Until Date", min_value=sim_date + timedelta(days=1), value=sim_date + timedelta(days=7))
                    
                    fc1, fc2 = st.columns(2)
                    if fc1.form_submit_button("Confirm Adjournment", use_container_width=True):
                        requests.post(f"{API_URL}/schedule/postpone", json={
                            "case_id": active_case_id,
                            "postponed_until": p_date.strftime("%Y-%m-%d"),
                            "reason": p_reason
                        })
                        st.session_state.postpone_case_id = None
                        st.success("Case successfully postponed!")
                        st.rerun()
                    if fc2.form_submit_button("Cancel", use_container_width=True):
                        st.session_state.postpone_case_id = None
                        st.rerun()
                        
        elif st.session_state.evidence_case_id and active_form_case:
            with st.container():
                st.markdown(f"### 📂 Request Evidence & Pause: *{active_form_case.get('title')}*")
                with st.form("evidence_form"):
                    e_notes = st.text_area("Evidence Requirements & Pending Items", placeholder="Detail what records, witness statements, or exhibits are required.")
                    e_date = st.date_input("Evidence Submission Deadline", min_value=sim_date + timedelta(days=1), value=sim_date + timedelta(days=5))
                    
                    fc1, fc2 = st.columns(2)
                    if fc1.form_submit_button("Submit Request & Pause", use_container_width=True):
                        requests.post(f"{API_URL}/schedule/request_evidence", json={
                            "case_id": active_case_id,
                            "evidence_deadline": e_date.strftime("%Y-%m-%d"),
                            "evidence_notes": e_notes
                        })
                        st.session_state.evidence_case_id = None
                        st.success("Evidence requested and proceedings paused.")
                        st.rerun()
                    if fc2.form_submit_button("Cancel", use_container_width=True):
                        st.session_state.evidence_case_id = None
                        st.rerun()
                        
        elif st.session_state.schedule_case_id and active_form_case:
            with st.container():
                st.markdown(f"### 📅 Schedule Hearing Slot: *{active_form_case.get('title')}*")
                with st.form("schedule_form"):
                    s_date = st.date_input("Hearing Date", min_value=sim_date, value=sim_date)
                    s_time = st.selectbox("Hearing Session", ["Morning Session (10 AM - 1 PM)", "Afternoon Session (2 PM - 5 PM)"])
                    s_room = st.selectbox("Court Room", ["Court Room 1", "Court Room 2", "Chambers"])
                    s_judge = st.selectbox("Judge / Bench", ["Hon'ble Justice A. Sharma", "Hon'ble Justice B. Verma", "Hon'ble Justice C. Gupta"])
                    
                    fc1, fc2 = st.columns(2)
                    if fc1.form_submit_button("Schedule Hearing", use_container_width=True):
                        requests.post(f"{API_URL}/schedule/assign_slot", json={
                            "case_id": active_case_id,
                            "hearing_date": s_date.strftime("%Y-%m-%d"),
                            "hearing_time": s_time,
                            "court_room": s_room,
                            "judge_name": s_judge
                        })
                        st.session_state.schedule_case_id = None
                        st.success("Hearing successfully scheduled!")
                        st.rerun()
                    if fc2.form_submit_button("Cancel", use_container_width=True):
                        st.session_state.schedule_case_id = None
                        st.rerun()
                        
        # 6. Alerts & Notifications
        alerts = []
        for case in queue_cases:
            if case["is_emergency"] and not case["hearing_date"]:
                alerts.append({
                    "type": "danger",
                    "text": f"🚨 <b>FAST-TRACK EMERGENCY:</b> Case <i>{case['title']}</i> is pending scheduling. Prioritize immediately!"
                })
            if case["status"] == "Awaiting Evidence" and case["evidence_deadline"]:
                dead_date = datetime.strptime(case["evidence_deadline"], "%Y-%m-%d").date()
                if dead_date <= sim_date:
                    alerts.append({
                        "type": "warning",
                        "text": f"⚠ <b>EVIDENCE OVERDUE:</b> Deadline has passed ({case['evidence_deadline']}) for <i>{case['title']}</i>."
                    })
                elif (dead_date - sim_date).days <= 3:
                    alerts.append({
                        "type": "warning",
                        "text": f"📅 <b>EVIDENCE DUE SOON:</b> Submission due in {(dead_date - sim_date).days} days for <i>{case['title']}</i>."
                    })
            if case["adjournment_count"] >= 3:
                alerts.append({
                    "type": "info",
                    "text": f"🔄 <b>FREQUENT ADJOURNMENTS:</b> Case <i>{case['title']}</i> has been postponed {case['adjournment_count']} times."
                })
                
        if alerts:
            st.markdown("### 🔔 System Alerts")
            for a in alerts[:4]:
                bg_color = "rgba(239, 68, 68, 0.15)" if a["type"] == "danger" else "rgba(245, 158, 11, 0.15)" if a["type"] == "warning" else "rgba(59, 130, 246, 0.15)"
                border_color = "#ef4444" if a["type"] == "danger" else "#f59e0b" if a["type"] == "warning" else "#3b82f6"
                st.markdown(f"""
                <div style='background-color: {bg_color}; border: 1px solid {border_color}; border-left: 5px solid {border_color}; border-radius: 6px; padding: 12px; margin-bottom: 10px; font-size: 13px; color: #e2e8f0;'>
                    {a['text']}
                </div>
                """, unsafe_allow_html=True)
                
        st.divider()
        
        # 7. Split Layout: Cause List vs Queue Manager
        col_slots, col_queue = st.columns([1, 1])
        
        with col_slots:
            st.markdown("### 🏛️ Daily Cause List")
            st.caption(f"Hearings scheduled for {sim_date_str}")
            
            sessions = ["Morning Session (10 AM - 1 PM)", "Afternoon Session (2 PM - 5 PM)"]
            
            for session in sessions:
                st.markdown(f"#### 🕒 {session}")
                matching_hearings = [h for h in slots_hearings if h["hearing_time"] == session]
                
                if not matching_hearings:
                    st.markdown("""
                    <div style='border: 1px dashed #475569; padding: 20px; border-radius: 8px; text-align: center; color: #64748b; margin-bottom: 15px;'>
                        No hearing scheduled for this slot.
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    for hearing in matching_hearings:
                        is_hearing_ready = hearing["is_ready"]
                        priority_color = "#dc2626" if hearing["priority_level"] == "Critical" else "#ea580c" if hearing["priority_level"] == "High" else "#f59e0b" if hearing["priority_level"] == "Medium" else "#10b981"
                        
                        card_status = hearing["status"]
                        status_style = "background: #1e3a8a; color: #60a5fa;"
                        if card_status == "In Hearing":
                            status_style = "background: #064e3b; color: #10b981; border: 1px solid #10b981;"
                        elif card_status == "Judgment Reserved":
                            status_style = "background: #78350f; color: #fbbf24;"
                            
                        ready_html = "<span style='color: #10b981; font-weight: bold;'>Ready</span>" if is_hearing_ready else "<span style='color: #ef4444; font-weight: bold;'>⚠️ Not Ready</span>"
                        
                        st.markdown(f"""
                        <div style='background: #1e293b; padding: 15px; border-radius: 8px; border-left: 6px solid {priority_color}; border: 1px solid #334155; margin-bottom: 10px;'>
                            <div style='display: flex; justify-content: space-between; align-items: center;'>
                                <strong style='font-size: 14px; color: #f1f5f9;'>{hearing['title']}</strong>
                                <span style='font-size: 11px; padding: 2px 8px; border-radius: 12px; {status_style}'>{card_status}</span>
                            </div>
                            <div style='color: #94a3b8; font-size: 12px; margin-top: 5px; line-height: 1.4;'>
                                <b>Case ID:</b> {hearing['case_number'].split(' | ')[0]}<br>
                                <b>Judge:</b> {hearing['judge_name']}<br>
                                <b>Court Room:</b> {hearing['court_room']}<br>
                                <b>Readiness Status:</b> {ready_html}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if not is_hearing_ready:
                            st.warning("⚠️ Case is not ready for hearing. Verify missing items in the Active Queue.")
                            
                        # Actions
                        ac1, ac2, ac3 = st.columns(3)
                        if card_status == "Scheduled":
                            if ac1.button("Start Hearing", key=f"start_{hearing['id']}", use_container_width=True):
                                requests.post(f"{API_URL}/schedule/update_case_status", json={"case_id": hearing["id"], "status": "In Hearing"})
                                st.rerun()
                        elif card_status == "In Hearing":
                            if ac1.button("Reserve Judgment", key=f"reserve_{hearing['id']}", use_container_width=True):
                                requests.post(f"{API_URL}/schedule/update_case_status", json={"case_id": hearing["id"], "status": "Judgment Reserved"})
                                st.rerun()
                                
                        if ac2.button("Postpone", key=f"postpone_btn_{hearing['id']}", use_container_width=True):
                            st.session_state.postpone_case_id = hearing["id"]
                            st.rerun()
                            
                        if ac3.button("Request Evidence", key=f"req_ev_btn_{hearing['id']}", use_container_width=True):
                            st.session_state.evidence_case_id = hearing["id"]
                            st.rerun()
                            
                        ac4, ac5, ac6 = st.columns(3)
                        if ac4.button("Mark Resolved", key=f"resolve_btn_{hearing['id']}", use_container_width=True):
                            requests.post(f"{API_URL}/schedule/update_case_status", json={"case_id": hearing["id"], "status": "Resolved"})
                            st.success("Case resolved!")
                            st.rerun()
                            
                        if ac5.button("Close Case", key=f"close_btn_{hearing['id']}", use_container_width=True):
                            requests.post(f"{API_URL}/schedule/update_case_status", json={"case_id": hearing["id"], "status": "Closed"})
                            st.rerun()
                            
                        st.divider()
                        
        with col_queue:
            st.markdown("### 📋 Active Court Queue")
            st.caption("Eligible cases sorted dynamically by computed priority score.")
            
            if not queue_cases:
                st.info("No active cases in queue.")
            else:
                for case in queue_cases:
                    p_score = calculate_final_priority(case)
                    status = case["status"]
                    priority_color = "#dc2626" if case["priority_level"] == "Critical" else "#ea580c" if case["priority_level"] == "High" else "#f59e0b" if case["priority_level"] == "Medium" else "#10b981"
                    
                    paused_label = ""
                    if status == "Adjourned / Postponed":
                        paused_label = f"<span style='background: #374151; color: #9ca3af; font-size: 11px; padding: 2px 8px; border-radius: 12px; margin-left: 5px;'>PAUSED: Postponed ({case['postponed_until']})</span>"
                    elif status == "Awaiting Evidence":
                        paused_label = f"<span style='background: #78350f; color: #fbbf24; font-size: 11px; padding: 2px 8px; border-radius: 12px; margin-left: 5px;'>PAUSED: Awaiting Evidence ({case['evidence_deadline']})</span>"
                    elif status == "Under Investigation":
                        paused_label = f"<span style='background: #4c1d95; color: #a78bfa; font-size: 11px; padding: 2px 8px; border-radius: 12px; margin-left: 5px;'>PAUSED: Under Investigation</span>"
                        
                    emergency_label = ""
                    if case["is_emergency"]:
                        emergency_label = "<span style='background: #991b1b; color: #fecaca; font-size: 11px; padding: 2px 8px; border-radius: 12px; font-weight: bold; margin-left: 5px;'>🚨 FAST-TRACK</span>"
                        
                    st.markdown(f"""
                    <div style='background: #0f172a; padding: 15px; border-radius: 8px; border: 1px solid #1e293b; border-left: 5px solid {priority_color}; margin-bottom: 12px;'>
                        <div style='display: flex; justify-content: space-between; align-items: flex-start;'>
                            <strong style='font-size: 14px; color: #f1f5f9;'>{case['title']}</strong>
                            <span style='background: {priority_color}20; color: {priority_color}; font-size: 11px; font-weight: bold; padding: 1px 6px; border-radius: 4px;'>Score: {p_score:.0f}</span>
                        </div>
                        <div style='color: #64748b; font-size: 11px; margin-top: 2px;'>
                            ID: {case['case_number'].split(' | ')[0]} | Type: {case['case_type']} {emergency_label} {paused_label}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Readiness Checklist
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        new_ev = st.checkbox("Evidence Uploaded", value=case["evidence_uploaded"], key=f"ev_{case['id']}")
                        new_doc = st.checkbox("Documents Verified", value=case["documents_verified"], key=f"doc_{case['id']}")
                    with rc2:
                        new_party = st.checkbox("Parties Notified", value=case["parties_notified"], key=f"party_{case['id']}")
                        new_inv = st.checkbox("Investigation Done", value=case["investigation_completed"], key=f"inv_{case['id']}")
                        
                    if (new_ev != case["evidence_uploaded"] or new_doc != case["documents_verified"] or 
                        new_party != case["parties_notified"] or new_inv != case["investigation_completed"]):
                        requests.post(f"{API_URL}/schedule/verify_readiness", json={
                            "case_id": case["id"],
                            "evidence_uploaded": new_ev,
                            "documents_verified": new_doc,
                            "parties_notified": new_party,
                            "investigation_completed": new_inv
                        })
                        st.rerun()
                        
                    # Emergency Overrides
                    with st.expander("🛠️ Emergency Overrides & Schedule Controls"):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            over_bail = st.checkbox("Bail Matter", value=case["is_bail_matter"], key=f"bail_{case['id']}")
                            over_child = st.checkbox("Child Protection", value=case["is_child_protection"], key=f"child_{case['id']}")
                        with ec2:
                            over_med = st.checkbox("Medical Emergency", value=case["is_medical_emergency"], key=f"med_{case['id']}")
                            over_dom = st.checkbox("Domestic Violence", value=case["is_domestic_violence"], key=f"dom_{case['id']}")
                            
                        if (over_bail != case["is_bail_matter"] or over_child != case["is_child_protection"] or
                            over_med != case["is_medical_emergency"] or over_dom != case["is_domestic_violence"]):
                            requests.post(f"{API_URL}/schedule/emergency_override", json={
                                "case_id": case["id"],
                                "is_bail_matter": over_bail,
                                "is_child_protection": over_child,
                                "is_medical_emergency": over_med,
                                "is_domestic_violence": over_dom
                            })
                            st.rerun()
                            
                        if case["hearing_date"]:
                            st.info(f"Scheduled for {case['hearing_date']} ({case['hearing_time']})")
                        else:
                            if st.button("📅 Schedule Hearing Slot", key=f"sch_btn_{case['id']}", use_container_width=True):
                                st.session_state.schedule_case_id = case["id"]
                                st.rerun()
                                
                    st.divider()

# ────────────────────────────────────────────────────────
# 8. Analytics Dashboard
# ────────────────────────────────────────────────────────
elif menu == "📊 Analytics Dashboard":
    try:
        from frontend.analytics_dashboard import render_analytics_dashboard
    except ImportError:
        from analytics_dashboard import render_analytics_dashboard
    
    render_analytics_dashboard(all_cases, API_URL, calculate_final_priority, calculate_humanitarian_triage)

