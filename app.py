"""Fly Away Tracker — Streamlit edition."""

import os

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from dotenv import load_dotenv
from yaml.loader import SafeLoader

import db

load_dotenv()
from pages.dashboard import page_dashboard
from pages.user_progress import page_user_progress
from pages.tasks import page_tasks
from pages.university_analysis import page_university_analysis
from pages.rubric_manage import page_rubric_manage
from pages.helpers import nav_to

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Fly Away Tracker",
    page_icon=":rocket:",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #faf9f7; }
    .stApp[data-theme="dark"] { background-color: #1a1a1a; }
    .stat-card {
        background: white;
        border: 1px solid #e5e5e5;
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
    }
    .stat-value { font-size: 28px; font-weight: 700; }
    .stat-label { font-size: 13px; color: #737373; margin-top: 2px; }
    .status-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        color: white;
    }
    /* Condensed vertical spacing */
    div[data-testid="stExpander"] { margin-bottom: -4px; }
    div[data-testid="stForm"] { padding: 0; }
    .stDivider { margin: 8px 0; }
    /* Sidebar nav styling */
    .nav-section { font-size: 11px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; margin: 16px 0 4px; }
    .nav-user { font-size: 14px; font-weight: 600; color: #374151; margin: 8px 0 2px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
if os.environ.get("AUTH_MARIA_PASSWORD") and os.environ.get("AUTH_SHAD_PASSWORD"):
    auth_config = {
        "credentials": {
            "usernames": {
                "maria": {
                    "name": "Maria",
                    "password": os.environ["AUTH_MARIA_PASSWORD"],
                },
                "shad": {
                    "name": "Shad",
                    "password": os.environ["AUTH_SHAD_PASSWORD"],
                },
            }
        },
        "cookie": {
            "name": os.environ.get("AUTH_COOKIE_NAME", "mpt_auth_cookie"),
            "key": os.environ["AUTH_COOKIE_KEY"],
            "expiry_days": int(os.environ.get("AUTH_COOKIE_EXPIRY_DAYS", "30")),
        },
    }
else:
    with open("config.yaml") as f:
        auth_config = yaml.load(f, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    auth_config["credentials"],
    auth_config["cookie"]["name"],
    auth_config["cookie"]["key"],
    auth_config["cookie"]["expiry_days"],
)

authenticator.login()

if st.session_state.get("authentication_status") is None:
    st.info("Please enter your username and password.")
    st.stop()
elif st.session_state.get("authentication_status") is False:
    st.error("Username or password is incorrect.")
    st.stop()

# ---------------------------------------------------------------------------
# DB init
# ---------------------------------------------------------------------------
conn = db.get_connection()
db.init_schema(conn)

users = db.get_users(conn)
if not users:
    db.seed(conn)
    users = db.get_users(conn)

# ---------------------------------------------------------------------------
# Sidebar — nested navigation
# ---------------------------------------------------------------------------
params = st.query_params
page = params.get("page", "dashboard")
selected_user_id = params.get("user_id", None)

with st.sidebar:
    st.markdown(f"**Logged in as:** {st.session_state['name']}")
    authenticator.logout("Logout", "sidebar")
    st.markdown("---")
    st.markdown("### Navigation")

    # Dashboard link
    if st.button("Dashboard", use_container_width=True, type="primary" if page == "dashboard" else "secondary"):
        nav_to("dashboard")
        st.rerun()

    # Per-user navigation
    for user in users:
        uid = user["id"]
        is_user_page = selected_user_id == uid

        st.markdown(f'<div class="nav-user">{user["name"]}</div>', unsafe_allow_html=True)

        active = page == "user" and is_user_page
        if st.button("Overview", key=f"nav_overview_{uid}", use_container_width=True,
                     type="primary" if active else "secondary"):
            nav_to("user", user_id=uid)
            st.rerun()

        active = page == "tasks" and is_user_page
        if st.button("Tasks", key=f"nav_tasks_{uid}", use_container_width=True,
                     type="primary" if active else "secondary"):
            nav_to("tasks", user_id=uid)
            st.rerun()

        # University pages (only if user has rubric data)
        rubric_qs = db.get_rubric_questions(conn, uid)
        if rubric_qs:
            active = page == "analysis" and is_user_page
            if st.button("Universities", key=f"nav_analysis_{uid}", use_container_width=True,
                         type="primary" if active else "secondary"):
                nav_to("analysis", user_id=uid)
                st.rerun()

            active = page == "rubric_manage" and is_user_page
            if st.button("Rubric", key=f"nav_rubric_{uid}", use_container_width=True,
                         type="primary" if active else "secondary"):
                nav_to("rubric_manage", user_id=uid)
                st.rerun()

        st.markdown("---")

    st.markdown("### Settings")
    if st.button("Re-seed database", type="secondary"):
        db.seed(conn)
        st.rerun()

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
if page == "user" and selected_user_id:
    page_user_progress(conn, users, selected_user_id)
elif page == "tasks" and selected_user_id:
    page_tasks(conn, users, selected_user_id)
elif page == "analysis" and selected_user_id:
    page_university_analysis(conn, users, selected_user_id)
elif page == "rubric_manage" and selected_user_id:
    page_rubric_manage(conn, users, selected_user_id)
else:
    page_dashboard(conn, users)
