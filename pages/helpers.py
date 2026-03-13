"""Shared helpers used across pages."""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

import db
import progress as prog

STATUSES = ["not_started", "in_progress", "complete"]

# Attachment file type constraints
ALLOWED_IMAGE_TYPES = ["png", "jpg", "jpeg", "gif", "webp"]
ALLOWED_PDF_TYPES = ["pdf"]
MAX_IMAGE_SIZE_MB = 2
MAX_PDF_SIZE_MB = 100

# Importance levels for rubric question weights
IMPORTANCE_LEVELS = {
    "High":     {"weight": 2.0, "color": "#ef4444", "bg": "#fef2f2"},
    "Moderate": {"weight": 1.5, "color": "#f59e0b", "bg": "#fffbeb"},
    "Low":      {"weight": 1.0, "color": "#3b82f6", "bg": "#eff6ff"},
}

# Score levels for rubric evaluations (Good/Moderate/Bad → numeric)
SCORE_LEVELS = {
    "Good":     {"score": 8, "color": "#22c55e", "bg": "#f0fdf4"},
    "Moderate": {"score": 5, "color": "#f59e0b", "bg": "#fffbeb"},
    "Bad":      {"score": 2, "color": "#ef4444", "bg": "#fef2f2"},
}
SCORE_OPTIONS = list(SCORE_LEVELS.keys())


def score_to_label(score: int) -> str:
    if score >= 7:
        return "Good"
    if score >= 4:
        return "Moderate"
    return "Bad"


def score_label_to_value(label: str) -> int:
    return SCORE_LEVELS.get(label, SCORE_LEVELS["Moderate"])["score"]


def score_badge_html(label: str) -> str:
    info = SCORE_LEVELS.get(label, SCORE_LEVELS["Moderate"])
    return (
        f'<span style="display:inline-block; padding:2px 10px; border-radius:9999px; '
        f'background:{info["bg"]}; color:{info["color"]}; font-size:12px; font-weight:600; '
        f'border:1px solid {info["color"]};">{label}</span>'
    )

def weight_to_importance(weight: float) -> str:
    for label, info in IMPORTANCE_LEVELS.items():
        if abs(weight - info["weight"]) < 0.01:
            return label
    return "Moderate"

def importance_to_weight(label: str) -> float:
    return IMPORTANCE_LEVELS.get(label, IMPORTANCE_LEVELS["Moderate"])["weight"]

def importance_badge_html(label: str) -> str:
    info = IMPORTANCE_LEVELS.get(label, IMPORTANCE_LEVELS["Moderate"])
    return (
        f'<span style="display:inline-block; padding:2px 10px; border-radius:9999px; '
        f'background:{info["bg"]}; color:{info["color"]}; font-size:12px; font-weight:600; '
        f'border:1px solid {info["color"]};">Importance: {label}</span>'
    )


def get_conn():
    return db.get_connection()


def get_all_users(conn):
    return db.get_users(conn)


def nav_to(pg: str, **kwargs):
    st.session_state.pop("show_add_analysis", None)
    st.query_params.update(page=pg, **kwargs)


def parse_deadline(dl):
    """Parse a deadline value into a datetime or None."""
    if not dl:
        return None
    if isinstance(dl, str):
        try:
            return datetime.fromisoformat(dl)
        except ValueError:
            return None
    return dl


def build_user_progress(conn, user_id: str):
    sections = db.get_sections(conn, user_id)
    all_milestones = []
    section_data = []
    for s in sections:
        milestones = db.get_milestones(conn, s["id"])
        ms_data = []
        for m in milestones:
            tasks = db.get_tasks(conn, m["id"])
            m_progress = prog.calculate_task_progress(tasks)
            dl = parse_deadline(m["deadline"])
            is_overdue = dl is not None and dl < datetime.now() and m["status"] != "complete"
            ms_data.append({**m, "progress": m_progress, "is_overdue": is_overdue, "tasks": tasks})
            all_milestones.append(m)
        s_progress = prog.calculate_weighted_progress(ms_data)
        section_data.append({**s, "progress": s_progress, "milestones": ms_data})

    overall = prog.calculate_weighted_progress(section_data)
    status_label = prog.derive_status_label(all_milestones)
    return section_data, overall, status_label


def render_donut(value: float, color: str, size: int = 200):
    pct = value * 100
    fig = go.Figure(go.Pie(
        values=[pct, 100 - pct], hole=0.75,
        marker=dict(colors=[color, "#e5e5e5"]),
        textinfo="none", hoverinfo="skip", sort=False,
    ))
    fig.update_layout(
        showlegend=False, margin=dict(t=0, b=0, l=0, r=0),
        width=size, height=size,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        annotations=[dict(text=f"<b>{pct:.0f}%</b>", x=0.5, y=0.5, font_size=20, showarrow=False)],
    )
    return fig


def save_uploaded_attachment(conn, parent_type: str, parent_id: str, uploaded_file) -> str | None:
    """Save an uploaded file as an attachment. Returns attachment ID or None if rejected."""
    file_bytes = uploaded_file.getvalue()
    ext = uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else ""
    if ext in ALLOWED_IMAGE_TYPES:
        att_type = "image"
        max_mb = MAX_IMAGE_SIZE_MB
    elif ext in ALLOWED_PDF_TYPES:
        att_type = "pdf"
        max_mb = MAX_PDF_SIZE_MB
    else:
        return None
    if len(file_bytes) > max_mb * 1024 * 1024:
        return None
    stored_name = db.save_attachment_file(file_bytes, uploaded_file.name)
    order = db.get_next_sort_order(conn, "attachments", "parent_id", parent_id)
    return db.create_attachment(
        conn, parent_type, parent_id, att_type,
        file_name=uploaded_file.name, stored_name=stored_name,
        file_size=len(file_bytes), sort_order=order,
    )


def save_link_attachment(conn, parent_type: str, parent_id: str, url: str) -> str:
    """Save a link attachment."""
    order = db.get_next_sort_order(conn, "attachments", "parent_id", parent_id)
    return db.create_attachment(
        conn, parent_type, parent_id, "link", url=url, sort_order=order,
    )


def render_existing_attachments(conn, attachments: list[dict], key_prefix: str, allow_delete: bool = True):
    """Display existing attachments with optional delete buttons."""
    if not attachments:
        return
    for att in attachments:
        cols = st.columns([4, 1] if allow_delete else [1])
        with cols[0]:
            if att["attachment_type"] == "image":
                file_path = db.get_attachment_file_path(att["stored_name"])
                if file_path.exists():
                    st.image(str(file_path), caption=att["file_name"], width=300)
                else:
                    st.warning(f"Image file missing: {att['file_name']}")
            elif att["attachment_type"] == "pdf":
                file_path = db.get_attachment_file_path(att["stored_name"])
                if file_path.exists():
                    st.download_button(
                        f"Download: {att['file_name']}",
                        data=file_path.read_bytes(),
                        file_name=att["file_name"],
                        mime="application/pdf",
                        key=f"{key_prefix}_dl_{att['id']}",
                    )
                else:
                    st.warning(f"PDF file missing: {att['file_name']}")
            elif att["attachment_type"] == "link":
                st.markdown(f"[{att['url']}]({att['url']})")
        if allow_delete and len(cols) > 1:
            with cols[1]:
                if st.button("Remove", key=f"{key_prefix}_rm_{att['id']}"):
                    db.delete_attachment(conn, att["id"])
                    st.rerun()


def render_attachment_buttons(conn, parent_type: str, parent_id: str, key_prefix: str):
    """Render compact icon buttons for adding/viewing attachments via popovers."""
    attachments = db.get_attachments(conn, parent_type, parent_id)
    image_atts = [a for a in attachments if a["attachment_type"] == "image"]
    pdf_atts = [a for a in attachments if a["attachment_type"] == "pdf"]
    link_atts = [a for a in attachments if a["attachment_type"] == "link"]

    c_img, c_pdf, c_link = st.columns(3)
    with c_img:
        img_label = f"Images ({len(image_atts)})" if image_atts else "Images"
        with st.popover(img_label, use_container_width=True):
            render_existing_attachments(conn, image_atts, f"{key_prefix}_img")
            uploaded = st.file_uploader(
                f"Add images (max {MAX_IMAGE_SIZE_MB}MB each)",
                type=ALLOWED_IMAGE_TYPES, accept_multiple_files=True,
                key=f"{key_prefix}_add_img",
            )
            if uploaded and st.button("Save", key=f"{key_prefix}_save_img"):
                too_large = []
                for f in uploaded:
                    if save_uploaded_attachment(conn, parent_type, parent_id, f) is None:
                        too_large.append(f.name)
                if too_large:
                    st.warning(f"Skipped (>{MAX_IMAGE_SIZE_MB}MB): {', '.join(too_large)}")
                st.rerun()
    with c_pdf:
        pdf_label = f"PDFs ({len(pdf_atts)})" if pdf_atts else "PDFs"
        with st.popover(pdf_label, use_container_width=True):
            render_existing_attachments(conn, pdf_atts, f"{key_prefix}_pdf")
            uploaded = st.file_uploader(
                f"Add PDFs (max {MAX_PDF_SIZE_MB}MB each)",
                type=ALLOWED_PDF_TYPES, accept_multiple_files=True,
                key=f"{key_prefix}_add_pdf",
            )
            if uploaded and st.button("Save", key=f"{key_prefix}_save_pdf"):
                too_large = []
                for f in uploaded:
                    if save_uploaded_attachment(conn, parent_type, parent_id, f) is None:
                        too_large.append(f.name)
                if too_large:
                    st.warning(f"Skipped (>{MAX_PDF_SIZE_MB}MB): {', '.join(too_large)}")
                st.rerun()
    with c_link:
        link_label = f"Links ({len(link_atts)})" if link_atts else "Links"
        with st.popover(link_label, use_container_width=True):
            render_existing_attachments(conn, link_atts, f"{key_prefix}_link")
            new_link = st.text_input("Add link", key=f"{key_prefix}_add_link")
            if new_link and st.button("Save", key=f"{key_prefix}_save_link"):
                save_link_attachment(conn, parent_type, parent_id, new_link.strip())
                st.rerun()
