import uuid
import streamlit as st
from workflow import agent_team_coordinator, SERVER_URL, DEMO_MODE, MODEL_ID
from mock_leads import mock_answer
from tables import parse_markdown_table_to_df, generate_styled_excel

# Base filename for every Excel export (the .xlsx extension is added where used).
EXPORT_NAME = "market_leads"

st.set_page_config(page_title="Lead Discovering Agent", layout="wide")

# --- CUSTOM CSS FOR INTERFACE AND SIDEBAR ---
st.markdown("""
<style>
    .stChatMessage:has([data-testid="stChatMessageAvatarUser"]) {
        flex-direction: row-reverse !important;
    }
    .stChatMessage:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
        display: flex !important;
        flex-direction: column !important;
        align-items: flex-end !important;
        text-align: right !important;
    }
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 1px 1px 5px rgba(0,0,0,0.05);
    }
    .sidebar-btn {
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

st.title("Autonomous Chemical Market Discovery Network", anchor=False)

# --- UTILITY FUNCTIONS FOR CORE PROCESSING ---

def _rebuild_messages_from_session(session_id: str) -> list[dict]:
    """
    Rebuilds the chat UI's message list from a persisted Agno TeamSession.
    Uses the real Agno API: team.get_session(session_id=...), which returns
    a TeamSession object with a `.runs` list. Each run has `.input.input_content`
    (the user's message) and `.content` (the assistant's final reply).
    """
    try:
        session = agent_team_coordinator.get_session(session_id=session_id)
        if not session or not session.runs:
            return []

        rebuilt = []
        for run in session.runs:
            user_text = run.input.input_content if run.input else None
            if user_text:
                rebuilt.append({"role": "user", "content": user_text, "file_label": None})

            assistant_text = run.content
            if assistant_text:
                file_label = EXPORT_NAME if "|" in assistant_text else None
                rebuilt.append({"role": "assistant", "content": assistant_text, "file_label": file_label})

        return rebuilt
    except Exception:
        return []


if "agent_session_id" not in st.session_state:
    st.session_state.agent_session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "System Active. What compound constraints, materials or supply chain requests are we targeting today?", "file_label": None}
    ]

with st.sidebar:
    st.subheader(" Conversation Matrix")

    if DEMO_MODE == "real":
        st.success(f"🟢 REAL MODE — `{MODEL_ID}` @ `{SERVER_URL}`")
    else:
        st.warning("🟡 MOCK MODE — instant, no server needed")
    st.caption("Switch by setting DEMO_MODE=mock|real in .env, then restart.")

    if st.button("Start New Chat Thread", use_container_width=True, type="primary"):
        st.session_state.agent_session_id = str(uuid.uuid4())
        st.session_state.messages = [
            {"role": "assistant", "content": "Started a new research pipeline thread. Enter a compound to begin.", "file_label": None}
        ]
        st.rerun()

    st.markdown("---")
    st.subheader("Saved Sessions")

    all_sessions = []
    if agent_team_coordinator.db is not None:
        try:
            all_sessions = agent_team_coordinator.db.get_sessions(session_type="team")
        except Exception as e:
            st.error(f"Could not load saved sessions: {e}")

    if all_sessions:
        # Most recent first
        all_sessions = sorted(
            all_sessions,
            key=lambda s: getattr(s, "created_at", 0) or 0,
            reverse=True,
        )

        for idx, saved_session in enumerate(all_sessions):
            session_id = saved_session.session_id
            is_current = session_id == st.session_state.agent_session_id

            #  Use the first user query as a human-readable session name,
            # since TeamSession has no session_title field in this Agno version.
            display_text = f"Session {session_id[:8]}..."  # fallback
            if saved_session.runs:
                first_run = saved_session.runs[0]
                if first_run.input and first_run.input.input_content:
                    query_preview = first_run.input.input_content.strip()
                    if len(query_preview) > 30:
                        query_preview = query_preview[:30] + "..."
                    display_text = query_preview

            label = f"{'▶ ' if is_current else ''}{display_text}"

            if st.button(
                label,
                key=f"session_btn_{session_id}_{idx}",
                use_container_width=True,
                type="primary" if is_current else "secondary",
            ):
                st.session_state.agent_session_id = session_id
                rebuilt = _rebuild_messages_from_session(session_id)
                if rebuilt:
                    st.session_state.messages = rebuilt
                else:
                    st.session_state.messages = [
                        {
                            "role": "assistant",
                            "content": "Session loaded. Previous history empty or unreadable.",
                            "file_label": None,
                        }
                    ]
                st.rerun()
    elif agent_team_coordinator.db is None:
        st.caption("Session history is off (no database configured).")
    else:
        st.info("No research traces found in your database instance yet.")

# =========================================================================
# 💬 CORE INTERACTION LOOP VIEWPORTS
# =========================================================================

for msg_idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message["role"] == "assistant" and message.get("file_label"):
            try:
                df = parse_markdown_table_to_df(message["content"])
                if df is not None and not df.empty:
                    styled_excel_payload = generate_styled_excel(df)
                    st.download_button(
                        label=f"Download {message['file_label']}.xlsx",
                        data=styled_excel_payload,
                        file_name=f"{message['file_label']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_hist_{msg_idx}"
                    )
            except Exception:
                pass  # never break history rendering over a bad old table

if user_prompt := st.chat_input("Ex: Ethanol processing factories near Gujarat..."):
    st.session_state.messages.append({"role": "user", "content": user_prompt, "file_label": None})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        final_text = None

        run_err = None
        spinner_msg = "Running agent pipeline..." if DEMO_MODE == "real" else "Discovering leads..."
        with st.spinner(spinner_msg):
            try:
                if DEMO_MODE == "real":
                    # db=agent_db means Agno persists this run + session to Postgres automatically.
                    response = agent_team_coordinator.run(
                        user_prompt,
                        session_id=st.session_state.agent_session_id,
                    )
                    final_text = response.content
                else:
                    # Mock mode: pure-Python filter, no server, no network. Instant.
                    final_text = mock_answer(user_prompt)
            except Exception as e:
                run_err = e
                final_text = None

        # Agno sometimes returns a provider error (e.g. Groq rate limit) as the
        # message CONTENT rather than raising — catch that too so no raw error
        # text hits the screen.
        _ft = str(final_text or "")
        _is_ratelimit = "rate limit" in _ft.lower() or "tokens per day" in _ft.lower() or "try again in" in _ft.lower()

        # Never show a raw stack trace on stage. Give a calm message, tuck the
        # technical detail into a collapsed expander for later debugging.
        if not _ft.strip() or _is_ratelimit:
            detail = _ft if _is_ratelimit else (f"{type(run_err).__name__}: {run_err}" if run_err else "")
            if _is_ratelimit:
                final_text = (
                    "⚠️ The live model's free-tier quota is used up for now. "
                    "Switch to **mock mode** (`DEMO_MODE=mock` in `.env`, restart) for an instant result, "
                    "or try a different model / wait for the quota to reset."
                )
            else:
                final_text = (
                    "I couldn't pull results for that one. Try rephrasing the compound, "
                    "or flip to mock mode for a guaranteed result."
                )
            if detail:
                with st.expander("technical detail (for debugging)"):
                    st.caption(detail)

        file_label = EXPORT_NAME

        response_placeholder.markdown(final_text)
        st.session_state.messages.append({"role": "assistant", "content": final_text, "file_label": file_label})

        # --- EXCEL EXPORT & VIEWPORT METRICS (fully guarded) ---
        try:
            df = parse_markdown_table_to_df(final_text)
            if df is not None and not df.empty:
                missing_fields_count = (df == "N/A").sum().sum()

                st.markdown("### Extraction Summary")
                col1, col2, col3 = st.columns(3)
                col1.metric("Verified Leads Extracted", len(df))
                col2.metric("Missing Fields Caught", missing_fields_count)
                col3.metric("Export Identifier", f"{file_label}.xlsx")

                excel_binary = generate_styled_excel(df)
                st.download_button(
                    label=f"Download {file_label}.xlsx",
                    data=excel_binary,
                    file_name=f"{file_label}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_current"
                )
        except Exception:
            st.info("Result shown above. (Table export skipped — response wasn't in table form.)")

    st.rerun()