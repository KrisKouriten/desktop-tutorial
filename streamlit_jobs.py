"""
Finance Director Job Search — Streamlit dashboard.

Usage:
    streamlit run streamlit_jobs.py
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from job_search import criteria as C
from job_search import poller, storage

st.set_page_config(
    page_title="FD Job Search — London & South West",
    page_icon="📋",
    layout="wide",
)

st.title("Finance Director — Job Search")
st.caption("London & South West UK · Reed + Adzuna + RSS")

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("View")
    min_score = st.slider("Minimum score", 0, 100, int(C.MIN_SCORE_TO_SHOW))
    status_filter = st.selectbox(
        "Status",
        ["all", "new", "seen", "shortlist", "hidden"],
        index=0,
    )
    st.divider()

    st.header("Sources")
    if st.button("Run scan now", use_container_width=True):
        with st.spinner("Polling sources…"):
            result = poller.run_once(verbose=False)
        st.success(
            f"Scanned {result['total']} listings → "
            f"{result['new']} new, {result['updated']} updated "
            f"({result['elapsed_s']:.1f}s)"
        )
        st.rerun()

    st.divider()
    st.header("Criteria summary")
    st.write(f"**Salary floor:** £{C.SALARY_MIN:,}")
    st.write(f"**Day-rate floor:** £{C.DAY_RATE_MIN}/day")
    st.write(f"**Radius:** {C.MILES_RADIUS} miles")
    st.write(f"**Permanent:** {C.INCLUDE_PERMANENT} · **Contract:** {C.INCLUDE_CONTRACT}")
    st.write(f"**Remote:** {C.REMOTE_PREFERENCE}")
    st.write(f"**Poll interval:** {C.POLL_INTERVAL_MINUTES} min")
    st.caption("Edit job_search/criteria.py to change these.")

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
rows = storage.load_listings(
    min_score=min_score,
    status=None if status_filter == "all" else status_filter,
    limit=1000,
)

# ---------------------------------------------------------------------------
# Headline numbers
# ---------------------------------------------------------------------------
all_rows = storage.load_listings(min_score=0, limit=5000)
total = len(all_rows)
new_rows = [r for r in all_rows if r.get("status") == "new"]
shortlisted = [r for r in all_rows if r.get("status") == "shortlist"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total tracked", total)
c2.metric("Unseen (new)", len(new_rows))
c3.metric("Shortlisted", len(shortlisted))
c4.metric("Showing", len(rows))

# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------
if not rows:
    st.info(
        "No listings yet. Set REED_API_KEY and/or ADZUNA_APP_ID/ADZUNA_APP_KEY "
        "in your environment, then click **Run scan now**."
    )
else:
    df = pd.DataFrame(rows)
    df["posted_at"] = pd.to_datetime(df["posted_at"], errors="coerce")
    df["first_seen_at"] = pd.to_datetime(df["first_seen_at"], errors="coerce")

    st.dataframe(
        df[
            [
                "score",
                "title",
                "company",
                "location",
                "salary_min",
                "salary_max",
                "contract_type",
                "source",
                "posted_at",
                "first_seen_at",
                "status",
                "match_reasons",
                "url",
            ]
        ].sort_values("score", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "url": st.column_config.LinkColumn("Open", display_text="→"),
            "score": st.column_config.NumberColumn("Score", format="%.0f"),
            "salary_min": st.column_config.NumberColumn("£ min", format="£%d"),
            "salary_max": st.column_config.NumberColumn("£ max", format="£%d"),
            "posted_at": st.column_config.DatetimeColumn("Posted", format="YYYY-MM-DD"),
            "first_seen_at": st.column_config.DatetimeColumn("First seen", format="YYYY-MM-DD HH:mm"),
        },
    )

    st.divider()
    st.subheader("Triage")
    sel = st.selectbox(
        "Listing",
        options=[f"{r['score']:>5.1f}  ·  {r['title']}  @  {r['company']}" for r in rows],
        index=0,
    )
    idx = [f"{r['score']:>5.1f}  ·  {r['title']}  @  {r['company']}" for r in rows].index(sel)
    chosen = rows[idx]
    col_a, col_b, col_c, col_d = st.columns(4)
    if col_a.button("Mark seen"):
        storage.set_status(chosen["external_id"], "seen")
        st.rerun()
    if col_b.button("Shortlist"):
        storage.set_status(chosen["external_id"], "shortlist")
        st.rerun()
    if col_c.button("Hide"):
        storage.set_status(chosen["external_id"], "hidden")
        st.rerun()
    if col_d.link_button("Open listing", chosen.get("url") or "#"):
        pass

    notes = st.text_area("Notes", value=chosen.get("notes") or "", height=100)
    if st.button("Save notes"):
        storage.set_notes(chosen["external_id"], notes)
        st.success("Saved.")

st.caption(f"Last rendered {datetime.utcnow().isoformat(timespec='seconds')}Z")
