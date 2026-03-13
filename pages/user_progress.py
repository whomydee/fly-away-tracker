"""User progress page — overview hub with journey bar, burn-up chart, and navigation cards."""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, date, timedelta

import db
import progress as prog
from pages.helpers import (
    build_user_progress, nav_to, parse_deadline, render_donut,
)


def page_user_progress(conn, users, user_id: str):
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        st.error("User not found")
        return

    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("< Dashboard"):
            nav_to("dashboard")
            st.rerun()

    section_data, overall, status_label = build_user_progress(conn, user_id)
    badge_label, badge_color = prog.STATUS_BADGES[status_label]

    st.markdown(f"# {user['name']}'s Progress")
    st.markdown(f'<span class="status-badge" style="background:{badge_color};">{badge_label}</span>', unsafe_allow_html=True)

    left, mid, right = st.columns([1, 1, 3])
    with left:
        fig = render_donut(overall, prog.get_progress_color(overall))
        st.plotly_chart(fig, use_container_width=False, config={"displayModeBar": False})
    with mid:
        st.metric("Overall Progress", f"{overall * 100:.0f}%")
        st.metric("Sections", len(section_data))
        total_milestones = sum(len(s["milestones"]) for s in section_data)
        st.metric("Milestones", total_milestones)
    with right:
        _render_upcoming_tasks(conn, user_id)

    # Record today's snapshot
    total_tasks = sum(len(m["tasks"]) for s in section_data for m in s["milestones"])
    complete_tasks = sum(
        1 for s in section_data for m in s["milestones"] for t in m["tasks"] if t["status"] == "complete"
    )
    db.record_snapshot(conn, user_id, overall, complete_tasks, total_tasks)

    # Navigation cards
    _render_nav_cards(conn, user_id, section_data)

    # Journey bar + burn-up chart
    _render_journey_bar(user, overall)
    _render_burnup_chart(conn, user, overall)


# ---------------------------------------------------------------------------
# Navigation cards — links to Tasks and University Analysis pages
# ---------------------------------------------------------------------------

def _render_nav_cards(conn, user_id, section_data):
    total_tasks = sum(len(m["tasks"]) for s in section_data for m in s["milestones"])
    complete_tasks = sum(
        1 for s in section_data for m in s["milestones"] for t in m["tasks"] if t["status"] == "complete"
    )
    in_progress_tasks = sum(
        1 for s in section_data for m in s["milestones"] for t in m["tasks"] if t["status"] == "in_progress"
    )

    rubric_qs = db.get_rubric_questions(conn, user_id)
    has_rubric = bool(rubric_qs)

    cols = st.columns(2 if has_rubric else 1)

    # Tasks card
    with cols[0]:
        st.markdown(
            f'<div style="background:linear-gradient(135deg, #4f46e5, #7c3aed); border-radius:16px; padding:24px; color:white; margin-bottom:12px;">'
            f'<div style="font-size:20px; font-weight:700; margin-bottom:6px;">Sections & Tasks</div>'
            f'<div style="font-size:13px; opacity:0.85; margin-bottom:16px;">'
            f'Manage your sections, milestones, and tasks</div>'
            f'<div style="display:flex; gap:24px;">'
            f'<div><div style="font-size:22px; font-weight:700;">{len(section_data)}</div>'
            f'<div style="font-size:11px; opacity:0.7;">Sections</div></div>'
            f'<div><div style="font-size:22px; font-weight:700;">{complete_tasks}/{total_tasks}</div>'
            f'<div style="font-size:11px; opacity:0.7;">Tasks Done</div></div>'
            f'<div><div style="font-size:22px; font-weight:700;">{in_progress_tasks}</div>'
            f'<div style="font-size:11px; opacity:0.7;">In Progress</div></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Open Tasks", use_container_width=True, type="primary", key="nav_tasks"):
            nav_to("tasks", user_id=user_id)
            st.rerun()

    # University Analysis card (only if user has rubric data)
    if has_rubric:
        uni_scores = db.get_university_scores(conn, user_id)
        uni_count = len(uni_scores)
        top_uni = uni_scores[0]["name"] if uni_scores else "None yet"
        top_score = f"{uni_scores[0]['pct']:.0f}%" if uni_scores else "--"

        with cols[1]:
            st.markdown(
                f'<div style="background:linear-gradient(135deg, #1e3a5f, #2d6a9f); border-radius:16px; padding:24px; color:white; margin-bottom:12px;">'
                f'<div style="font-size:20px; font-weight:700; margin-bottom:6px;">University Analysis</div>'
                f'<div style="font-size:13px; opacity:0.85; margin-bottom:16px;">'
                f'Evaluate and compare universities using your rubric</div>'
                f'<div style="display:flex; gap:24px;">'
                f'<div><div style="font-size:22px; font-weight:700;">{uni_count}</div>'
                f'<div style="font-size:11px; opacity:0.7;">Universities</div></div>'
                f'<div><div style="font-size:22px; font-weight:700;">{top_score}</div>'
                f'<div style="font-size:11px; opacity:0.7;">Top ({top_uni})</div></div>'
                f'<div><div style="font-size:22px; font-weight:700;">{len(rubric_qs)}</div>'
                f'<div style="font-size:11px; opacity:0.7;">Criteria</div></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            if st.button("View Analysis", use_container_width=True, type="primary", key="nav_analysis"):
                nav_to("analysis", user_id=user_id)
                st.rerun()
            if st.button("Manage Rubric", use_container_width=True, key="nav_rubric"):
                nav_to("rubric_manage", user_id=user_id)
                st.rerun()


# ---------------------------------------------------------------------------
# Upcoming tasks table
# ---------------------------------------------------------------------------

_PRIORITY_COLORS = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#3b82f6"}
_STATUS_LABELS = {"not_started": "Not Started", "in_progress": "In Progress", "complete": "Complete"}


def _weight_to_priority(w: float) -> str:
    if w >= 2.0:
        return "High"
    if w >= 1.5:
        return "Medium"
    return "Low"


def _render_upcoming_tasks(conn, user_id: str):
    all_tasks = db.get_user_tasks(conn, user_id)
    tasks = [t for t in all_tasks if t["status"] != "complete"]

    st.markdown(
        '<div style="font-size:14px; font-weight:700; margin-bottom:4px;">Upcoming Tasks</div>',
        unsafe_allow_html=True,
    )

    if not tasks:
        st.caption("All tasks complete!")
        return

    # Sort: tasks with deadlines first (by date), then by priority
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    sorted_tasks = sorted(tasks, key=lambda t: (
        t["deadline"] if t["deadline"] else "9999-12-31",
        priority_order.get(_weight_to_priority(t["weight"]), 2),
    ))

    # Pagination
    page_size = 5
    total_pages = max(1, (len(sorted_tasks) + page_size - 1) // page_size)
    page_key = "upcoming_tasks_page"
    current_page = st.session_state.get(page_key, 0)
    current_page = min(current_page, total_pages - 1)

    start = current_page * page_size
    page_tasks = sorted_tasks[start:start + page_size]

    # Build HTML table with clickable task names
    _STATUS_COLORS_TABLE = {"Not Started": "#9ca3af", "In Progress": "#f59e0b", "Complete": "#22c55e"}

    header = (
        '<table style="width:100%; border-collapse:collapse; font-size:13px;">'
        '<thead><tr style="border-bottom:2px solid #e5e7eb;">'
        '<th style="text-align:left; padding:6px 8px; color:#6b7280;">Task</th>'
        '<th style="text-align:left; padding:6px 8px; color:#6b7280;">Status</th>'
        '<th style="text-align:left; padding:6px 8px; color:#6b7280;">Deadline</th>'
        '<th style="text-align:left; padding:6px 8px; color:#6b7280;">Priority</th>'
        '<th style="text-align:left; padding:6px 8px; color:#6b7280;">Section</th>'
        '<th style="text-align:left; padding:6px 8px; color:#6b7280;">Milestone</th>'
        '</tr></thead><tbody>'
    )

    rows_html = ""
    for t in page_tasks:
        dl = parse_deadline(t["deadline"])
        priority = _weight_to_priority(t["weight"])
        pri_color = _PRIORITY_COLORS.get(priority, "#6b7280")
        status_label = _STATUS_LABELS.get(t["status"], t["status"])
        status_color = _STATUS_COLORS_TABLE.get(status_label, "#9ca3af")
        dl_str = dl.strftime("%Y-%m-%d") if dl else ""
        link = f"?page=tasks&user_id={user_id}&section_id={t['section_id']}&milestone_id={t['milestone_id']}"

        rows_html += (
            f'<tr style="border-bottom:1px solid #f3f4f6;">'
            f'<td style="padding:8px;"><a href="{link}" target="_self" '
            f'style="color:#4f46e5; text-decoration:none; font-weight:500;">{t["title"]}</a></td>'
            f'<td style="padding:8px; color:{status_color}; font-weight:600;">{status_label}</td>'
            f'<td style="padding:8px; color:#374151;">{dl_str}</td>'
            f'<td style="padding:8px; color:{pri_color}; font-weight:600;">{priority}</td>'
            f'<td style="padding:8px; color:#374151;">{t["section_title"]}</td>'
            f'<td style="padding:8px; color:#374151;">{t["milestone_title"]}</td>'
            f'</tr>'
        )

    st.markdown(header + rows_html + '</tbody></table>', unsafe_allow_html=True)

    if total_pages > 1:
        pc1, pc2, pc3 = st.columns([1, 2, 1])
        with pc1:
            if st.button("< Prev", key="tasks_prev", disabled=current_page == 0, use_container_width=True):
                st.session_state[page_key] = current_page - 1
                st.rerun()
        with pc2:
            st.markdown(
                f'<div style="text-align:center; font-size:12px; color:#737373; padding-top:6px;">'
                f'Page {current_page + 1} of {total_pages}</div>',
                unsafe_allow_html=True,
            )
        with pc3:
            if st.button("Next >", key="tasks_next", disabled=current_page >= total_pages - 1, use_container_width=True):
                st.session_state[page_key] = current_page + 1
                st.rerun()


# ---------------------------------------------------------------------------
# Journey bar
# ---------------------------------------------------------------------------

def _render_journey_bar(user: dict, overall: float):
    """Render the journey progress bar with start, current position, and goal."""
    start_str = user.get("start_date")
    target_str = user.get("target_date")

    if not start_str or not target_str:
        st.info("Set a start date and target date to see your journey progress.")
        with st.form("set_dates_form"):
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1:
                sd = st.date_input("Start date", value=date.today() - timedelta(days=30))
            with c2:
                td = st.date_input("Target date", value=date.today() + timedelta(days=90))
            with c3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("Set Dates", type="primary", use_container_width=True):
                    db.update_user_dates(
                        db.get_connection(), user["id"],
                        start_date=sd.isoformat(), target_date=td.isoformat(),
                    )
                    st.rerun()
        return

    start_date = date.fromisoformat(start_str)
    target_date = date.fromisoformat(target_str)
    today = date.today()

    total_days = max((target_date - start_date).days, 1)
    elapsed_days = (today - start_date).days
    remaining_days = max((target_date - today).days, 0)
    time_pct = min(max(elapsed_days / total_days * 100, 0), 100)
    prog_pct = overall * 100

    if prog_pct >= time_pct:
        marker_color = "#22c55e"
    elif prog_pct >= time_pct * 0.7:
        marker_color = "#f59e0b"
    else:
        marker_color = "#ef4444"

    st.markdown(
        f'<div style="background:#f8f9fa; border-radius:12px; padding:20px 24px; margin:8px 0 16px;">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">'
        f'<span style="font-size:15px; font-weight:700; color:#1f2937;">Your Journey</span>'
        f'<span style="font-size:12px; color:#6b7280;">{remaining_days} days remaining</span>'
        f'</div>'
        f'<div style="position:relative; height:28px; margin-bottom:8px;">'
        f'<div style="position:absolute; left:0; right:0; top:50%; transform:translateY(-50%); height:8px; background:#e5e7eb; border-radius:9999px;"></div>'
        f'<div style="position:absolute; left:0; top:50%; transform:translateY(-50%); height:8px; background:{marker_color}; border-radius:9999px; width:{prog_pct:.0f}%;"></div>'
        f'<div style="position:absolute; left:{time_pct:.0f}%; top:0; bottom:0; border-left:2px dashed #9ca3af; opacity:0.6;"></div>'
        f'<div style="position:absolute; left:{prog_pct:.0f}%; top:50%; transform:translate(-50%, -50%); width:20px; height:20px; background:{marker_color}; border-radius:50%; border:3px solid white; box-shadow:0 1px 4px rgba(0,0,0,0.2);"></div>'
        f'<div style="position:absolute; left:0; top:50%; transform:translate(-4px, -50%); font-size:14px;">🚀</div>'
        f'<div style="position:absolute; right:0; top:50%; transform:translate(4px, -50%); font-size:14px;">🏁</div>'
        f'</div>'
        f'<div style="display:flex; justify-content:space-between; align-items:center; font-size:12px; color:#6b7280;">'
        f'<span>{start_date.strftime("%b %d, %Y")}</span>'
        f'<span style="font-weight:600; color:{marker_color}; font-size:13px;">{prog_pct:.0f}% complete</span>'
        f'<span>{target_date.strftime("%b %d, %Y")}</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Burn-up chart
# ---------------------------------------------------------------------------

def _render_burnup_chart(conn, user: dict, overall: float):
    """Render a burn-up chart showing progress over time vs ideal pace."""
    start_str = user.get("start_date")
    target_str = user.get("target_date")
    if not start_str or not target_str:
        return

    snapshots = db.get_snapshots(conn, user["id"])
    if not snapshots:
        return

    start_date = date.fromisoformat(start_str)
    target_date = date.fromisoformat(target_str)

    snap_dates = [date.fromisoformat(s["date"]) for s in snapshots]
    snap_progress = [s["progress"] * 100 for s in snapshots]

    ideal_dates = [start_date, target_date]
    ideal_progress = [0, 100]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=ideal_dates, y=ideal_progress,
        mode="lines", name="Ideal Pace",
        line=dict(color="#d1d5db", width=2, dash="dash"),
    ))

    fig.add_trace(go.Scatter(
        x=snap_dates, y=snap_progress,
        mode="lines+markers", name="Actual Progress",
        line=dict(color="#6366f1", width=3),
        marker=dict(size=6, color="#6366f1"),
        fill="tozeroy", fillcolor="rgba(99,102,241,0.08)",
    ))

    today = date.today()
    today_str = today.isoformat()
    fig.add_shape(
        type="line", x0=today_str, x1=today_str, y0=0, y1=105,
        line=dict(color="#9ca3af", width=1, dash="dot"),
    )
    fig.add_annotation(
        x=today_str, y=105, text="Today", showarrow=False,
        font=dict(size=11, color="#9ca3af"), yanchor="bottom",
    )

    fig.update_layout(
        title=dict(text="Progress Over Time", font=dict(size=15)),
        xaxis=dict(
            title="", showgrid=False,
            range=[start_date - timedelta(days=2), target_date + timedelta(days=5)],
        ),
        yaxis=dict(
            title="Progress %", showgrid=True, gridcolor="#f3f4f6",
            range=[0, 105], ticksuffix="%",
        ),
        height=280,
        margin=dict(l=40, r=20, t=40, b=30),
        plot_bgcolor="white",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1, font=dict(size=11),
        ),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
