"""Streamlit admin GUI for the Theophysics corpus index and ME sidecar."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import psycopg2
import streamlit as st

# The indexer package lives two levels up under LEAN 4/.
INDEXER_DIR = Path(__file__).resolve().parents[2] / "LEAN 4" / "theophysics_corpus_indexer"
sys.path.insert(0, str(INDEXER_DIR))

import db
from config import SERIES_LABELS, SOURCE_ROOTS

st.set_page_config(page_title="Theophysics Corpus Admin", layout="wide")


@st.cache_resource
def db_connection() -> psycopg2.extensions.connection:
    return db.get_conn()


def _run_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"


def overview_page() -> None:
    st.header(":material/database: Corpus overview")
    conn = db_connection()
    with conn.cursor() as cur:
        p1 = db.get_p1_metrics(cur)
        p2 = db.get_p2_metrics(cur)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unique files", f"{p1['unique_files']:,}")
    c2.metric("Total locations", f"{p1['total_locations']:,}")
    c3.metric("Duplicate hashes", f"{p1['duplicate_hashes']:,}")
    c4.metric("Duplicate ratio", f"{p1['duplicate_ratio']:.2%}")

    st.subheader("Classification health")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Classified ≥0.8", f"{p2['classified_pct']}%")
    c2.metric("Library quarantined", f"{p2['library_pct']}%")
    c3.metric("Unclassified", f"{p2['unclassified_pct']}%")
    c4.metric("With receipt", f"{p2['with_receipt_pct']}%")

    if p2.get("series_counts"):
        st.subheader("Series counts")
        series_df = pd.DataFrame(
            list(p2["series_counts"].items()), columns=["series", "count"]
        )
        st.bar_chart(series_df.set_index("series"))

    with st.expander("Per-root location counts"):
        per_root_df = pd.DataFrame(
            list(p1["per_root"].items()), columns=["root", "locations"]
        )
        st.dataframe(per_root_df, hide_index=True)


def unclassified_page() -> None:
    st.header(":material/help_outline: Unclassified review")
    limit = st.slider("Rows to show", 10, 500, 100)
    conn = db_connection()
    df = pd.read_sql(
        """
        SELECT f.sha256, f.ext, f.size_bytes, f.summary, l.path
        FROM files f
        JOIN locations l ON l.sha256 = f.sha256
        WHERE f.series IS NULL AND f.is_library = false
        ORDER BY f.first_seen DESC
        LIMIT %s
        """,
        conn,
        params=(limit,),
    )

    event = st.dataframe(
        df,
        on_select="rerun",
        selection_mode="multi-row",
        hide_index=True,
        key="unclass_df",
    )
    selected_rows = event.selection.rows if event else []

    if not selected_rows:
        st.info("Select one or more rows above to classify them.")
        return

    selected = df.iloc[selected_rows]
    st.caption(f"{len(selected)} file(s) selected")

    with st.container(border=True):
        new_series = st.selectbox("Assign series", SERIES_LABELS)
        note = st.text_input("Note (optional)", placeholder="Why this series?")
        if st.button("Apply classification", type="primary"):
            run_id = _run_id("manual-classify")
            with conn.cursor() as cur:
                for sha in selected["sha256"]:
                    cur.execute(
                        "UPDATE files SET series = %s, series_conf = 1.0 WHERE sha256 = %s",
                        (new_series, sha),
                    )
                    db.insert_receipt(
                        cur,
                        sha,
                        run_id,
                        "MANUAL_CLASSIFY",
                        result=new_series,
                        log_path=note or None,
                        ran_at=datetime.now(timezone.utc),
                    )
            conn.commit()
            st.success(f"Classified {len(selected)} files as {new_series}.")
            st.rerun()


def folder_batch_page() -> None:
    st.header(":material/folder: Folder batch classify")
    root = st.selectbox("Source root", SOURCE_ROOTS)
    conn = db_connection()

    # Discover directories under the chosen root from the locations table.
    cur = conn.cursor()
    cur.execute(
        "SELECT path FROM locations WHERE path LIKE %s",
        (root.replace("\\", "/") + "/%",),
    )
    dirs: set[str] = set()
    for (path,) in cur.fetchall():
        rel = path[len(root) :].lstrip("\\/")
        parts = rel.replace("\\", "/").split("/")
        prefix = ""
        for part in parts[:-1]:
            prefix = f"{prefix}/{part}".strip("/")
            dirs.add(prefix)

    subdir = st.selectbox("Subfolder", ["(root)"] + sorted(dirs))
    target = root.rstrip("\\/")
    if subdir != "(root)":
        target = target + "\\" + subdir.replace("/", "\\")

    like_pattern = target.replace("\\", "\\\\") + "%"
    df = pd.read_sql(
        """
        SELECT DISTINCT f.sha256, f.ext, f.summary, l.path
        FROM files f
        JOIN locations l ON l.sha256 = f.sha256
        WHERE l.path LIKE %s ESCAPE '\\'
        ORDER BY l.path
        """,
        conn,
        params=(like_pattern,),
    )
    st.caption(f"{len(df)} file(s) under `{target}`")

    event = st.dataframe(
        df,
        on_select="rerun",
        selection_mode="multi-row",
        hide_index=True,
        key="folder_df",
    )
    selected_rows = event.selection.rows if event else []

    if selected_rows:
        selected = df.iloc[selected_rows]
        st.caption(f"{len(selected)} file(s) selected")
        new_series = st.selectbox("Assign series", SERIES_LABELS, key="folder_series")
        if st.button("Apply to selected", type="primary", key="folder_apply"):
            run_id = _run_id("manual-folder-classify")
            with conn.cursor() as cur:
                for sha in selected["sha256"]:
                    cur.execute(
                        "UPDATE files SET series = %s, series_conf = 1.0 WHERE sha256 = %s",
                        (new_series, sha),
                    )
                    db.insert_receipt(
                        cur,
                        sha,
                        run_id,
                        "MANUAL_CLASSIFY",
                        result=new_series,
                        log_path=target,
                        ran_at=datetime.now(timezone.utc),
                    )
            conn.commit()
            st.success(f"Classified {len(selected)} files as {new_series}.")
            st.rerun()


def me_sidecar_page() -> None:
    st.header(":material/account_tree: Master Equation sidecar")
    conn = db_connection()

    claim_df = pd.read_sql("SELECT * FROM me_claims", conn)
    st.subheader("Governing claim")
    st.dataframe(claim_df, hide_index=True)

    counts_df = pd.read_sql(
        """
        SELECT status, kind, COUNT(*) AS n
        FROM me_presentations
        GROUP BY status, kind
        ORDER BY kind, status
        """,
        conn,
    )
    st.subheader("Presentations by status and kind")
    st.dataframe(counts_df, hide_index=True)

    drift_df = pd.read_sql(
        """
        SELECT drift_type, path, detail, detected_at
        FROM me_drift
        ORDER BY detected_at DESC
        LIMIT 200
        """,
        conn,
    )
    st.subheader(f"Drift items ({len(drift_df)} shown, max 200)")
    st.dataframe(drift_df, hide_index=True)


def main() -> None:
    st.title("Theophysics Corpus Admin")
    page = st.sidebar.radio(
        "View",
        ["Overview", "Unclassified review", "Folder batch classify", "ME sidecar"],
    )

    if page == "Overview":
        overview_page()
    elif page == "Unclassified review":
        unclassified_page()
    elif page == "Folder batch classify":
        folder_batch_page()
    else:
        me_sidecar_page()


if __name__ == "__main__":
    main()
