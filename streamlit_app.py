"""
HR Agent — Streamlit demo UI

Connects to the FastAPI backend (default: http://localhost:8000).
Run both processes together:
  Terminal 1:  uvicorn hr_agent.main:app --reload --reload-dir hr_agent
  Terminal 2:  streamlit run streamlit_app.py
"""
import time

import requests
import streamlit as st

# ── Config ─────────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"
POLL_INTERVAL_SEC = 2
POLL_MAX_ATTEMPTS = 45  # ~90 seconds max wait

# ── Page setup ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HR Agent",
    page_icon="👔",
    layout="wide",
)

# ── Session state ──────────────────────────────────────────────────────────────
if "jobs" not in st.session_state:
    st.session_state.jobs = {}        # {job_id: {title, filename, status}}
if "candidates" not in st.session_state:
    st.session_state.candidates = {}  # {candidate_id: {name, filename, status}}


# ── API helpers ────────────────────────────────────────────────────────────────

STATUS_COLOR = {
    "PENDING":    "🔘",
    "EXTRACTED":  "🔵",
    "STRUCTURED": "🟡",
    "EMBEDDED":   "🟢",
    "FAILED":     "🔴",
}


def status_badge(status: str) -> str:
    return f"{STATUS_COLOR.get(status, '⚪')} {status}"


def score_bar(value: float | None) -> str:
    if value is None:
        return "—"
    pct = int(value * 100)
    filled = int(pct / 5)
    return f"`{'█' * filled}{'░' * (20 - filled)}` {pct}%"


def api_get(path: str) -> dict | list | None:
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the API. Is the FastAPI server running on port 8000?")
        return None
    except Exception as exc:
        st.error(f"API error: {exc}")
        return None


def api_post(path: str, **kwargs) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}{path}", timeout=30, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the API. Is the FastAPI server running on port 8000?")
        return None
    except Exception as exc:
        st.error(f"API error: {exc}")
        return None


def api_put(path: str, **kwargs) -> dict | None:
    try:
        r = requests.put(f"{API_BASE}{path}", timeout=10, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the API.")
        return None
    except Exception as exc:
        st.error(f"API error: {exc}")
        return None


def api_delete(path: str) -> bool:
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return True
    except Exception as exc:
        st.error(f"API error: {exc}")
        return False


# ── Session helpers ────────────────────────────────────────────────────────────

def reload_from_db():
    """Populate session state from the DB (useful after server restart)."""
    jobs_data = api_get("/admin/jobs")
    if jobs_data:
        for job in jobs_data:
            jid = job["id"]
            st.session_state.jobs[jid] = {
                "title": job.get("title") or "Untitled",
                "filename": "—",
                "status": job.get("status", "PENDING"),
            }

    cands_data = api_get("/admin/candidates")
    if cands_data:
        for cand in cands_data:
            cid = cand["id"]
            st.session_state.candidates[cid] = {
                "name": cand.get("name") or "Unknown",
                "filename": "—",
                "status": cand.get("status", "PENDING"),
            }


def refresh_all_statuses():
    for jid in list(st.session_state.jobs.keys()):
        data = api_get(f"/jobs/{jid}")
        if data:
            st.session_state.jobs[jid]["status"] = data.get("status", "PENDING")
            if data.get("title"):
                st.session_state.jobs[jid]["title"] = data["title"]

    for key, info in list(st.session_state.candidates.items()):
        email = info.get("email")
        if email:
            data = api_get(f"/candidates/{email}")
        else:
            data = api_get(f"/candidates/imports/{key}")
            if data and data.get("proposed_email"):
                data = api_get(f"/candidates/{data['proposed_email']}")
        if data:
            st.session_state.candidates[key]["status"] = data.get("status", "PENDING")
            if data.get("name"):
                st.session_state.candidates[key]["name"] = data["name"]
            if data.get("email"):
                st.session_state.candidates[key]["email"] = data["email"]


def poll_import_until_done(import_id: str, status_placeholder) -> str:
    """Poll GET /candidates/imports/{import_id} until terminal status."""
    for attempt in range(POLL_MAX_ATTEMPTS):
        data = api_get(f"/candidates/imports/{import_id}")
        if data is None:
            return "FAILED"
        status = data.get("status", "PROCESSING")
        status_placeholder.info(
            f"Processing... {status_badge(status)}  "
            f"(attempt {attempt + 1}/{POLL_MAX_ATTEMPTS})"
        )
        if status in ("COMPLETED", "CONFLICT", "FAILED", "DISCARDED"):
            return status
        time.sleep(POLL_INTERVAL_SEC)
    return "TIMEOUT"


def poll_until_ready(entity_type: str, entity_id: str, status_placeholder) -> str:
    endpoint = f"/{entity_type}s/{entity_id}"
    for attempt in range(POLL_MAX_ATTEMPTS):
        data = api_get(endpoint)
        if data is None:
            return "FAILED"
        status = data.get("status", "PENDING")
        status_placeholder.info(
            f"Processing... {status_badge(status)}  "
            f"(attempt {attempt + 1}/{POLL_MAX_ATTEMPTS})"
        )
        if status in ("EMBEDDED", "FAILED"):
            return status
        time.sleep(POLL_INTERVAL_SEC)
    return "TIMEOUT"


# ── JD display helpers ─────────────────────────────────────────────────────────

def _pill(text: str, color: str = "#e0e0e0") -> str:
    return (
        f'<span style="background:{color};padding:2px 8px;border-radius:12px;'
        f'font-size:0.82em;margin:2px;display:inline-block">{text}</span>'
    )


def _pills(items: list[str], color: str = "#dde8fb") -> str:
    if not items:
        return "<em style='color:#aaa'>—</em>"
    return " ".join(_pill(i, color) for i in items)


def render_jd_fields(jd: dict):
    """Render all extracted JD fields in a structured two-column layout."""
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Role**")
        st.markdown(f"> {jd.get('normalized_role') or '—'}")
        st.markdown("**Seniority**")
        st.markdown(f"> {jd.get('seniority_level') or '—'}")
        st.markdown("**Experience**")
        exp_min = jd.get("experience_min", "?")
        exp_max = jd.get("experience_max", "?")
        st.markdown(f"> {exp_min} – {exp_max} years")
        st.markdown("**Employment Type**")
        st.markdown(f"> {jd.get('employment_type') or '—'}")
        st.markdown("**Location**")
        st.markdown(f"> {jd.get('location') or '—'}")
        st.markdown("**Industry**")
        st.markdown(f"> {jd.get('industry') or '—'}")
        st.markdown("**Department**")
        st.markdown(f"> {jd.get('department') or '—'}")

    with c2:
        st.markdown("**Must-Have Skills**")
        st.markdown(_pills(jd.get("must_have_skills") or []), unsafe_allow_html=True)
        st.markdown("**Nice-to-Have Skills**")
        st.markdown(_pills(jd.get("good_to_have_skills") or [], "#e8f5e9"), unsafe_allow_html=True)
        st.markdown("**Tools & Technologies**")
        st.markdown(_pills(jd.get("tools_and_technologies") or [], "#fff3e0"), unsafe_allow_html=True)
        st.markdown("**Certifications**")
        st.markdown(_pills(jd.get("certifications") or [], "#f3e5f5"), unsafe_allow_html=True)
        st.markdown("**Education Requirements**")
        st.markdown(_pills(jd.get("education_requirements") or [], "#fce4ec"), unsafe_allow_html=True)

    responsibilities = jd.get("responsibilities") or []
    if responsibilities:
        with st.expander(f"Key Responsibilities ({len(responsibilities)})"):
            for r in responsibilities:
                st.markdown(f"- {r}")

    if jd.get("summary"):
        with st.expander("Summary"):
            st.markdown(jd["summary"])


def render_hard_checks_config(jd: dict, jid: str):
    """
    Render the hard-check configuration panel for a job.
    List fields get a multiselect; scalar fields get a checkbox.
    Returns the dict of new hard_checks built from current widget state.
    """
    current_hc: dict = jd.get("hard_checks") or {}
    new_hc: dict = {}

    st.caption(
        "Selected values are applied as **hard filters** — candidates that don't "
        "match are eliminated before scoring. Experience is always a hard check."
    )
    st.markdown("---")

    # ── List fields ────────────────────────────────────────────────────────────
    skills = jd.get("must_have_skills") or []
    if skills:
        default = [v for v in current_hc.get("must_have_skills", []) if v in skills]
        sel = st.multiselect(
            "🔴 Must-Have Skills (hard check)",
            options=skills,
            default=default,
            key=f"hc_skills_{jid}",
            help="Candidate must have ALL selected skills (checked in skills + tools pool).",
        )
        if sel:
            new_hc["must_have_skills"] = sel

    tools = jd.get("tools_and_technologies") or []
    if tools:
        default = [v for v in current_hc.get("tools_and_technologies", []) if v in tools]
        sel = st.multiselect(
            "🔧 Tools & Technologies (hard check)",
            options=tools,
            default=default,
            key=f"hc_tools_{jid}",
            help="Candidate must have ALL selected tools in their tools list.",
        )
        if sel:
            new_hc["tools_and_technologies"] = sel

    certs = jd.get("certifications") or []
    if certs:
        default = [v for v in current_hc.get("certifications", []) if v in certs]
        sel = st.multiselect(
            "📜 Certifications (hard check)",
            options=certs,
            default=default,
            key=f"hc_certs_{jid}",
            help="Candidate must hold ALL selected certifications.",
        )
        if sel:
            new_hc["certifications"] = sel

    # ── Scalar fields ──────────────────────────────────────────────────────────
    seniority = jd.get("seniority_level")
    if seniority:
        enabled = st.checkbox(
            f"🎓 Seniority must be: **{seniority}**",
            value=bool(current_hc.get("seniority_level")),
            key=f"hc_seniority_{jid}",
            help="Candidates with a different extracted seniority level are eliminated.",
        )
        if enabled:
            new_hc["seniority_level"] = seniority

    role = jd.get("normalized_role")
    if role:
        enabled = st.checkbox(
            f"💼 Role must match: **{role}**",
            value=bool(current_hc.get("normalized_role")),
            key=f"hc_role_{jid}",
            help="Only candidates with exactly this normalized role pass the filter.",
        )
        if enabled:
            new_hc["normalized_role"] = role

    industry = jd.get("industry")
    if industry:
        enabled = st.checkbox(
            f"🏭 Industry must include: **{industry}**",
            value=bool(current_hc.get("industry")),
            key=f"hc_industry_{jid}",
            help="Candidate's industry list must contain this industry.",
        )
        if enabled:
            new_hc["industry"] = industry

    location = jd.get("location")
    if location:
        enabled = st.checkbox(
            f"📍 Location must match: **{location}**",
            value=bool(current_hc.get("location")),
            key=f"hc_location_{jid}",
            help="Candidate's location must match (substring check both ways).",
        )
        if enabled:
            new_hc["location"] = location

    st.markdown("---")
    if st.button("💾 Save Hard Checks", key=f"save_hc_{jid}", type="primary"):
        result = api_put(f"/jobs/{jid}/hard-checks", json={"hard_checks": new_hc})
        if result is not None:
            if new_hc:
                st.success(f"Saved {len(new_hc)} hard check(s). Re-run matching to apply.")
            else:
                st.info("All hard checks cleared for this job.")

    return new_hc


def render_active_hard_checks(jd: dict):
    """Show a compact summary of active hard checks for a job."""
    hc: dict = jd.get("hard_checks") or {}
    exp_min = jd.get("experience_min")
    exp_max = jd.get("experience_max")

    lines = []
    if exp_min is not None or exp_max is not None:
        lines.append(f"Experience: **{exp_min or '?'} – {exp_max or '?'} years** (always)")
    for field, value in hc.items():
        if isinstance(value, list):
            lines.append(f"{field.replace('_', ' ').title()}: **{', '.join(value)}**")
        else:
            lines.append(f"{field.replace('_', ' ').title()}: **{value}**")

    if lines:
        with st.expander(f"🔒 Active Hard Checks ({len(lines)} rule(s))", expanded=False):
            for line in lines:
                st.markdown(f"- {line}")
    else:
        st.caption("_No hard checks configured (only experience filter applies)._")


# ── Sidebar — Admin ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Admin")
    st.divider()

    if st.button("🔄 Reload All from DB", use_container_width=True):
        reload_from_db()
        st.rerun()

    st.divider()
    st.markdown("**Danger Zone**")
    if "confirm_clear" not in st.session_state:
        st.session_state.confirm_clear = False

    if not st.session_state.confirm_clear:
        if st.button("🗑️ Clear All Data", use_container_width=True):
            st.session_state.confirm_clear = True
            st.rerun()
    else:
        st.warning("This will delete **all** jobs, CVs, embeddings and match results.")
        col_yes, col_no = st.columns(2)
        if col_yes.button("Yes, clear", type="primary", use_container_width=True):
            if api_delete("/admin/clear-all"):
                st.session_state.jobs = {}
                st.session_state.candidates = {}
                st.session_state.confirm_clear = False
                st.success("All data cleared.")
                st.rerun()
        if col_no.button("Cancel", use_container_width=True):
            st.session_state.confirm_clear = False
            st.rerun()

    st.divider()
    st.caption(f"API: `{API_BASE}`")


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("HR Agent")
st.caption("AI-powered CV ↔ Job Description matching — POC Demo")

health = api_get("/health")
if health and health.get("status") == "ok":
    st.success("API online", icon="✅")
else:
    st.error("API is offline — start the FastAPI server first.", icon="🔴")
    st.code("uvicorn hr_agent.main:app --reload --reload-dir hr_agent")
    st.stop()

st.divider()


# ── Tabs ────────────────────────────────────────────────────────────────────────
tab_jd, tab_cv, tab_match = st.tabs([
    "📋  Job Descriptions",
    "👤  Candidates",
    "🔍  Find Matches",
])


# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Job Descriptions
# ══════════════════════════════════════════════════════════════════════════════
with tab_jd:
    st.subheader("Upload Job Description")
    st.caption("Upload a PDF of the job description. Fields are extracted automatically by LLM.")

    uploaded_jd = st.file_uploader("Choose a JD PDF", type=["pdf"], key="jd_uploader")

    if st.button("Upload JD", type="primary", disabled=uploaded_jd is None):
        with st.spinner("Uploading PDF..."):
            result = api_post(
                "/jobs/upload",
                files={"file": (uploaded_jd.name, uploaded_jd.getvalue(), "application/pdf")},
            )

        if result:
            job_id = result["job_id"]
            st.session_state.jobs[job_id] = {
                "title": uploaded_jd.name.replace(".pdf", ""),
                "filename": uploaded_jd.name,
                "status": "EXTRACTED",
            }
            st.success(f"Uploaded — job_id: `{job_id}`")

            status_ph = st.empty()
            final_status = poll_until_ready("job", job_id, status_ph)

            if final_status == "EMBEDDED":
                data = api_get(f"/jobs/{job_id}")
                if data and data.get("title"):
                    st.session_state.jobs[job_id]["title"] = data["title"]
                st.session_state.jobs[job_id]["status"] = "EMBEDDED"
                status_ph.success(f"Ready! {status_badge('EMBEDDED')} — extraction complete.")
            elif final_status == "FAILED":
                st.session_state.jobs[job_id]["status"] = "FAILED"
                status_ph.error("Processing failed. Check the server logs.")
            else:
                status_ph.warning("Processing timed out. Refresh status below.")

    # ── Job list ───────────────────────────────────────────────────────────────
    if st.session_state.jobs:
        st.divider()
        col1, col2 = st.columns([4, 1])
        col1.subheader("Uploaded Job Descriptions")
        if col2.button("Refresh Status", key="refresh_jobs"):
            refresh_all_statuses()
            st.rerun()

        for jid, info in st.session_state.jobs.items():
            with st.container(border=True):
                # Header row
                h1, h2, h3 = st.columns([3, 2, 1])
                h1.markdown(f"**{info['title']}**")
                h1.caption(f"`{jid}`")
                h2.markdown(info.get("filename", "—"))
                h3.markdown(status_badge(info["status"]))

                # Extracted fields + hard checks panel (only when structured/embedded)
                if info["status"] in ("STRUCTURED", "EMBEDDED"):
                    with st.expander("📋 Extracted Fields & Hard Checks"):
                        jd_data = api_get(f"/jobs/{jid}")
                        if jd_data:
                            fields_col, checks_col = st.columns([1, 1])

                            with fields_col:
                                st.markdown("#### Extracted Fields")
                                render_jd_fields(jd_data)

                            with checks_col:
                                st.markdown("#### 🔒 Hard Check Configuration")
                                render_hard_checks_config(jd_data, jid)
    else:
        st.info("No job descriptions uploaded yet in this session. Use **Reload from DB** in the sidebar if you have existing data.")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — Candidates
# ══════════════════════════════════════════════════════════════════════════════
with tab_cv:
    st.subheader("Upload Candidate CVs")
    st.caption("Upload one or more CV PDFs. You can upload multiple at once.")

    uploaded_cvs = st.file_uploader(
        "Choose CV PDFs", type=["pdf"], accept_multiple_files=True, key="cv_uploader"
    )

    if st.button("Upload CVs", type="primary", disabled=not uploaded_cvs):
        for cv_file in uploaded_cvs:
            st.markdown(f"**Processing:** `{cv_file.name}`")
            upload_ph = st.empty()

            with upload_ph.container():
                with st.spinner(f"Uploading {cv_file.name}..."):
                    result = api_post(
                        "/candidates/upload",
                        files={"file": (cv_file.name, cv_file.getvalue(), "application/pdf")},
                    )

            if result:
                import_id = result["import_id"]
                st.session_state.candidates[import_id] = {
                    "name": cv_file.name.replace(".pdf", ""),
                    "filename": cv_file.name,
                    "status": "PROCESSING",
                }
                upload_ph.success(f"Uploaded — import_id: `{import_id}` (processing in background)")

                status_ph = st.empty()
                # Poll imports until completed, conflict, or failed
                final_status = poll_import_until_done(import_id, status_ph)

                if final_status == "COMPLETED":
                    imports = api_get("/candidates/imports") or []
                    row = next((i for i in imports if i.get("import_id") == import_id), None)
                    email = row.get("proposed_email") if row else None
                    if email:
                        data = api_get(f"/candidates/{email}")
                        if data and data.get("name"):
                            st.session_state.candidates[import_id]["name"] = data["name"]
                            st.session_state.candidates[import_id]["email"] = email
                        st.session_state.candidates[import_id]["status"] = data.get("status", "EMBEDDED") if data else "COMPLETED"
                        status_ph.success(
                            f"{cv_file.name} — {status_badge('EMBEDDED')}  "
                            f"Name: **{st.session_state.candidates[import_id]['name']}**  "
                            f"Email: `{email}`"
                        )
                    else:
                        status_ph.success(f"{cv_file.name} — processing completed.")
                elif final_status == "CONFLICT":
                    st.session_state.candidates[import_id]["status"] = "CONFLICT"
                    status_ph.warning(
                        f"{cv_file.name} — duplicate email detected. "
                        f"Resolve in the React UI under Candidates → Duplicate emails."
                    )
                elif final_status == "FAILED":
                    st.session_state.candidates[import_id]["status"] = "FAILED"
                    status_ph.error(f"{cv_file.name} — processing failed.")
                else:
                    status_ph.warning(f"{cv_file.name} — timed out.")

    # ── Candidate list ─────────────────────────────────────────────────────────
    if st.session_state.candidates:
        st.divider()
        col1, col2 = st.columns([4, 1])
        col1.subheader("Uploaded Candidates")
        if col2.button("Refresh Status", key="refresh_cvs"):
            refresh_all_statuses()
            st.rerun()

        for key, info in st.session_state.candidates.items():
            with st.container(border=True):
                h1, h2, h3 = st.columns([3, 2, 1])
                h1.markdown(f"**{info['name']}**")
                label = info.get("email") or key
                h1.caption(f"`{label}`")
                h2.markdown(info.get("filename", "—"))
                h3.markdown(status_badge(info["status"]))

                if info["status"] in ("STRUCTURED", "EMBEDDED"):
                    with st.expander("👤 Extracted Profile"):
                        email = info.get("email")
                        cv_data = api_get(f"/candidates/{email}") if email else None
                        if cv_data:
                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown(f"**Current Title:** {cv_data.get('current_title') or '—'}")
                                st.markdown(f"**Normalized Role:** {cv_data.get('normalized_role') or '—'}")
                                st.markdown(f"**Seniority:** {cv_data.get('seniority_level') or '—'}")
                                st.markdown(f"**Experience:** {cv_data.get('years_experience') or '—'} years")
                                st.markdown(f"**Current Company:** {cv_data.get('current_company') or '—'}")
                                st.markdown(f"**Location:** {cv_data.get('location') or '—'}")
                                inds = cv_data.get("industries") or []
                                st.markdown(f"**Industries:** {', '.join(inds) or '—'}")
                            with c2:
                                st.markdown("**Skills**")
                                st.markdown(_pills(cv_data.get("skills") or []), unsafe_allow_html=True)
                                st.markdown("**Tools & Technologies**")
                                st.markdown(_pills(cv_data.get("tools_and_technologies") or [], "#fff3e0"), unsafe_allow_html=True)
                                st.markdown("**Certifications**")
                                st.markdown(_pills(cv_data.get("certifications") or [], "#f3e5f5"), unsafe_allow_html=True)
                            exp_areas = cv_data.get("experience_areas") or []
                            if exp_areas:
                                st.markdown("**Experience Areas**")
                                st.markdown(_pills(exp_areas, "#e8f5e9"), unsafe_allow_html=True)
                            edu = cv_data.get("education") or []
                            if edu:
                                st.markdown("**Education**")
                                for e in edu:
                                    deg = e.get("degree", "")
                                    inst = e.get("institution", "")
                                    yr = e.get("year", "")
                                    st.markdown(f"- {deg} — {inst}" + (f" ({yr})" if yr else ""))
    else:
        st.info("No candidates uploaded yet in this session. Use **Reload from DB** in the sidebar if you have existing data.")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — Find Matches
# ══════════════════════════════════════════════════════════════════════════════
with tab_match:
    st.subheader("Find Matching Candidates")
    st.caption("Select a job description to rank all uploaded candidates by fit.")

    ready_jobs = {
        jid: info
        for jid, info in st.session_state.jobs.items()
        if info["status"] == "EMBEDDED"
    }

    if not ready_jobs:
        st.warning(
            "No ready job descriptions found. "
            "Upload a JD in the **Job Descriptions** tab and wait for status **EMBEDDED**."
        )
    else:
        jd_options = {f"{info['title']}  [{jid[:8]}…]": jid for jid, info in ready_jobs.items()}
        selected_label = st.selectbox("Select Job Description", options=list(jd_options.keys()))
        selected_job_id = jd_options[selected_label]

        # Show active hard checks for the selected job
        jd_detail = api_get(f"/jobs/{selected_job_id}")
        if jd_detail:
            render_active_hard_checks(jd_detail)

        col_btn, col_recompute = st.columns([2, 2])
        run_match = col_btn.button("Find Matches", type="primary")
        force_recompute = col_recompute.button(
            "Force Re-run",
            help="Clears cached results and re-runs the full pipeline (picks up new hard checks)",
        )

        if force_recompute:
            with st.spinner("Triggering fresh pipeline run..."):
                result = api_post("/recompute-match", json={"job_id": selected_job_id})
            if result:
                st.success("Re-run triggered. Wait ~15 seconds then click **Find Matches**.")

        if run_match:
            with st.spinner("Running matching pipeline… this may take 15–30 seconds on first run."):
                data = api_get(f"/matches/{selected_job_id}")

            if data is None:
                st.stop()

            st.divider()

            # ── Summary strip ──────────────────────────────────────────────
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Candidates", data["total_candidates"])
            m2.metric("Passed Filter", data["passed_filter"])
            m3.metric("Eliminated", data["total_candidates"] - data["passed_filter"])
            ranked = [m for m in data["matches"] if not m["is_filtered"] and m["final_score"] is not None]
            top_score = f"{ranked[0]['final_score'] * 100:.0f}%" if ranked else "—"
            m4.metric("Top Score", top_score)

            # ── Ranked candidates ──────────────────────────────────────────
            st.subheader("Ranked Candidates")
            if not ranked:
                st.warning("No candidates passed the hard filter for this job.")
            else:
                for match in ranked:
                    final = match["final_score"] or 0
                    rule = match["rule_score"] or 0
                    vector = match["vector_score"] or 0
                    llm = match["llm_score"] or 0

                    with st.container(border=True):
                        header_col, score_col = st.columns([3, 1])
                        header_col.markdown(
                            f"**#{match['rank']}  {match['candidate_name'] or match['candidate_id']}**"
                        )
                        header_col.caption(f"`{match['candidate_id']}`")
                        score_col.metric("Final Score", f"{final * 100:.0f}%")

                        s1, s2, s3 = st.columns(3)
                        s1.markdown("**Rule Score**")
                        s1.progress(rule, text=f"{rule * 100:.0f}%")
                        s2.markdown("**Vector Score**")
                        s2.progress(vector, text=f"{vector * 100:.0f}%")
                        s3.markdown("**LLM Score**")
                        s3.progress(llm, text=f"{llm * 100:.0f}%")

                        if match.get("explanation"):
                            st.info(match["explanation"], icon="💬")

            # ── Filtered out ───────────────────────────────────────────────
            filtered = [m for m in data["matches"] if m["is_filtered"]]
            if filtered:
                with st.expander(f"Eliminated by hard filter ({len(filtered)} candidates)"):
                    for m in filtered:
                        st.markdown(
                            f"- **{m['candidate_name'] or m['candidate_id']}** "
                            f"— {m['filter_reason']}"
                        )

            if data.get("computed_at"):
                st.caption(f"Results computed at: {data['computed_at']}")
