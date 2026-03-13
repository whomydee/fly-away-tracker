"""Rubric management page — view/edit/add rubric questions with weights."""

import streamlit as st

import db
from pages.helpers import (
    nav_to, IMPORTANCE_LEVELS, weight_to_importance,
    importance_to_weight, importance_badge_html,
)


def page_rubric_manage(conn, users, user_id: str):
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        st.error("User not found")
        return

    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("< Back to Progress"):
            nav_to("user", user_id=user_id)
            st.rerun()

    st.markdown(f"# {user['name']}'s Rubric Criteria")
    st.caption("Define the questions and importance levels used to evaluate universities")

    importance_options = list(IMPORTANCE_LEVELS.keys())
    questions = db.get_rubric_questions(conn, user_id)

    # --- Questions table ---
    if questions:
        # Header row
        h1, h2, h3, h4 = st.columns([0.5, 5, 1.5, 1.5])
        with h1:
            st.markdown("**#**")
        with h2:
            st.markdown("**Question**")
        with h3:
            st.markdown("**Importance**")
        with h4:
            st.markdown("**Actions**")
        st.divider()

        for i, q in enumerate(questions):
            c1, c2, c3, c4 = st.columns([0.5, 5, 1.5, 1.5])
            with c1:
                st.markdown(f"**{i + 1}**")
            with c2:
                st.markdown(q["question"])
            with c3:
                label = weight_to_importance(q.get("weight", 1.0))
                st.markdown(importance_badge_html(label), unsafe_allow_html=True)
            with c4:
                act1, act2 = st.columns(2)
                with act1:
                    with st.popover("Edit"):
                        with st.form(f"edit_rq_{q['id']}"):
                            eq_text = st.text_input("Question", value=q["question"])
                            current_importance = weight_to_importance(q.get("weight", 1.0))
                            eq_importance = st.selectbox(
                                "Importance",
                                importance_options,
                                index=importance_options.index(current_importance),
                            )
                            if st.form_submit_button("Save"):
                                db.update_rubric_question(
                                    conn, q["id"],
                                    question=eq_text.strip(),
                                    weight=importance_to_weight(eq_importance),
                                )
                                st.rerun()
                with act2:
                    with st.popover("Del"):
                        st.warning("Delete this question and all its evaluations?")
                        if st.button("Confirm", key=f"del_rq_{q['id']}", type="primary"):
                            db.delete_rubric_question(conn, q["id"])
                            st.rerun()
    else:
        st.info("No rubric questions defined yet. Add your first question below.")

    st.markdown("")

    # --- Add question ---
    st.markdown("### Add New Question")
    with st.form("add_rubric_q", clear_on_submit=True):
        aq_col1, aq_col2 = st.columns([3, 1])
        with aq_col1:
            new_q = st.text_input("Question", placeholder="e.g. Does the university offer co-op programs?")
        with aq_col2:
            new_importance = st.selectbox("Importance", importance_options, index=1)
        if st.form_submit_button("Add Question") and new_q.strip():
            order = db.get_next_sort_order(conn, "rubric_questions", "user_id", user_id)
            db.create_rubric_question(conn, user_id, new_q.strip(), order, weight=importance_to_weight(new_importance))
            st.rerun()
