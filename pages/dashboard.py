"""Dashboard page — overview cards for all users with progress bars."""

import streamlit as st

import db
import progress as prog
from pages.helpers import build_user_progress, nav_to


def page_dashboard(conn, users):
    st.title("Dashboard")
    st.caption("Track your fly-away journey")

    stats = db.get_stats(conn)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="stat-card"><div class="stat-value">{stats["total_tasks"]}</div><div class="stat-label">Total Tasks</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-card"><div class="stat-value">{stats["completed_tasks"]}</div><div class="stat-label">Completed</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-card"><div class="stat-value">{stats["due_this_week"]}</div><div class="stat-label">Due This Week</div></div>', unsafe_allow_html=True)
    with c4:
        color = "#ef4444" if stats["overdue"] > 0 else "#22c55e"
        st.markdown(f'<div class="stat-card"><div class="stat-value" style="color:{color}">{stats["overdue"]}</div><div class="stat-label">Overdue</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    cols = st.columns(min(len(users), 2))
    for i, user in enumerate(users):
        _, overall, status_label = build_user_progress(conn, user["id"])
        accent = prog.USER_ACCENT_COLORS[i % len(prog.USER_ACCENT_COLORS)]
        badge_label, badge_color = prog.STATUS_BADGES[status_label]
        pct = overall * 100

        with cols[i % len(cols)]:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, {accent['gradient_start']}, {accent['gradient_end']});
                border-radius: 16px; padding: 28px 24px; color: white; margin-bottom: 8px;
            ">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <span style="font-size:22px; font-weight:700;">{user['name']}</span>
                    <span class="status-badge" style="background:{badge_color};">{badge_label}</span>
                </div>
                <div style="background:rgba(255,255,255,0.25); border-radius:9999px; height:10px; margin-bottom:8px;">
                    <div style="background:white; width:{pct:.0f}%; height:100%; border-radius:9999px;"></div>
                </div>
                <div style="font-size:14px; opacity:0.9;">{pct:.0f}% complete</div>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"View {user['name']}'s progress", key=f"view_{user['id']}", use_container_width=True):
                nav_to("user", user_id=user["id"])
                st.rerun()
