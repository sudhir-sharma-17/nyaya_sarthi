"""
Centralized Judicial Operations Analytics Dashboard
Aggregates insights from all platform modules into a unified control room.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import requests
from datetime import datetime, timedelta


def render_analytics_dashboard(all_cases, API_URL, calculate_final_priority, calculate_humanitarian_triage):
    st.markdown("<h2 class='section-header'>📊 Judicial Operations Control Room</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b;'>Centralized operational intelligence aggregating insights from Case Registry, Priority Matrix, Humanitarian Triage, Schedule Optimizer & Precedent Intelligence.</p>", unsafe_allow_html=True)

    if not all_cases:
        st.info("Ingest cases to view analytics.")
        return

    # ── Fetch scheduling data ──
    sim_date_str = datetime.utcnow().strftime("%Y-%m-%d")
    queue_cases = []
    slots_hearings = []
    try:
        res = requests.get(f"{API_URL}/schedule/sim_date", timeout=5)
        if res.status_code == 200:
            sim_date_str = res.json().get("sim_date", sim_date_str)
    except: pass
    try:
        q = requests.get(f"{API_URL}/schedule/queue", timeout=5)
        if q.status_code == 200: queue_cases = q.json()
    except: pass
    try:
        s = requests.get(f"{API_URL}/schedule/slots?date_str={sim_date_str}", timeout=5)
        if s.status_code == 200: slots_hearings = s.json().get("hearings", [])
    except: pass

    sim_date = datetime.strptime(sim_date_str, "%Y-%m-%d").date()

    # ── Precompute aggregations ──
    total = len(all_cases)
    statuses = [c.get("status", "Pending") for c in all_cases]
    status_counts = pd.Series(statuses).value_counts().to_dict()

    active_hearings = status_counts.get("In Hearing", 0) + status_counts.get("Scheduled", 0)
    postponed = status_counts.get("Adjourned / Postponed", 0)
    resolved = status_counts.get("Resolved", 0) + status_counts.get("Closed", 0)
    awaiting_ev = status_counts.get("Awaiting Evidence", 0)
    pending_review = status_counts.get("Pending Review", 0) + status_counts.get("Pending", 0)
    judgment_reserved = status_counts.get("Judgment Reserved", 0)

    emergency_cases = [c for c in all_cases if c.get("humanitarian_flag") or c.get("is_bail_matter") or c.get("is_child_protection") or c.get("is_medical_emergency") or c.get("is_domestic_violence")]
    emergency_count = len(emergency_cases)

    priorities = [c.get("priority_level", "Low") for c in all_cases]
    pri_counts = pd.Series(priorities).value_counts().to_dict()

    # ══════════════════════════════════════════════════════════
    # SECTION 1: Global KPI Metrics
    # ══════════════════════════════════════════════════════════
    st.markdown("### 🌐 Global Case Statistics")
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    def _kpi(col, label, val, color, icon):
        col.markdown(f"""
        <div style='background: #0f172a; padding: 18px 12px; border-radius: 10px; border: 1px solid #1e293b; border-top: 3px solid {color}; text-align: center;'>
            <span style='font-size: 28px;'>{icon}</span>
            <h2 style='margin: 4px 0 0; color: {color}; font-size: 28px;'>{val}</h2>
            <span style='color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;'>{label}</span>
        </div>""", unsafe_allow_html=True)

    _kpi(k1, "Total Cases", total, "#3b82f6", "📁")
    _kpi(k2, "Active Hearings", active_hearings, "#10b981", "🏛️")
    _kpi(k3, "Postponed", postponed, "#f59e0b", "⏸️")
    _kpi(k4, "Resolved", resolved, "#22c55e", "✅")
    _kpi(k5, "Emergency", emergency_count, "#ef4444", "🚨")
    _kpi(k6, "Evidence Pending", awaiting_ev, "#a855f7", "📂")

    st.divider()

    # ══════════════════════════════════════════════════════════
    # SECTION 2 & 5: Workflow Status + Priority Distribution
    # ══════════════════════════════════════════════════════════
    st.markdown("### 📈 Workflow & Priority Analytics")
    wa1, wa2 = st.columns(2)

    with wa1:
        st.markdown("#### ⚙️ Workflow Status Distribution")
        workflow_labels = ["Pending Review", "Scheduled", "In Hearing", "Awaiting Evidence", "Under Investigation", "Adjourned / Postponed", "Judgment Reserved", "Resolved", "Closed"]
        wf_data = []
        for lbl in workflow_labels:
            cnt = status_counts.get(lbl, 0)
            if lbl == "Pending Review":
                cnt += status_counts.get("Pending", 0)
            if cnt > 0:
                wf_data.append({"Status": lbl, "Count": cnt})
        if wf_data:
            df_wf = pd.DataFrame(wf_data)
            color_map = {"Pending Review": "#64748b", "Scheduled": "#3b82f6", "In Hearing": "#10b981", "Awaiting Evidence": "#a855f7", "Under Investigation": "#6366f1", "Adjourned / Postponed": "#f59e0b", "Judgment Reserved": "#f97316", "Resolved": "#22c55e", "Closed": "#6b7280"}
            fig_wf = px.bar(df_wf, x="Status", y="Count", color="Status", color_discrete_map=color_map)
            fig_wf.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#94a3b8", showlegend=False, margin=dict(t=10, b=30, l=30, r=10), xaxis=dict(tickangle=-35))
            st.plotly_chart(fig_wf, use_container_width=True)
        else:
            st.info("No workflow data.")

    with wa2:
        st.markdown("#### 🎯 Priority Level Distribution")
        pri_data = [{"Priority": p, "Count": pri_counts.get(p, 0)} for p in ["Critical", "High", "Medium", "Low"] if pri_counts.get(p, 0) > 0]
        if pri_data:
            df_pri = pd.DataFrame(pri_data)
            fig_pri = px.pie(df_pri, values="Count", names="Priority", hole=0.45, color="Priority", color_discrete_map={"Critical": "#dc2626", "High": "#ea580c", "Medium": "#f59e0b", "Low": "#10b981"})
            fig_pri.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#94a3b8", margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig_pri, use_container_width=True)
        else:
            st.info("No priority data.")

    st.divider()

    # ══════════════════════════════════════════════════════════
    # SECTION 3: Scheduling Analytics
    # ══════════════════════════════════════════════════════════
    st.markdown("### 📅 Scheduling Analytics")
    sc1, sc2, sc3, sc4 = st.columns(4)

    morning = [h for h in slots_hearings if "Morning" in h.get("hearing_time", "")]
    afternoon = [h for h in slots_hearings if "Afternoon" in h.get("hearing_time", "")]
    scheduled_queue = [c for c in queue_cases if c.get("hearing_date")]
    unscheduled_queue = [c for c in queue_cases if not c.get("hearing_date")]

    _kpi(sc1, f"Hearings Today ({sim_date_str})", len(slots_hearings), "#3b82f6", "📋")
    _kpi(sc2, "Morning Slot", len(morning), "#f59e0b", "🌅")
    _kpi(sc3, "Afternoon Slot", len(afternoon), "#6366f1", "🌇")
    _kpi(sc4, "Awaiting Scheduling", len(unscheduled_queue), "#ef4444", "⏳")

    if slots_hearings:
        st.markdown("##### 🏛️ Today's Cause List Summary")
        for h in slots_hearings:
            ready_icon = "✅" if h.get("is_ready") else "⚠️"
            st.markdown(f"""
            <div style='background: #1e293b; padding: 10px 15px; border-radius: 6px; border-left: 4px solid #3b82f6; margin-bottom: 6px; font-size: 13px; color: #e2e8f0;'>
                {ready_icon} <b>{h['title']}</b> — {h.get('hearing_time','N/A')} | {h.get('court_room','N/A')} | {h.get('judge_name','N/A')} | Status: <i>{h.get('status','N/A')}</i>
            </div>""", unsafe_allow_html=True)

    st.divider()

    # ══════════════════════════════════════════════════════════
    # SECTION 4: Postponement Analytics
    # ══════════════════════════════════════════════════════════
    st.markdown("### ⏸️ Postponement & Adjournment Analytics")
    pp1, pp2 = st.columns(2)

    total_adjournments = sum(c.get("adjournment_count", 0) or 0 for c in all_cases)
    frequent_adj = [c for c in all_cases if (c.get("adjournment_count") or 0) >= 3]

    with pp1:
        adj_k1, adj_k2 = st.columns(2)
        _kpi(adj_k1, "Total Adjournments", total_adjournments, "#f59e0b", "🔄")
        _kpi(adj_k2, "Frequently Postponed (≥3)", len(frequent_adj), "#ef4444", "⚠️")

        # Adjournment reasons from queue data
        reasons = [c.get("postponement_reason") for c in queue_cases if c.get("postponement_reason")]
        if reasons:
            st.markdown("##### 📝 Adjournment Reasons")
            reason_counts = pd.Series(reasons).value_counts().reset_index()
            reason_counts.columns = ["Reason", "Count"]
            fig_r = px.bar(reason_counts, x="Reason", y="Count", color_discrete_sequence=["#f59e0b"])
            fig_r.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#94a3b8", showlegend=False, margin=dict(t=10, b=30, l=30, r=10))
            st.plotly_chart(fig_r, use_container_width=True)

    with pp2:
        if frequent_adj:
            st.markdown("##### 🔴 Long-Pending Postponed Cases")
            for c in frequent_adj[:5]:
                st.markdown(f"""
                <div style='background: #1e293b; padding: 10px 15px; border-radius: 6px; border-left: 4px solid #ef4444; margin-bottom: 6px; font-size: 13px; color: #e2e8f0;'>
                    <b>{c.get('title','Untitled')}</b> — Adjourned <b>{c.get('adjournment_count',0)}x</b> | Age: {c.get('case_age_days',0)} days | Priority: {c.get('priority_level','Low')}
                </div>""", unsafe_allow_html=True)
        else:
            st.success("No frequently postponed cases detected.")

    st.divider()

    # ══════════════════════════════════════════════════════════
    # SECTION 6: Humanitarian Analytics
    # ══════════════════════════════════════════════════════════
    st.markdown("### 🏥 Humanitarian & Emergency Analytics")
    hm1, hm2 = st.columns(2)

    bail_cases = [c for c in all_cases if c.get("is_bail_matter")]
    child_cases = [c for c in all_cases if c.get("is_child_protection")]
    med_cases = [c for c in all_cases if c.get("is_medical_emergency")]
    dv_cases = [c for c in all_cases if c.get("is_domestic_violence")]
    hum_flagged = [c for c in all_cases if c.get("humanitarian_flag")]

    with hm1:
        hk1, hk2, hk3, hk4 = st.columns(4)
        _kpi(hk1, "Bail Matters", len(bail_cases), "#ef4444", "⚖️")
        _kpi(hk2, "Child Protection", len(child_cases), "#a855f7", "👶")
        _kpi(hk3, "Medical Emergency", len(med_cases), "#f97316", "🏥")
        _kpi(hk4, "Domestic Violence", len(dv_cases), "#ec4899", "🛡️")

    with hm2:
        hum_data = [
            {"Category": "Bail Matters", "Count": len(bail_cases)},
            {"Category": "Child Protection", "Count": len(child_cases)},
            {"Category": "Medical Emergency", "Count": len(med_cases)},
            {"Category": "Domestic Violence", "Count": len(dv_cases)},
            {"Category": "Humanitarian Flag", "Count": len(hum_flagged)},
        ]
        hum_data = [h for h in hum_data if h["Count"] > 0]
        if hum_data:
            df_hum = pd.DataFrame(hum_data)
            fig_hum = px.bar(df_hum, x="Category", y="Count", color="Category", color_discrete_sequence=["#ef4444", "#a855f7", "#f97316", "#ec4899", "#f59e0b"])
            fig_hum.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#94a3b8", showlegend=False, margin=dict(t=10, b=30, l=30, r=10))
            st.plotly_chart(fig_hum, use_container_width=True)
        else:
            st.info("No humanitarian/emergency flags currently set.")

    st.divider()

    # ══════════════════════════════════════════════════════════
    # SECTION 7 & 8: Resolution + Evidence Tracking
    # ══════════════════════════════════════════════════════════
    st.markdown("### 📊 Resolution & Evidence Tracking")
    re1, re2 = st.columns(2)

    with re1:
        st.markdown("#### ✅ Resolution Analytics")
        resolved_cases = [c for c in all_cases if c.get("status") in ["Resolved", "Closed"]]
        ages_resolved = [c.get("case_age_days", 0) or 0 for c in resolved_cases]
        avg_resolution = np.mean(ages_resolved) if ages_resolved else 0
        fast_tracked = [c for c in resolved_cases if c.get("humanitarian_flag") or c.get("is_bail_matter") or c.get("is_medical_emergency")]

        rk1, rk2, rk3 = st.columns(3)
        _kpi(rk1, "Resolved", len(resolved_cases), "#22c55e", "✅")
        _kpi(rk2, "Avg Resolution (days)", f"{avg_resolution:.0f}", "#3b82f6", "⏱️")
        _kpi(rk3, "Fast-Tracked", len(fast_tracked), "#f59e0b", "⚡")

        if resolved_cases:
            st.markdown("##### Recently Resolved")
            for rc in resolved_cases[:4]:
                st.markdown(f"""
                <div style='background: #0f2918; padding: 8px 12px; border-radius: 6px; border-left: 4px solid #22c55e; margin-bottom: 5px; font-size: 12px; color: #bbf7d0;'>
                    ✅ <b>{rc.get('title','Untitled')}</b> — Age: {rc.get('case_age_days',0)} days | Type: {rc.get('case_type','N/A')}
                </div>""", unsafe_allow_html=True)

    with re2:
        st.markdown("#### 📂 Evidence & Investigation Tracking")
        missing_ev = [c for c in queue_cases if not c.get("evidence_uploaded")]
        inv_pending = [c for c in queue_cases if not c.get("investigation_completed")]
        doc_unverified = [c for c in queue_cases if not c.get("documents_verified")]

        ek1, ek2, ek3 = st.columns(3)
        _kpi(ek1, "Missing Evidence", len(missing_ev), "#ef4444", "📄")
        _kpi(ek2, "Investigation Pending", len(inv_pending), "#a855f7", "🔍")
        _kpi(ek3, "Docs Unverified", len(doc_unverified), "#f59e0b", "📋")

        # Readiness gauge
        if queue_cases:
            ready_count = len([c for c in queue_cases if c.get("evidence_uploaded") and c.get("documents_verified") and c.get("parties_notified") and c.get("investigation_completed")])
            pct = (ready_count / len(queue_cases)) * 100 if queue_cases else 0
            fig_gauge = go.Figure(go.Indicator(mode="gauge+number", value=pct, title={"text": "Queue Readiness %", "font": {"color": "#94a3b8", "size": 14}}, number={"suffix": "%", "font": {"color": "#e2e8f0"}}, gauge={"axis": {"range": [0, 100], "tickcolor": "#475569"}, "bar": {"color": "#3b82f6"}, "bgcolor": "#1e293b", "bordercolor": "#334155", "steps": [{"range": [0, 40], "color": "#7f1d1d"}, {"range": [40, 70], "color": "#78350f"}, {"range": [70, 100], "color": "#064e3b"}]}))
            fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#94a3b8", height=250, margin=dict(t=40, b=10, l=30, r=30))
            st.plotly_chart(fig_gauge, use_container_width=True)

    st.divider()

    # ══════════════════════════════════════════════════════════
    # SECTION 9 & 10: AI Alerts + Queue Intelligence
    # ══════════════════════════════════════════════════════════
    st.markdown("### 🤖 AI Operational Alerts & Queue Intelligence")
    al1, al2 = st.columns(2)

    with al1:
        st.markdown("#### 🔔 Operational Alerts")
        alerts = []
        # Deadline risks
        for c in queue_cases:
            if c.get("status") == "Awaiting Evidence" and c.get("evidence_deadline"):
                try:
                    dd = datetime.strptime(c["evidence_deadline"], "%Y-%m-%d").date()
                    if dd <= sim_date:
                        alerts.append(("🔴", f"EVIDENCE OVERDUE for <b>{c['title']}</b> (deadline: {c['evidence_deadline']})"))
                    elif (dd - sim_date).days <= 3:
                        alerts.append(("🟡", f"Evidence due in {(dd - sim_date).days} days for <b>{c['title']}</b>"))
                except: pass
        # Emergency escalations
        for c in queue_cases:
            if c.get("is_emergency") and not c.get("hearing_date"):
                alerts.append(("🔴", f"EMERGENCY UNSCHEDULED: <b>{c['title']}</b> — requires immediate slot assignment"))
        # Frequent adjournments
        for c in all_cases:
            if (c.get("adjournment_count") or 0) >= 3:
                alerts.append(("🟠", f"FREQUENT ADJOURNMENTS ({c.get('adjournment_count')}x): <b>{c.get('title','Untitled')}</b>"))

        if alerts:
            for icon, text in alerts[:8]:
                bg = "rgba(239,68,68,0.12)" if icon == "🔴" else "rgba(245,158,11,0.12)" if icon in ("🟡", "🟠") else "rgba(59,130,246,0.12)"
                bd = "#ef4444" if icon == "🔴" else "#f59e0b" if icon in ("🟡", "🟠") else "#3b82f6"
                st.markdown(f"""<div style='background:{bg}; border-left:4px solid {bd}; border-radius:6px; padding:10px 14px; margin-bottom:6px; font-size:12px; color:#e2e8f0;'>{icon} {text}</div>""", unsafe_allow_html=True)
        else:
            st.success("✅ No active alerts. All systems nominal.")

    with al2:
        st.markdown("#### 📋 Queue Intelligence")
        emergency_overrides = [c for c in queue_cases if c.get("is_emergency")]
        auto_promoted = [c for c in queue_cases if c.get("status") == "Scheduled" and c.get("hearing_date")]

        qi1, qi2 = st.columns(2)
        _kpi(qi1, "Emergency Overrides", len(emergency_overrides), "#ef4444", "🚨")
        _kpi(qi2, "Scheduled (Auto-Promoted)", len(auto_promoted), "#10b981", "📅")

        # Backlog age distribution
        st.markdown("##### 📊 Backlog Age Distribution")
        ages = [c.get("case_age_days", 0) or 0 for c in all_cases]
        if ages and max(ages) > 0:
            bins = ["<1 yr", "1-3 yrs", "3-5 yrs", "5-10 yrs", "10-15 yrs", "15+ yrs"]
            vals = [
                len([a for a in ages if a < 365]),
                len([a for a in ages if 365 <= a < 365*3]),
                len([a for a in ages if 365*3 <= a < 365*5]),
                len([a for a in ages if 365*5 <= a < 365*10]),
                len([a for a in ages if 365*10 <= a < 365*15]),
                len([a for a in ages if a >= 365*15]),
            ]
            df_age = pd.DataFrame({"Age Bracket": bins, "Cases": vals})
            df_age = df_age[df_age["Cases"] > 0]
            fig_age = px.bar(df_age, x="Age Bracket", y="Cases", color_discrete_sequence=["#3b82f6"])
            fig_age.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#94a3b8", showlegend=False, margin=dict(t=10, b=30, l=30, r=10))
            st.plotly_chart(fig_age, use_container_width=True)
