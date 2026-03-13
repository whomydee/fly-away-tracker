"""University analysis page — ranked table with scores, colors, reasons."""

import streamlit as st

import db
from pages.helpers import (
    nav_to, weight_to_importance, importance_badge_html,
    SCORE_OPTIONS, score_to_label, score_label_to_value, score_badge_html,
    ALLOWED_IMAGE_TYPES, ALLOWED_PDF_TYPES,
    save_uploaded_attachment, save_link_attachment, render_attachment_buttons,
)


def _score_color(pct):
    if pct >= 75:
        return "#22c55e"
    if pct >= 50:
        return "#f59e0b"
    if pct >= 25:
        return "#f97316"
    return "#ef4444"


def _score_label(pct):
    if pct >= 75:
        return "Strong"
    if pct >= 50:
        return "Moderate"
    if pct >= 25:
        return "Weak"
    return "Poor"


def page_university_analysis(conn, users, user_id: str):
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        st.error("User not found")
        return

    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("< Back to Progress"):
            nav_to("user", user_id=user_id)
            st.rerun()

    st.markdown(f"# {user['name']}'s University Analysis")

    questions = db.get_rubric_questions(conn, user_id)

    # Add University button
    if st.button("+ Add University Analysis", type="primary"):
        st.session_state["show_add_analysis"] = True
        st.rerun()

    if st.session_state.get("show_add_analysis"):
        _show_add_analysis_dialog(conn, user_id, questions)

    uni_scores = db.get_university_scores(conn, user_id)

    if not uni_scores:
        st.info("No universities analyzed yet. Click **+ Add University Analysis** above to get started.")
        return

    # --- Header row ---
    h_rank, h_name, h_score, h_rating, h_pick, h_not, h_action = st.columns([0.5, 2, 0.8, 1, 2, 2, 1])
    with h_rank:
        st.markdown("**Rank**")
    with h_name:
        st.markdown("**University**")
    with h_score:
        st.markdown("**Score**")
    with h_rating:
        st.markdown("**Rating**")
    with h_pick:
        st.markdown("**Reason to Pick**")
    with h_not:
        st.markdown("**Reason Not to Pick**")
    with h_action:
        st.markdown("**Actions**")
    st.divider()

    # --- University rows ---
    for u in uni_scores:
        color = _score_color(u["pct"])
        label = _score_label(u["pct"])

        c_rank, c_name, c_score, c_rating, c_pick, c_not, c_action = st.columns([0.5, 2, 0.8, 1, 2, 2, 1])
        with c_rank:
            st.markdown(f"**#{u['rank']}**")
        with c_name:
            st.markdown(f"**{u['name']}**")
        with c_score:
            st.markdown(f"**{u['pct']:.0f}%**")
        with c_rating:
            st.markdown(
                f'<span style="display:inline-block; padding:2px 10px; border-radius:9999px; '
                f'background:{color}; color:white; font-size:12px; font-weight:600;">{label}</span>',
                unsafe_allow_html=True,
            )
        with c_pick:
            st.caption(u.get("reason_to_pick") or "--")
        with c_not:
            st.caption(u.get("reason_not_to_pick") or "--")
        with c_action:
            _render_details_button(conn, user_id, u, questions)


@st.dialog("Add University Analysis", width="large")
def _show_add_analysis_dialog(conn, user_id: str, questions: list[dict]):
    uni_name = st.text_input("University Name", placeholder="e.g. University of Toronto")

    st.markdown("#### Evaluate each criterion")
    answers = {}
    for q in questions:
        imp = weight_to_importance(q.get("weight", 1.0))
        st.markdown(
            f"**{q['question']}** &nbsp; {importance_badge_html(imp)}",
            unsafe_allow_html=True,
        )
        c_text, c_score = st.columns([3, 1])
        with c_text:
            text_ans = st.text_area(
                "Answer", placeholder="Describe how this university meets this criterion...",
                key=f"new_text_{q['id']}", height=80, label_visibility="collapsed",
            )
        with c_score:
            score_label = st.selectbox(
                "Score", SCORE_OPTIONS, index=1,
                key=f"new_score_{q['id']}",
            )
        q_images = None
        q_pdfs = None
        q_link = ""
        _, c_img, c_pdf, c_link = st.columns([3, 0.5, 0.5, 0.5])
        with c_img:
            with st.popover(":camera: Image"):
                q_images = st.file_uploader(
                    "Upload images", type=ALLOWED_IMAGE_TYPES,
                    accept_multiple_files=True, key=f"new_q_img_{q['id']}",
                )
        with c_pdf:
            with st.popover(":page_facing_up: PDF"):
                q_pdfs = st.file_uploader(
                    "Upload PDFs", type=ALLOWED_PDF_TYPES,
                    accept_multiple_files=True, key=f"new_q_pdf_{q['id']}",
                )
        with c_link:
            with st.popover(":link: Link"):
                q_link = st.text_input("URL", key=f"new_q_link_{q['id']}")

        answers[q["id"]] = {
            "text": text_ans, "score_label": score_label,
            "files": (q_images or []) + (q_pdfs or []),
            "link": q_link,
        }

    st.markdown("#### Summary")
    reason_pick = st.text_area("Reason to pick this university", placeholder="What makes this university a good choice?")
    reason_not = st.text_area("Reason NOT to pick this university", placeholder="Any concerns or drawbacks?")

    st.markdown("#### Attachments")
    _, ac1, ac2, ac3 = st.columns([3, 0.5, 0.5, 0.5])
    uni_images = None
    uni_pdfs = None
    uni_link = ""
    with ac1:
        with st.popover(":camera: Images"):
            uni_images = st.file_uploader(
                "Upload images", type=ALLOWED_IMAGE_TYPES,
                accept_multiple_files=True, key="new_uni_img",
            )
    with ac2:
        with st.popover(":page_facing_up: PDFs"):
            uni_pdfs = st.file_uploader(
                "Upload PDFs", type=ALLOWED_PDF_TYPES,
                accept_multiple_files=True, key="new_uni_pdf",
            )
    with ac3:
        with st.popover(":link: Link"):
            uni_link = st.text_input("URL", key="new_uni_link")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Analysis", type="primary", use_container_width=True):
            if not uni_name.strip():
                st.error("Please enter a university name.")
            else:
                name = uni_name.strip()
                too_large = []

                # Save evaluations + per-question attachments
                for q in questions:
                    a = answers[q["id"]]
                    score_val = score_label_to_value(a["score_label"])
                    eval_id = db.upsert_rubric_evaluation(
                        conn, q["id"], name, str(score_val),
                        text_answer=a["text"].strip() or None,
                    )
                    for f in a["files"]:
                        result = save_uploaded_attachment(conn, "rubric_evaluation", eval_id, f)
                        if result is None:
                            too_large.append(f.name)
                    link = (a.get("link") or "").strip()
                    if link:
                        save_link_attachment(conn, "rubric_evaluation", eval_id, link)

                # Save analysis + university-level attachments
                analysis_id = db.upsert_university_analysis(
                    conn, user_id, name,
                    reason_pick.strip() or None, reason_not.strip() or None,
                )
                for f in (uni_images or []) + (uni_pdfs or []):
                    result = save_uploaded_attachment(conn, "university_analysis", analysis_id, f)
                    if result is None:
                        too_large.append(f.name)
                link = (uni_link or "").strip()
                if link:
                    save_link_attachment(conn, "university_analysis", analysis_id, link)

                if too_large:
                    st.warning(f"Skipped oversized files: {', '.join(too_large)}")
                else:
                    st.session_state.pop("show_add_analysis", None)
                    st.rerun()
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.session_state.pop("show_add_analysis", None)
            st.rerun()


def _render_details_button(conn, user_id, uni, questions):
    """Render a Details button that opens a dialog for a university."""
    evals = {}
    for q in questions:
        for ev in db.get_rubric_evaluations(conn, q["id"]):
            if ev["university_name"] == uni["name"]:
                try:
                    score = int(ev["answer"])
                except (ValueError, TypeError):
                    score = 0
                evals[q["id"]] = {
                    "id": ev["id"],
                    "score": score,
                    "text_answer": ev.get("text_answer") or "",
                }

    # Get the analysis ID for university-level attachments
    analysis_row = db.get_university_analysis(conn, user_id, uni["name"])
    analysis_id = analysis_row["id"] if analysis_row else None

    @st.dialog(f"{uni['name']} — Details", width="large")
    def _details_dialog():
        color = _score_color(uni["pct"])
        label = _score_label(uni["pct"])
        st.markdown(
            f'**Rank #{uni["rank"]}** &nbsp; | &nbsp; '
            f'**Score: {uni["pct"]:.0f}%** &nbsp; | &nbsp; '
            f'<span style="display:inline-block; padding:2px 10px; border-radius:9999px; '
            f'background:{color}; color:white; font-size:12px; font-weight:600;">{label}</span>',
            unsafe_allow_html=True,
        )

        st.markdown("")
        st.markdown("#### Criteria Evaluation")

        with st.form(f"details_{uni['name']}"):
            edited = {}
            for q in questions:
                ev = evals.get(q["id"], {"id": None, "score": 5, "text_answer": ""})
                imp = weight_to_importance(q.get("weight", 1.0))
                current_label = score_to_label(ev["score"])

                st.markdown(
                    f"**{q['question']}** &nbsp; {importance_badge_html(imp)}",
                    unsafe_allow_html=True,
                )
                c_text, c_score = st.columns([3, 1])
                with c_text:
                    text_ans = st.text_area(
                        "Answer", value=ev["text_answer"],
                        key=f"detail_text_{uni['name']}_{q['id']}",
                        height=80, label_visibility="collapsed",
                    )
                with c_score:
                    score_label = st.selectbox(
                        "Score", SCORE_OPTIONS,
                        index=SCORE_OPTIONS.index(current_label),
                        key=f"detail_score_{uni['name']}_{q['id']}",
                    )
                edited[q["id"]] = {"text": text_ans, "score_label": score_label}

            st.markdown("#### Summary")
            new_reason_pick = st.text_area(
                "Reason to pick",
                value=uni.get("reason_to_pick") or "",
            )
            new_reason_not = st.text_area(
                "Reason not to pick",
                value=uni.get("reason_not_to_pick") or "",
            )

            col_save, col_del = st.columns(2)
            with col_save:
                save = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
            with col_del:
                remove = st.form_submit_button("Remove University", use_container_width=True)

            if save:
                for q in questions:
                    a = edited[q["id"]]
                    score_val = score_label_to_value(a["score_label"])
                    db.upsert_rubric_evaluation(
                        conn, q["id"], uni["name"], str(score_val),
                        text_answer=a["text"].strip() or None,
                    )
                db.upsert_university_analysis(
                    conn, user_id, uni["name"],
                    new_reason_pick.strip() or None,
                    new_reason_not.strip() or None,
                )
                st.rerun()

            if remove:
                db.delete_university_analysis(conn, user_id, uni["name"])
                st.rerun()

        # --- Attachments section (outside form so file_uploader works) ---
        st.divider()
        st.markdown("#### Attachments")

        if analysis_id:
            st.caption("University-level")
            render_attachment_buttons(conn, "university_analysis", analysis_id, f"det_uni_{uni['name']}")

        for q in questions:
            ev = evals.get(q["id"])
            if not ev or not ev["id"]:
                continue
            st.caption(f"{q['question'][:60]}")
            render_attachment_buttons(conn, "rubric_evaluation", ev["id"], f"det_q_{uni['name']}_{q['id']}")

    if st.button("Details", key=f"btn_details_{uni['name']}"):
        _details_dialog()
