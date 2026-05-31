"""
core/analytics.py
=================
Analytics Engine  —  Version 2.0
Delegates all priority scoring to the canonical priority_engine.py
and adds richer humanitarian/constitutional evaluation helpers.
"""

from typing import Dict, Any, List
import re

from core.priority_engine import (
    _build_text_blob,
    _constitutional_floor,
    _medical_emergency_check,
    _compute_urgency,
    _compute_backlog,
    _compute_humanitarian,
    score_to_level,
    CONSTITUTIONAL_CRITICAL_SIGNALS,
    MEDICAL_EMERGENCY_SIGNALS,
    HUMANITARIAN_TIERS,
)


class AnalyticsEngine:
    """
    Wraps the priority_engine pipeline and exposes helper methods
    for humanitarian evaluation, delay analysis, and explanation generation.
    """

    def __init__(self):
        # Weights mirror priority_engine.py (single source of truth)
        self.weights = {
            "urgency":       0.55,
            "backlog":       0.25,
            "humanitarian":  0.20,
        }

    # ── Primary scoring entry point ────────────────────────────────────────────
    def calculate_priority_score(
        self,
        metadata: Dict[str, Any],
        raw_text: str = "",
    ) -> Dict[str, Any]:
        """
        Compute the full priority breakdown for a case.

        Returns dict with keys:
            score, level, urgency, backlog, humanitarian_boost,
            constitutional_floor, medical_escalation,
            triggered_signals, explanation
        """
        # Merge raw_text into metadata so the pipeline can see all content
        if raw_text:
            existing = metadata.get("_text_blob", "")
            metadata = dict(metadata)
            metadata["_text_blob"] = (existing + " " + raw_text).strip()

        blob = _build_text_blob(metadata)

        # Layer 1 — Constitutional floor
        const_floor, const_signals = _constitutional_floor(blob, metadata)

        # Layer 2 — Medical emergency
        med_floor, med_signals = _medical_emergency_check(blob, metadata)
        hard_floor = max(const_floor, med_floor)

        # Layer 3 — Urgency
        urgency, urgency_signals = _compute_urgency(blob, metadata)

        # Layer 4 — Backlog
        backlog, age_days, age_label = _compute_backlog(metadata)

        # Layer 5 — Humanitarian
        humanitarian, hum_signals = _compute_humanitarian(blob, metadata)

        # Weighted combination → apply hard floor
        raw_score = (
            (urgency     * self.weights["urgency"]) +
            (backlog     * self.weights["backlog"]) +
            (humanitarian * self.weights["humanitarian"])
        )
        final_score = round(min(max(raw_score, hard_floor), 100.0), 2)
        level = score_to_level(final_score)

        all_signals = const_signals + med_signals + urgency_signals + hum_signals

        explanation = self._generate_explanation(
            metadata, final_score, level, urgency, backlog,
            humanitarian, const_floor, med_floor, all_signals, age_label
        )

        return {
            "score":               final_score,
            "level":               level,
            "urgency":             round(urgency, 2),
            "backlog":             round(backlog, 2),
            "humanitarian_boost":  round(humanitarian, 2),
            "constitutional_floor": const_floor,
            "medical_escalation":  med_floor,
            "triggered_signals":   all_signals[:10],
            "explanation":         explanation,
        }

    # ── Backlog helper (kept for backward compat) ──────────────────────────────
    def compute_backlog_score(self, metadata: Dict[str, Any]) -> float:
        backlog, _, _ = _compute_backlog(metadata)
        return backlog

    # ── Humanitarian boolean flag ──────────────────────────────────────────────
    def evaluate_humanitarian(self, data: Dict[str, Any]) -> bool:
        """
        Returns True if ANY humanitarian indicator is present.
        Used to set humanitarian_flag on the Case ORM object.
        """
        blob = _build_text_blob(data).lower()

        # Constitutional/medical are automatically humanitarian
        for sig in CONSTITUTIONAL_CRITICAL_SIGNALS:
            if sig in blob:
                return True
        for sig in MEDICAL_EMERGENCY_SIGNALS:
            if sig in blob:
                return True

        # Tiered humanitarian keywords
        for sig, _ in HUMANITARIAN_TIERS:
            if sig in blob:
                return True

        # ORM flags
        flag_keys = [
            "humanitarian_flag", "is_bail_matter", "is_child_protection",
            "is_medical_emergency", "is_domestic_violence", "constitutional_flag",
        ]
        for key in flag_keys:
            if data.get(key):
                return True

        return False

    # ── Explanation generator ──────────────────────────────────────────────────
    def _generate_explanation(
        self,
        metadata: Dict[str, Any],
        final_score: float,
        level: str,
        urgency: float,
        backlog: float,
        humanitarian: float,
        const_floor: float,
        med_floor: float,
        signals: List[str],
        age_label: str,
    ) -> str:
        # Prefer a pre-computed LLM reasoning if high quality
        llm_reasoning = metadata.get("priority_reasoning_summary", "")
        if llm_reasoning and len(str(llm_reasoning).strip()) > 40:
            return str(llm_reasoning).strip()

        parts = []

        if const_floor >= 86:
            parts.append(
                "⚖️ Constitutional/liberty violation — mandatory Critical floor applied."
            )
        if med_floor >= 86:
            parts.append(
                "🏥 Medical emergency detected — immediate judicial attention required."
            )

        if urgency >= 90:
            parts.append("🔴 Extreme urgency: immediate legal/humanitarian threat identified.")
        elif urgency >= 75:
            parts.append("🟠 High urgency: serious legal or humanitarian risk present.")
        elif urgency >= 55:
            parts.append("🟡 Moderate urgency from case content.")

        if humanitarian >= 60:
            parts.append("💛 Strong humanitarian imperative — vulnerable parties severely affected.")
        elif humanitarian >= 30:
            parts.append("💛 Humanitarian vulnerability factors detected.")

        if backlog >= 70:
            parts.append(f"📅 Severe judicial delay — {age_label}.")
        elif backlog >= 40:
            parts.append(f"📅 Significant backlog — {age_label}.")

        top_signals = [
            s for s in signals
            if not s.endswith("=True") and ":" not in s
        ][:4]
        if top_signals:
            parts.append(f"Key factors: {', '.join(top_signals)}.")

        age_days = metadata.get("case_age_days", 0)
        if age_days and int(age_days) > 365 * 3:
            parts.append(
                f"Significant backlog delay ({int(age_days) // 365} years)."
            )

        if not parts:
            parts.append("Standard priority based on baseline case features.")

        return " ".join(parts)


# ── Singleton ─────────────────────────────────────────────────────────────────
analytics_engine = AnalyticsEngine()
