"""Tasks page — sections, milestones, tasks management."""

import streamlit as st
from datetime import datetime

import db
import progress as prog
from pages.helpers import (
    STATUSES, build_user_progress, nav_to, parse_deadline,
)

_STATUS_INDICATORS = {
    "complete":    ("&#10003;", "#22c55e"),   # checkmark
    "in_progress": ("&#9679;",  "#f59e0b"),   # filled circle (amber)
    "not_started": ("&#9675;",  "#d4d4d4"),   # empty circle (gray)
}

_STATUS_COLORS = {
    "complete":    "#22c55e",
    "in_progress": "#f59e0b",
    "not_started": "#9ca3af",
}


def page_tasks(conn, users, user_id: str):
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        st.error("User not found")
        return

    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("< Back"):
            nav_to("user", user_id=user_id)
            st.rerun()

    st.markdown(f"# {user['name']}'s Tasks")

    # Check for highlight params (from clicking a task link)
    params = st.query_params
    highlight_section = params.get("section_id")
    highlight_milestone = params.get("milestone_id")

    section_data, overall, _ = build_user_progress(conn, user_id)

    for idx, section in enumerate(section_data):
        expand_section = section["id"] == highlight_section
        _render_section(conn, section, idx, expand_section, highlight_milestone)

    st.markdown("")
    if st.button("+ Add Section", use_container_width=True):
        st.session_state["show_add_section"] = True
        st.rerun()

    if st.session_state.get("show_add_section"):
        _show_add_section_dialog(conn, user_id)

    # Task dialogs rendered at page level for stable widget positioning
    _handle_task_dialogs(conn, section_data)


@st.dialog("Add Section")
def _show_add_section_dialog(conn, user_id: str):
    with st.form("add_section_form", clear_on_submit=True):
        sec_title = st.text_input("Section title")
        sec_weight = st.number_input("Weight", min_value=0.1, value=1.0, step=0.1)
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Add Section", type="primary", use_container_width=True)
        with col2:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)
        if submitted and sec_title.strip():
            order = db.get_next_sort_order(conn, "sections", "user_id", user_id)
            db.create_section(conn, user_id, sec_title.strip(), sec_weight, order)
            st.session_state.pop("show_add_section", None)
            st.rerun()
        if cancelled:
            st.session_state.pop("show_add_section", None)
            st.rerun()


# ---------------------------------------------------------------------------
# Section -> Milestone -> Task rendering
# ---------------------------------------------------------------------------

def _render_section(conn, section, idx, force_expand=False, highlight_milestone=None):
    sec_color = prog.SECTION_COLORS[idx % len(prog.SECTION_COLORS)]
    sec_pct = section["progress"] * 100
    milestone_count = len(section["milestones"])
    task_count = sum(len(m["tasks"]) for m in section["milestones"])

    # Progress bar with stats overlaid on the right
    st.markdown(
        f'<div style="position:relative; height:16px; padding:0 4px; margin-bottom:-10px;">'
        f'<div style="position:absolute; left:4px; right:4px; top:50%; transform:translateY(-50%); background:#e5e5e5; border-radius:9999px; height:5px;">'
        f'<div style="background:{sec_color}; width:{sec_pct:.0f}%; height:100%; border-radius:9999px;"></div>'
        f'</div>'
        f'<span style="position:absolute; right:8px; top:50%; transform:translateY(-50%); font-size:11px; color:#737373; white-space:nowrap;">'
        f'{milestone_count} milestones &middot; {task_count} tasks</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    with st.expander(f"{section['title']}  —  {sec_pct:.0f}%", expanded=force_expand):
        with st.form(f"edit_sec_{section['id']}", border=False):
            c1, c2 = st.columns([5, 1.5])
            with c1:
                new_title = st.text_input("Title", value=section["title"], key=f"sec_t_{section['id']}")
            with c2:
                new_weight = st.number_input("Weight", min_value=0.1, value=float(section["weight"]), step=0.1, key=f"sec_w_{section['id']}")
            save = st.form_submit_button("Save", use_container_width=False)
            if save:
                db.update_section(conn, section["id"], title=new_title.strip(), weight=new_weight)
                st.rerun()

        with st.popover("Delete Section", use_container_width=False):
            st.warning("Delete this section and all its milestones/tasks?")
            if st.button("Confirm Delete", key=f"del_sec_{section['id']}", type="primary", use_container_width=True):
                db.delete_section(conn, section["id"])
                st.rerun()

        st.divider()

        for m in section["milestones"]:
            expand_ms = m["id"] == highlight_milestone
            _render_milestone(conn, m, sec_color, force_expand=expand_ms)

        if st.button("+ Add Milestone", key=f"add_ms_btn_{section['id']}"):
            st.session_state[f"show_add_ms_{section['id']}"] = True
            st.rerun()

        if st.session_state.get(f"show_add_ms_{section['id']}"):
            _show_add_milestone_dialog(conn, section)


@st.dialog("Add Milestone")
def _show_add_milestone_dialog(conn, section: dict):
    st.caption(f"Adding to **{section['title']}**")
    with st.form("add_milestone_form", clear_on_submit=True):
        ms_title = st.text_input("Milestone title")
        ms_desc = st.text_input("Description (optional)")
        ms_deadline = st.date_input("Deadline (optional)", value=None)
        ms_weight = st.number_input("Weight", min_value=0.1, value=1.0, step=0.1)
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Add Milestone", type="primary", use_container_width=True)
        with col2:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)
        if submitted and ms_title.strip():
            dl_str = datetime.combine(ms_deadline, datetime.min.time()).isoformat() if ms_deadline else None
            order = db.get_next_sort_order(conn, "milestones", "section_id", section["id"])
            db.create_milestone(
                conn, section["id"], ms_title.strip(),
                description=ms_desc.strip() or None,
                deadline=dl_str, weight=ms_weight, sort_order=order,
            )
            st.session_state.pop(f"show_add_ms_{section['id']}", None)
            st.rerun()
        if cancelled:
            st.session_state.pop(f"show_add_ms_{section['id']}", None)
            st.rerun()


def _render_milestone(conn, m, sec_color, force_expand=False):
    m_pct = m["progress"] * 100
    dl = parse_deadline(m["deadline"])
    deadline_str = dl.strftime("%b %d, %Y") if dl else ""
    status_color = _STATUS_COLORS[m["status"]]
    status_label = m["status"].replace("_", " ").title()

    due_html = f' &middot; Due {deadline_str}' if deadline_str else ''
    overdue_html = ' &middot; <span style="color:#ef4444; font-weight:600;">OVERDUE</span>' if m["is_overdue"] else ''
    st.markdown(
        f'<div style="display:flex; align-items:center; gap:8px; margin-left:4px; padding:1px 4px 0; margin-bottom:-10px;">'
        f'<div style="flex:0 0 120px; background:#e5e5e5; border-radius:9999px; height:4px;">'
        f'<div style="background:{sec_color}; width:{m_pct:.0f}%; height:100%; border-radius:9999px;"></div>'
        f'</div>'
        f'<span style="font-size:11px; color:#737373;">{m_pct:.0f}%</span>'
        f'<span style="display:inline-block; padding:1px 6px; border-radius:9999px; background:{status_color}22; color:{status_color}; font-size:10px; font-weight:600;">{status_label}</span>'
        f'<span style="font-size:11px; color:#6b7280;">{due_html}{overdue_html}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    with st.expander(m["title"], expanded=force_expand):
        with st.form(f"edit_ms_{m['id']}", border=False):
            r1c1, r1c2 = st.columns([3, 1.5])
            with r1c1:
                em_title = st.text_input("Title", value=m["title"], key=f"ms_t_{m['id']}")
            with r1c2:
                em_status = st.selectbox(
                    "Status", STATUSES,
                    index=STATUSES.index(m["status"]),
                    key=f"ms_s_{m['id']}",
                )

            r2c1, r2c2, r2c3 = st.columns([2, 1.5, 1])
            with r2c1:
                em_desc = st.text_input("Description", value=m["description"] or "", key=f"ms_d_{m['id']}")
            with r2c2:
                em_deadline = st.date_input("Deadline", value=dl.date() if dl else None, key=f"ms_dl_{m['id']}")
            with r2c3:
                em_weight = st.number_input("Weight", min_value=0.1, value=float(m["weight"]), step=0.1, key=f"ms_w_{m['id']}")

            em_notes = st.text_area("Notes", value=m["notes"] or "", height=68, key=f"ms_n_{m['id']}")

            fc1, fc2 = st.columns(2)
            with fc1:
                save = st.form_submit_button("Save", type="primary", use_container_width=True)
            with fc2:
                pass
            if save:
                dl_str = datetime.combine(em_deadline, datetime.min.time()).isoformat() if em_deadline else None
                db.update_milestone(
                    conn, m["id"],
                    title=em_title.strip(), description=em_desc.strip() or None,
                    deadline=dl_str, weight=em_weight, notes=em_notes.strip() or None,
                )
                if em_status != m["status"]:
                    db.update_milestone_status(conn, m["id"], em_status)
                st.rerun()

        with st.popover("Delete Milestone"):
            st.warning(f"Delete **{m['title']}** and all its tasks?")
            if st.button("Confirm Delete", key=f"del_ms_{m['id']}", type="primary", use_container_width=True):
                db.delete_milestone(conn, m["id"])
                st.rerun()

        st.divider()

        for t in m["tasks"]:
            _render_task(conn, t)

        if st.button("+ Add Task", key=f"add_task_btn_{m['id']}"):
            st.session_state["show_add_task"] = {"id": m["id"], "title": m["title"]}
            st.rerun()


def _render_task(conn, t):
    icon, icon_color = _STATUS_INDICATORS[t["status"]]
    tdl = parse_deadline(t["deadline"])
    due_html = f'<span style="font-size:11px; color:#9ca3af; margin-left:auto;">Due {tdl.strftime("%b %d, %Y")}</span>' if tdl else ''

    st.markdown(
        f'<div style="display:flex; align-items:center; gap:8px; padding:2px 0 0;">'
        f'<span style="color:{icon_color}; font-size:14px; font-weight:bold;">{icon}</span>'
        f'<span style="font-size:13px; font-weight:500; color:#374151; flex:1;">{t["title"]}</span>'
        f'{due_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    _, t_status_col, t_edit_col, t_del_col = st.columns([4, 1.5, 0.5, 0.5])
    with t_status_col:
        new_status = st.selectbox(
            "Status", STATUSES,
            index=STATUSES.index(t["status"]),
            key=f"task_{t['id']}",
            label_visibility="collapsed",
        )
        if new_status != t["status"]:
            db.update_task_status(conn, t["id"], new_status)
            st.rerun()
    with t_edit_col:
        if st.button("✎", key=f"edit_task_btn_{t['id']}", help="Edit task details"):
            st.session_state["edit_task_data"] = dict(t)
            st.rerun()
    with t_del_col:
        with st.popover("✕"):
            st.caption(f"Delete **{t['title']}**?")
            if st.button("Delete", key=f"del_task_{t['id']}", type="primary", use_container_width=True):
                db.delete_task(conn, t["id"])
                st.rerun()


# ---------------------------------------------------------------------------
# Task dialogs — rendered at page level for stable widget positioning
# ---------------------------------------------------------------------------

def _handle_task_dialogs(conn, section_data):
    add_task_ms = st.session_state.get("show_add_task")
    if add_task_ms:
        _show_add_task_dialog(conn, add_task_ms)

    edit_task_data = st.session_state.get("edit_task_data")
    if edit_task_data:
        _show_edit_task_dialog(conn, edit_task_data)


@st.dialog("Add Task")
def _show_add_task_dialog(conn, milestone: dict):
    st.caption(f"Adding to **{milestone['title']}**")
    with st.form("add_task_form", clear_on_submit=True):
        at_title = st.text_input("Task title")
        at_desc = st.text_input("Description (optional)")
        c1, c2 = st.columns(2)
        with c1:
            at_deadline = st.date_input("Deadline (optional)", value=None)
        with c2:
            at_weight = st.number_input("Weight", min_value=0.1, value=1.0, step=0.1)
        at_notes = st.text_area("Notes (optional)", height=68)

        bc1, bc2 = st.columns(2)
        with bc1:
            submitted = st.form_submit_button("Add Task", type="primary", use_container_width=True)
        with bc2:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

        if submitted and at_title.strip():
            dl_str = datetime.combine(at_deadline, datetime.min.time()).isoformat() if at_deadline else None
            order = db.get_next_sort_order(conn, "tasks", "milestone_id", milestone["id"])
            db.create_task(
                conn, milestone["id"], at_title.strip(),
                description=at_desc.strip() or None,
                deadline=dl_str, weight=at_weight,
                notes=at_notes.strip() or None,
                sort_order=order,
            )
            st.session_state.pop("show_add_task", None)
            st.rerun()
        if cancelled:
            st.session_state.pop("show_add_task", None)
            st.rerun()


@st.dialog("Edit Task")
def _show_edit_task_dialog(conn, task: dict):
    tdl = parse_deadline(task.get("deadline"))
    with st.form("edit_task_form"):
        et_title = st.text_input("Title", value=task["title"])
        et_desc = st.text_input("Description", value=task.get("description") or "")
        c1, c2 = st.columns(2)
        with c1:
            et_deadline = st.date_input("Deadline", value=tdl.date() if tdl else None)
        with c2:
            et_weight = st.number_input("Weight", min_value=0.1, value=float(task["weight"]), step=0.1)
        et_notes = st.text_area("Notes", value=task.get("notes") or "", height=68)

        bc1, bc2 = st.columns(2)
        with bc1:
            save = st.form_submit_button("Save", type="primary", use_container_width=True)
        with bc2:
            cancel = st.form_submit_button("Cancel", use_container_width=True)

        if save:
            dl_str = datetime.combine(et_deadline, datetime.min.time()).isoformat() if et_deadline else None
            db.update_task(
                conn, task["id"],
                title=et_title.strip(), description=et_desc.strip() or None,
                deadline=dl_str, weight=et_weight, notes=et_notes.strip() or None,
            )
            st.session_state.pop("edit_task_data", None)
            st.rerun()
        if cancel:
            st.session_state.pop("edit_task_data", None)
            st.rerun()
