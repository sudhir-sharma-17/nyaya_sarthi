"""
core/priority_engine.py
=======================
JUDICIAL PRIORITY ENGINE  —  Version 2.0
Legally Intelligent · Humanitarian-Aware · Context-Sensitive

Architecture: 5-layer scoring pipeline
  Layer 1 — Constitutional Floor Guarantee (hard minimum)
  Layer 2 — Medical Emergency Auto-Escalation
  Layer 3 — Urgency Score  (text-aware, multi-signal)
  Layer 4 — Backlog / Delay Score
  Layer 5 — Humanitarian Triage Boost

Final Score = (urgency × 0.55) + (backlog × 0.25) + (humanitarian × 0.20)
Then apply hard floor from Layers 1 & 2.

Levels:
    0  – 30  → Low
    31 – 60  → Medium
    61 – 85  → High
    86 – 100 → Critical
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import re

# ── Priority Level Thresholds ──────────────────────────────────────────────────
LEVEL_CRITICAL = 86
LEVEL_HIGH     = 61
LEVEL_MEDIUM   = 31

# ── Constitutional & Liberty Signals → HARD FLOOR 86 (Critical) ───────────────
CONSTITUTIONAL_CRITICAL_SIGNALS: List[str] = [
    # Article violations
    "article 21", "art. 21", "art 21",
    "article 14", "art. 14", "art 14",
    "article 32", "art. 32", "art 32",
    "right to life", "right to liberty", "personal liberty",
    "fundamental right",

    # Habeas corpus & detention
    "habeas corpus", "illegal detention", "unlawful detention",
    "wrongful detention", "preventive detention",
    "national security act", "nsa detention",
    "maintenance of internal security act", "misa",
    "conservation of foreign exchange",

    # Custodial abuse
    "custodial torture", "custodial death", "custodial violence",
    "custodial abuse", "custodial neglect",
    "third degree", "police torture",

    # Constitutional urgency
    "constitutional emergency", "urgent constitutional",
    "liberty violation", "state repression",
]

# ── Medical Emergency Signals → HARD FLOOR 86 (Critical) ──────────────────────
MEDICAL_EMERGENCY_SIGNALS: List[str] = [
    "kidney failure", "renal failure", "dialysis",
    "icu", "intensive care unit", "ventilator", "life support",
    "organ failure", "liver failure", "heart failure",
    "life threatening", "life-threatening", "terminal illness",
    "cancer treatment", "chemotherapy", "radiation therapy",
    "sepsis", "coma", "brain damage",
    "prison medical neglect", "jail medical", "custody medical",
    "denied medical", "refused treatment", "no medical care",
    "emergency surgery", "emergency treatment", "critical condition",
    "palliative care", "end stage",
]

# ── High Urgency Signals → Score >= 75 ────────────────────────────────────────
HIGH_URGENCY_SIGNALS: List[Tuple[str, float]] = [
    # Bail & liberty
    ("bail",                    15.0),
    ("anticipatory bail",       20.0),
    ("default bail",            20.0),
    ("bail rejected",           22.0),
    ("repeated bail rejection", 25.0),
    ("bail denial",             22.0),
    ("bail refused",            22.0),
    ("undertrial",              18.0),
    ("remand",                  15.0),

    # Detention
    ("detention",               18.0),
    ("preventive detention",    25.0),
    ("illegal custody",         25.0),

    # Child welfare
    ("child",                   15.0),
    ("minor",                   15.0),
    ("juvenile",                18.0),
    ("child abuse",             25.0),
    ("child protection",        22.0),
    ("custody of child",        22.0),
    ("education disruption",    18.0),
    ("school",                  10.0),

    # Domestic violence & sexual violence
    ("domestic violence",       22.0),
    ("sexual assault",          25.0),
    ("rape",                    25.0),
    ("pocso",                   25.0),
    ("harassment",              15.0),

    # Writ / constitutional
    ("writ petition",           20.0),
    ("pil",                     18.0),
    ("public interest",         15.0),
    ("mandamus",                15.0),
    ("certiorari",              15.0),
    ("prohibition",             15.0),

    # Human rights
    ("human rights",            20.0),
    ("state negligence",        20.0),
    ("state liability",         18.0),
    ("compensation",            10.0),
    ("rehabilitation",          10.0),

    # Delay-specific
    ("delayed trial",           18.0),
    ("prolonged detention",     22.0),
    ("charge sheet",            12.0),
    ("delayed chargesheet",     18.0),
    ("speedy trial",            18.0),
    ("adjournment",             10.0),
    ("repeated adjournment",    15.0),

    # Medical (below critical threshold)
    ("medical",                 12.0),
    ("health",                  10.0),
    ("disability",              15.0),
    ("mental health",           15.0),

    # Poverty / vulnerability
    ("poverty",                 12.0),
    ("destitute",               15.0),
    ("senior citizen",          15.0),
    ("elderly",                 15.0),
    ("widow",                   15.0),
    ("orphan",                  18.0),

    # Criminal urgency
    ("murder",                  18.0),
    ("death sentence",          25.0),
    ("capital punishment",      25.0),
    ("death penalty",           25.0),
    ("acquittal",               12.0),
    ("conviction",              12.0),
]

# ── Moderate Urgency Signals ───────────────────────────────────────────────────
MODERATE_URGENCY_SIGNALS: List[Tuple[str, float]] = [
    ("appeal",          8.0),
    ("revision",        8.0),
    ("review",          8.0),
    ("quashing",       10.0),
    ("stay",           10.0),
    ("interim relief", 10.0),
    ("injunction",     10.0),
    ("eviction",        8.0),
    ("property",        5.0),
    ("contract",        5.0),
    ("recovery",        5.0),
    ("arbitration",     5.0),
    ("taxation",        5.0),
    ("commercial",      5.0),
    ("service matter",  6.0),
    ("pension",         8.0),
    ("land",            6.0),
    ("matrimonial",     8.0),
    ("divorce",         8.0),
]

# ── Humanitarian Triage Indicators (additive boosts) ──────────────────────────
HUMANITARIAN_TIERS: List[Tuple[str, float]] = [
    # Tier 1 — severe (25 pts each, capped)
    ("custodial suffering",      25.0),
    ("custodial torture",        25.0),
    ("custodial neglect",        25.0),
    ("child welfare",            22.0),
    ("child abuse",              22.0),
    ("medical neglect",          22.0),
    ("life threatening",         22.0),
    ("organ failure",            22.0),
    ("dialysis",                 22.0),
    ("kidney failure",           22.0),
    ("illegal detention",        22.0),
    ("wrongful imprisonment",    22.0),

    # Tier 2 — high (15 pts each)
    ("domestic violence",        15.0),
    ("sexual assault",           15.0),
    ("disability",               15.0),
    ("severe poverty",           15.0),
    ("destitute",                15.0),
    ("orphan",                   15.0),
    ("widow",                    15.0),
    ("education disruption",     15.0),
    ("family suffering",         15.0),
    ("family separation",        15.0),

    # Tier 3 — moderate (10 pts each)
    ("senior citizen",           10.0),
    ("elderly",                  10.0),
    ("mental health",            10.0),
    ("poverty",                  10.0),
    ("undertrial",               10.0),
    ("juvenile",                 10.0),
    ("minor",                    10.0),
    ("child",                    10.0),
    ("bail",                      8.0),
    ("medical",                   8.0),
    ("legal aid",                  8.0),
    ("custody",                    8.0),
    ("detention",                  8.0),
]


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def score_to_level(score: float) -> str:
    """Convert a numeric priority score to its label."""
    if score >= LEVEL_CRITICAL:
        return "Critical"
    elif score >= LEVEL_HIGH:
        return "High"
    elif score >= LEVEL_MEDIUM:
        return "Medium"
    return "Low"


def compute_priority_score(case: Dict[str, Any]) -> float:
    """
    Compute the unified Priority Score for a case dict / ORM-like mapping.
    Returns float in [0.0, 100.0], rounded to 2 decimal places.
    """
    breakdown = _compute_full_breakdown(case)
    return breakdown["score"]


def get_priority_level(case: Dict[str, Any]) -> str:
    """Return the priority level label for a case dict."""
    return score_to_level(compute_priority_score(case))


def compute_priority_breakdown(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a detailed breakdown dict used by explanation panels.
    Keys: score, level, urgency, backlog, humanitarian, age_days, age_label,
          constitutional_floor, medical_escalation, triggered_signals
    """
    return _compute_full_breakdown(case)


def compute_priority_score_from_orm(case_obj) -> float:
    """
    Convenience wrapper that accepts a SQLAlchemy ORM Case object
    and returns the unified Priority Score.
    """
    # Pull all text fields together so signal detection works on the
    # full content the ORM holds, not just title/summary.
    raw_content = getattr(case_obj, "raw_content", "") or ""
    combined_text = " ".join(filter(None, [
        getattr(case_obj, "title",       ""),
        getattr(case_obj, "summary",     ""),
        getattr(case_obj, "legal_issue", ""),
        getattr(case_obj, "reasoning",   ""),
        raw_content[:3000],               # first 3 KB of raw JSON is enough
    ]))

    return compute_priority_score({
        "case_age_days":        getattr(case_obj, "case_age_days",        0),
        "filing_date":          getattr(case_obj, "filing_date",          None),
        "case_type":            getattr(case_obj, "case_type",            ""),
        "constitutional_flag":  getattr(case_obj, "constitutional_flag",  False),
        "title":                getattr(case_obj, "title",                ""),
        "summary":              getattr(case_obj, "summary",              ""),
        "legal_issue":          getattr(case_obj, "legal_issue",          ""),
        "reasoning":            getattr(case_obj, "reasoning",            ""),
        "humanitarian_flag":    getattr(case_obj, "humanitarian_flag",    False),
        "inactivity_days":      getattr(case_obj, "inactivity_days",      0),
        "adjournment_count":    getattr(case_obj, "adjournment_count",    0),
        "is_bail_matter":       getattr(case_obj, "is_bail_matter",       False),
        "is_child_protection":  getattr(case_obj, "is_child_protection",  False),
        "is_medical_emergency": getattr(case_obj, "is_medical_emergency", False),
        "is_domestic_violence": getattr(case_obj, "is_domestic_violence", False),
        "_text_blob":           combined_text,
    })


# ══════════════════════════════════════════════════════════════════════════════
#  INTERNAL PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def _compute_full_breakdown(case: Dict[str, Any]) -> Dict[str, Any]:
    """5-layer scoring pipeline — single source of truth."""

    # ── Build unified text corpus ──────────────────────────────────────────────
    blob = _build_text_blob(case)

    # ── Layer 1: Constitutional / Liberty Floor ────────────────────────────────
    constitutional_floor, constitutional_signals = _constitutional_floor(blob, case)

    # ── Layer 2: Medical Emergency Auto-Escalation ─────────────────────────────
    medical_escalation, medical_signals = _medical_emergency_check(blob, case)

    # Hard floor = max of both escalation triggers
    hard_floor = max(constitutional_floor, medical_escalation)

    # ── Layer 3: Urgency Score ─────────────────────────────────────────────────
    urgency, urgency_signals = _compute_urgency(blob, case)

    # ── Layer 4: Backlog / Delay Score ────────────────────────────────────────
    backlog, age_days, age_label = _compute_backlog(case)

    # ── Layer 5: Humanitarian Triage Boost ────────────────────────────────────
    humanitarian, humanitarian_signals = _compute_humanitarian(blob, case)

    # ── Weighted combination ───────────────────────────────────────────────────
    raw_score = (urgency * 0.55) + (backlog * 0.25) + (humanitarian * 0.20)
    raw_score = round(min(max(raw_score, 0.0), 100.0), 2)

    # Apply hard floor (constitutional / medical guarantees)
    final_score = round(max(raw_score, hard_floor), 2)
    final_score = round(min(final_score, 100.0), 2)

    level = score_to_level(final_score)

    # ── Explanation ────────────────────────────────────────────────────────────
    all_signals = constitutional_signals + medical_signals + urgency_signals + humanitarian_signals
    explanation = _build_explanation(
        final_score, level, urgency, backlog, humanitarian,
        constitutional_floor, medical_escalation, all_signals, age_label
    )

    return {
        "score":                 final_score,
        "level":                 level,
        "urgency":               round(urgency, 2),
        "backlog":               round(backlog, 2),
        "humanitarian":          round(humanitarian, 2),
        "age_days":              age_days,
        "age_label":             age_label,
        "constitutional_floor":  constitutional_floor,
        "medical_escalation":    medical_escalation,
        "triggered_signals":     all_signals[:10],   # top 10 for UI
        "explanation":           explanation,
    }


def _build_text_blob(case: Dict[str, Any]) -> str:
    """Combine all text fields into one lower-cased blob for signal scanning."""
    # If caller pre-built the blob (e.g. from ORM), use it
    pre = case.get("_text_blob", "")
    if pre:
        return pre.lower()

    parts = [
        str(case.get("title",       "") or ""),
        str(case.get("summary",     "") or ""),
        str(case.get("legal_issue", "") or ""),
        str(case.get("reasoning",   "") or ""),
        str(case.get("case_type",   "") or ""),
        str(case.get("petitioner",  "") or ""),
        str(case.get("respondent",  "") or ""),
    ]
    return " ".join(parts).lower()


# ── Layer 1: Constitutional Floor ─────────────────────────────────────────────

def _constitutional_floor(blob: str, case: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    If ANY constitutional / liberty signal is detected, the case can NEVER
    be below Critical (score floor = 86).
    """
    triggered = []

    # Check ORM flags first
    if case.get("constitutional_flag"):
        triggered.append("constitutional_flag=True")

    for signal in CONSTITUTIONAL_CRITICAL_SIGNALS:
        if signal in blob:
            triggered.append(signal)

    if triggered:
        return 86.0, triggered
    return 0.0, []


# ── Layer 2: Medical Emergency ────────────────────────────────────────────────

def _medical_emergency_check(blob: str, case: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    If ANY medical emergency signal is present, floor = 86 (Critical).
    """
    triggered = []

    if case.get("is_medical_emergency"):
        triggered.append("is_medical_emergency=True")

    for signal in MEDICAL_EMERGENCY_SIGNALS:
        if signal in blob:
            triggered.append(signal)

    if triggered:
        return 86.0, triggered
    return 0.0, []


# ── Layer 3: Urgency Score ─────────────────────────────────────────────────────

def _compute_urgency(blob: str, case: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    Multi-signal urgency score [0, 100].
    Base = 30. Additive boosts from HIGH and MODERATE signal tables.
    ORM emergency flags → instant 100.
    """
    triggered: List[str] = []

    # Hard overrides from ORM flags
    if case.get("is_bail_matter"):
        triggered.append("is_bail_matter")
    if case.get("is_child_protection"):
        triggered.append("is_child_protection")
    if case.get("is_medical_emergency"):
        triggered.append("is_medical_emergency")
    if case.get("is_domestic_violence"):
        triggered.append("is_domestic_violence")
    if triggered:
        return 100.0, triggered

    urgency = 30.0

    # Case-type base bumps
    ct = str(case.get("case_type", "") or "").lower()
    if any(k in ct for k in ("constitutional", "writ", "pil", "habeas")):
        urgency += 30.0
        triggered.append(f"case_type:{ct}")
    elif any(k in ct for k in ("criminal", "bail", "detention")):
        urgency += 22.0
        triggered.append(f"case_type:{ct}")
    elif any(k in ct for k in ("appeal", "review", "revision")):
        urgency += 15.0
        triggered.append(f"case_type:{ct}")
    else:
        urgency += 8.0

    # HIGH urgency signals
    for signal, boost in HIGH_URGENCY_SIGNALS:
        if signal in blob:
            urgency += boost
            triggered.append(signal)
            if urgency >= 100.0:
                break

    # MODERATE urgency signals (only if not already maxed)
    if urgency < 100.0:
        for signal, boost in MODERATE_URGENCY_SIGNALS:
            if signal in blob:
                urgency += boost
                triggered.append(signal)
                if urgency >= 100.0:
                    break

    # Inactivity penalty
    inactivity = _safe_int(case.get("inactivity_days", 0))
    if inactivity > 730:
        urgency += 20.0
        triggered.append(f"inactivity:{inactivity}d")
    elif inactivity > 365:
        urgency += 15.0
        triggered.append(f"inactivity:{inactivity}d")
    elif inactivity > 180:
        urgency += 8.0
        triggered.append(f"inactivity:{inactivity}d")

    # Adjournment count
    adj = _safe_int(case.get("adjournment_count", 0))
    if adj >= 10:
        urgency += 15.0
        triggered.append(f"adjournments:{adj}")
    elif adj >= 5:
        urgency += 8.0
        triggered.append(f"adjournments:{adj}")
    elif adj >= 3:
        urgency += 4.0
        triggered.append(f"adjournments:{adj}")

    return round(min(urgency, 100.0), 2), triggered


# ── Layer 4: Backlog / Delay ───────────────────────────────────────────────────

def _compute_backlog(case: Dict[str, Any]) -> Tuple[float, int, str]:
    """Backlog score [0, 100] based on case age and delay signals."""
    age_days = _safe_int(case.get("case_age_days", 0))

    # Fallback: compute from filing_date
    if not age_days and case.get("filing_date"):
        from datetime import datetime
        try:
            fd = case["filing_date"]
            if isinstance(fd, str):
                fd = datetime.fromisoformat(fd.replace("Z", ""))
            elif not isinstance(fd, datetime):
                fd = None
            if fd:
                age_days = (datetime.utcnow() - fd).days
        except Exception:
            age_days = 0

    # Progressive scale (Indian court backlog reality)
    if age_days > 365 * 15:
        backlog = 100.0
        age_label = f"{age_days // 365} years (extreme backlog)"
    elif age_days > 365 * 10:
        backlog = 90.0
        age_label = f"{age_days // 365} years (severe backlog)"
    elif age_days > 365 * 7:
        backlog = 80.0
        age_label = f"{age_days // 365} years (high backlog)"
    elif age_days > 365 * 5:
        backlog = 70.0
        age_label = f"{age_days // 365} years (significant backlog)"
    elif age_days > 365 * 3:
        backlog = 55.0
        age_label = f"{age_days // 365} years (moderate backlog)"
    elif age_days > 365 * 1:
        backlog = 35.0
        age_label = "over 1 year old"
    elif age_days > 180:
        backlog = 20.0
        age_label = f"{age_days} days old"
    else:
        backlog = 10.0
        age_label = f"{age_days} days old"

    return round(backlog, 2), age_days, age_label


# ── Layer 5: Humanitarian Triage ──────────────────────────────────────────────

def _compute_humanitarian(blob: str, case: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    Additive humanitarian boost [0, 100].
    Scans tiered keyword list; each tier contributes once per signal.
    """
    triggered: List[str] = []
    total = 0.0

    # ORM flags
    if case.get("humanitarian_flag"):
        total += 20.0
        triggered.append("humanitarian_flag=True")
    if case.get("is_child_protection"):
        total += 22.0
        triggered.append("is_child_protection=True")
    if case.get("is_domestic_violence"):
        total += 15.0
        triggered.append("is_domestic_violence=True")
    if case.get("is_medical_emergency"):
        total += 22.0
        triggered.append("is_medical_emergency=True")

    # Keyword tiers
    for signal, boost in HUMANITARIAN_TIERS:
        if signal in blob:
            total += boost
            triggered.append(signal)
            if total >= 100.0:
                break

    return round(min(total, 100.0), 2), triggered


# ── Explanation Builder ───────────────────────────────────────────────────────

def _build_explanation(
    score: float,
    level: str,
    urgency: float,
    backlog: float,
    humanitarian: float,
    constitutional_floor: float,
    medical_escalation: float,
    signals: List[str],
    age_label: str,
) -> str:
    parts = []

    if constitutional_floor >= 86:
        parts.append(
            "⚖️ Constitutional/liberty violation detected — case carries mandatory Critical floor priority."
        )
    if medical_escalation >= 86:
        parts.append(
            "🏥 Medical emergency condition detected — immediate judicial attention required."
        )

    if urgency >= 90:
        parts.append("🔴 Extreme urgency: immediate legal or humanitarian threat identified.")
    elif urgency >= 75:
        parts.append("🟠 High urgency: serious legal/humanitarian risk present.")
    elif urgency >= 55:
        parts.append("🟡 Moderate urgency from case content analysis.")

    if humanitarian >= 60:
        parts.append("💛 Strong humanitarian imperative — vulnerable parties affected.")
    elif humanitarian >= 30:
        parts.append("💛 Humanitarian vulnerability factors detected.")

    if backlog >= 70:
        parts.append(f"📅 Severe judicial delay — {age_label}.")
    elif backlog >= 40:
        parts.append(f"📅 Significant backlog — {age_label}.")

    top_signals = [s for s in signals if not s.endswith("=True") and ":" not in s][:4]
    if top_signals:
        parts.append(f"Key factors: {', '.join(top_signals)}.")

    if not parts:
        parts.append("Standard priority based on case features and judicial guidelines.")

    return " ".join(parts)


# ── Private helpers ───────────────────────────────────────────────────────────

def _safe_int(val: Any) -> int:
    try:
        return int(val or 0)
    except (TypeError, ValueError):
        return 0
