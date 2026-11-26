"""Urban Company | Evidence Discovery Engine (Step 1.4.2).

Start with: streamlit run app.py
No logged-in app scraping. This app analyzes uploaded/public evidence paraphrases.
"""
from __future__ import annotations

import hashlib
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from insights import QUESTIONS, OPPORTUNITIES, join_predictions, research_evidence, question_status, segment_counts, opportunity_table, validate_imported_predictions

from engine import (
    DEFAULT_MODEL, HUMAN_FIELDS, TAXONOMY, check_evidence, csv_bytes,
    eligible_rows, evaluation_table, groq_classify, read_csv_file, read_csv_text,
    records_by_theme, source_mix, validate_golden,
)

ROOT = Path(__file__).parent
st.set_page_config(page_title="Urban Company | AI Evidence Discovery", layout="wide", page_icon="🔎")
st.markdown("""<style>
.block-container {padding-top: 1.6rem; max-width: 1300px;}
[data-testid=\"stMetric\"] {background: #F1F5F4; padding: 14px; border-radius: 9px;}
hr {margin: 1rem 0;}
</style>""", unsafe_allow_html=True)


def config_value(name: str, fallback: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except (FileNotFoundError, KeyError):
        pass
    return os.environ.get(name, fallback)


st.title("Urban Company — AI Evidence Discovery")
st.caption("Research upgrade · Public Indian home-service evidence · Behavioural analysis, not sentiment scoring")

with st.sidebar:
    st.header("Evidence inputs")
    st.caption("The 37-record starter batch and approved golden set are bundled. Upload newer CSVs to replace either one.")
    evidence_upload = st.file_uploader("AI input CSV", type="csv", key="evidence_csv")
    golden_upload = st.file_uploader("Human golden set CSV", type="csv", key="golden_csv")
    prediction_upload = st.file_uploader("Previously exported AI predictions CSV (optional)", type="csv", key="predictions_csv", help="Restore authentic completed Groq predictions after a Streamlit session reset. These are validated against current source gates.")
    st.divider()
    st.header("AI configuration")
    key_from_secrets = config_value("GROQ_API_KEY")
    if key_from_secrets:
        api_key = key_from_secrets
        st.success("Groq API key configured in app secrets")
    else:
        api_key = st.text_input("Temporary Groq API key (optional)", type="password", help="Kept in this browser session; do not paste into source code or public screenshots.")
        st.info("No key configured. You can inspect and validate data; live AI calls are disabled.")
    model = config_value("GROQ_MODEL", DEFAULT_MODEL)
    st.caption(f"Model: `{model}`")
    st.caption("AI uses Groq structured outputs, not legacy deprecated model IDs.")
    st.divider()
    st.warning("Only public, permitted content or your own paraphrases. Do not upload invoices, addresses, phone numbers or other personal documents.")

try:
    evidence_bytes = evidence_upload.getvalue() if evidence_upload is not None else (ROOT / "data/ai_input_37.csv").read_bytes()
    gold_bytes = golden_upload.getvalue() if golden_upload is not None else (ROOT / "data/golden_set_20.csv").read_bytes()
    rows = read_csv_text(evidence_bytes)
    golden = read_csv_text(gold_bytes)
    validation = check_evidence(rows)
    golden_check = validate_golden(golden, rows)
except (ValueError, UnicodeDecodeError) as exc:
    st.error(f"Input validation failed: {exc}")
    st.stop()

fingerprint = hashlib.sha256(evidence_bytes + b"|" + gold_bytes).hexdigest()
if st.session_state.get("input_signature") != fingerprint:
    st.session_state["input_signature"] = fingerprint
    st.session_state["ai_predictions"] = {}
    st.session_state["ai_errors"] = {}
    st.session_state["human_corrections"] = {}
    st.session_state["verified_conditional"] = []
    st.session_state["verified_hold"] = []
    st.session_state["predictions_import_signature"] = None

st.sidebar.header("Source verification gate")
conditional = [r for r in rows if "conditional" in r.get("source_gate", "").lower()]
held = [r for r in rows if "hold" in r.get("source_gate", "").lower()]
verified_conditional = set(st.sidebar.multiselect(
    "Verified conditional review links", [r["record_id"] for r in conditional],
    key="verified_conditional", help="Mark a review ID here ONLY after opening the exact individual review link and confirming its contents."))
verified_hold = set(st.sidebar.multiselect(
    "Override held rows (document first)", [r["record_id"] for r in held],
    key="verified_hold", help="Low-confidence rows must stay excluded unless new source evidence is documented."))
if verified_hold:
    hold_notes = st.sidebar.text_area("Required reason for held-source override", key="hold_override_reason")
    if len(hold_notes.strip()) < 15:
        st.sidebar.error("Document at least 15 characters before allowing held rows")
        verified_hold = set()
else:
    hold_notes = ""

eligible, rejected = eligible_rows(rows, verified_conditional, verified_hold)
eligible_ids = {r["record_id"] for r in eligible}
if prediction_upload is not None:
    upload_bytes = prediction_upload.getvalue()
    import_signature = hashlib.sha256(upload_bytes + evidence_bytes + str(sorted(eligible_ids)).encode()).hexdigest()
    if st.session_state.get("predictions_import_signature") != import_signature:
        try:
            restored, import_problems = validate_imported_predictions(read_csv_text(upload_bytes), rows, eligible_ids)
            st.session_state["ai_predictions"].update(restored)
            st.session_state["predictions_import_signature"] = import_signature
            st.session_state["prediction_import_problems"] = import_problems
        except (ValueError, UnicodeDecodeError) as exc:
            st.sidebar.error(f"Could not import predictions: {exc}")
    if st.session_state.get("prediction_import_problems"):
        with st.sidebar.expander("Excluded prediction rows"):
            st.write(st.session_state["prediction_import_problems"])
# Bundled authentic prediction export from the user's previously completed Groq run.
# Explicit opt-in is required; the app does not claim new AI calls were made.
if st.sidebar.button("Load 24 saved Groq predictions", help="Restores the recorded 24 real model outputs for research exploration. These were produced previously, not by a new API call."):
    try:
        saved = read_csv_file(ROOT / "data/ai_predictions_24.csv")
        restored, issues = validate_imported_predictions(saved, rows, eligible_ids)
        st.session_state["ai_predictions"].update(restored)
        st.sidebar.success(f"Restored {len(restored)} saved AI results")
        if issues:
            st.sidebar.warning(f"{len(issues)} imported results were excluded. Check source gates.")
    except (ValueError, OSError) as exc:
        st.sidebar.error(f"Could not load saved predictions: {exc}")
preds: dict = st.session_state["ai_predictions"]
corrections: dict = st.session_state["human_corrections"]

if not golden_check["passed"]:
    st.error("Golden-set reference is not ready: " + "; ".join(golden_check["errors"]))

m1, m2, m3, m4 = st.columns(4)
m1.metric("Evidence records", len(rows))
m2.metric("Eligible for AI now", len(eligible))
m3.metric("Golden-set records", len(golden))
m4.metric("AI predictions completed", len(preds))

st.caption("Public posts are a self-selected sample, not Urban Company booking-event data. All unproven 90-day return outcomes remain unknown.")

overview, quality_tab, ai_tab, review_tab, eval_tab, research_tab, segment_tab, opportunity_tab = st.tabs([
    "01 · Evidence", "02 · Quality gates", "03 · AI classification", "04 · Human review", "05 · Evaluation",
    "06 · Research questions", "07 · Segments", "08 · Opportunities"
])

with overview:
    st.subheader("Source mix and observed customer accounts")
    sm = source_mix(rows)
    st.write("Source breakdown: " + " · ".join(f"{v} {k}" for k, v in sm.items()))
    st.info("The original 37 records were collected from Reddit, consumer complaint pages and Trustpilot. The 11 Trustpilot reviews require individual click-through verification before use in the AI run.")
    st.warning("Do not interpret the percentage of complaints or themes as a population incidence or a 90-day repeat rate. Quiet non-returners are absent from public reviews.")
    available_categories = sorted({r["service_category"] for r in rows})
    selected_categories = st.multiselect("Filter by service category", available_categories, key="category_filter")
    subset = [r for r in rows if not selected_categories or r["service_category"] in selected_categories]
    st.dataframe([{
        "record_id": r["record_id"], "source_type": r["source_type"],
        "service_category": r["service_category"], "city": r["city"],
        "observation_paraphrase": r["observation_paraphrase"],
        "source_gate": r["source_gate"], "source_url": r["source_url"]
    } for r in subset], use_container_width=True, hide_index=True,
    column_config={"source_url": st.column_config.LinkColumn("Direct source link")})
    st.download_button("Download original AI input", csv_bytes(rows), file_name="urban_company_ai_input.csv", mime="text/csv")

with quality_tab:
    st.subheader("Deduplication, source provenance and blocking conditions")
    k1, k2, k3 = st.columns(3)
    k1.metric("Unique IDs", validation["unique_ids"])
    k2.metric("Unique source URLs", validation["unique_urls"])
    k3.metric("Data-integrity blockers", len(validation["block_ids"]))
    if validation["block_ids"]:
        st.error("The following IDs cannot be classified until corrected: " + ", ".join(sorted(validation["block_ids"])))
    st.write("**Eligibility:** Ready sources are included. Conditional sources require human verification of the direct review link. Low-confidence sources remain held unless explicitly justified.")
    st.dataframe([{"record_id": r["record_id"], "source_gate": r["source_gate"],
                   "reason": r["eligibility_reason"], "source_url": r["source_url"]}
                  for r in rejected], hide_index=True, use_container_width=True,
                 column_config={"source_url": st.column_config.LinkColumn("Source")})
    severity = Counter(i["severity"] for i in validation["issues"])
    st.caption("Checks: " + ", ".join(f"{k}: {v}" for k,v in sorted(severity.items())))
    with st.expander("View complete validation issue log"):
        st.dataframe(validation["issues"], hide_index=True, use_container_width=True)
    st.download_button("Download validation issue log", csv_bytes(validation["issues"], ["record_id", "severity", "issue"]),
                       file_name="validation_issues.csv", mime="text/csv")

with ai_tab:
    st.subheader("Live, source-grounded AI classification")
    st.caption("Only the AI-input CSV fields enter the model prompt. The human-label reference is never sent to the model.")
    if not api_key:
        st.error("A Groq API key is required for actual AI classification. The app does not fabricate predictions or substitute rule-based output.")
    if not eligible:
        st.warning("No eligible sources; verify or correct input records first.")
    # Users may run one first to inspect quality/cost before expanding.
    ready_to_run = [r for r in eligible if r["record_id"] not in preds]
    if ready_to_run:
        limit = st.number_input("Maximum new records per run", min_value=1,
                                max_value=len(ready_to_run), value=min(3, len(ready_to_run)), step=1)
    else:
        limit = 0
        st.success("All currently eligible evidence rows have an AI output.")
    send_consent = st.checkbox("I confirm these are public/permitted paraphrases and understand they are sent to Groq for processing.", key="consent")
    btn_disabled = not (api_key and eligible and golden_check["passed"] and ready_to_run and send_consent)
    if st.button("Run actual AI classification", type="primary", disabled=btn_disabled):
        run = ready_to_run[:int(limit)]
        bar = st.progress(0)
        status = st.empty()
        for i, r in enumerate(run):
            status.caption(f"Processing {i+1}/{len(run)} — {r['record_id']}")
            try:
                preds[r["record_id"]] = groq_classify(r, api_key, model)
                st.session_state["ai_errors"].pop(r["record_id"], None)
            except Exception as exc:
                st.session_state["ai_errors"][r["record_id"]] = str(exc)[:400]
                if "HTTP 429" in str(exc) or "HTTP 401" in str(exc):
                    st.error("Groq rate limit or authentication error; stopped early. Existing outputs are preserved.")
                    break
            bar.progress((i + 1) / len(run))
        status.empty()
        st.rerun()
    if st.session_state["ai_errors"]:
        with st.expander("AI errors / records not counted as classified"):
            st.json(st.session_state["ai_errors"])
    if preds:
        results = [preds[k] for k in sorted(preds)]
        st.dataframe([{"record_id": p["record_id"], "primary_theme": p["primary_theme"],
                       "behavior": p["behavior_description"], "repeat_90d_status": p["repeat_90d_status"],
                       "customer_segment": p["customer_segment"], "limitation": p["limitation"]}
                      for p in results], use_container_width=True, hide_index=True)
        theme_rows = records_by_theme(results)
        st.caption("Theme counts are only among successfully AI-classified records, not population estimates.")
        st.dataframe(theme_rows, hide_index=True, use_container_width=True)
        st.download_button("Download AI outputs", csv_bytes(results), file_name="urban_company_ai_predictions.csv", mime="text/csv")
    else:
        st.info("No live AI classifications have been generated. Once an API key is configured, start with 3 records and inspect the outputs.")

with review_tab:
    st.subheader("Human corrections to model predictions")
    st.caption("Corrections are recorded separately and never overwrite the frozen golden-set reference.")
    if not preds:
        st.info("First run the AI classifier in tab 03; no model outputs exist to review.")
    else:
        select_id = st.selectbox("Choose a classified record", sorted(preds), key="review_record")
        p = preds[select_id]
        r = next(row for row in rows if row["record_id"] == select_id)
        st.markdown("**Source observation:** " + r["observation_paraphrase"])
        st.link_button("Open original source", r["source_url"])
        st.write(f"**AI theme:** {p['primary_theme']}")
        st.write(f"**AI behaviour:** {p['behavior_description']}")
        st.write(f"**90-day status:** {p['repeat_90d_status']} · **Limitation:** {p['limitation']}")
        with st.form("review_form"):
            corrected_theme = st.selectbox("Human-reviewed theme", TAXONOMY,
                                           index=TAXONOMY.index(corrections.get(select_id, {}).get("reviewed_theme", p["primary_theme"])))
            corrected_behavior = st.text_area("Human-reviewed behaviour", value=corrections.get(select_id, {}).get("reviewed_behavior", p["behavior_description"]))
            human_decision = st.selectbox("Review decision", ["Approve AI", "Correct AI", "Reject evidence"],
                                         index=["Approve AI", "Correct AI", "Reject evidence"].index(corrections.get(select_id, {}).get("decision", "Approve AI")))
            human_reason = st.text_area("Evidence-based reviewer rationale", value=corrections.get(select_id, {}).get("rationale", ""))
            submitted = st.form_submit_button("Save review")
        if submitted:
            if human_decision in ("Correct AI", "Reject evidence") and len(human_reason.strip()) < 12:
                st.error("Corrections and rejections require a short rationale.")
            else:
                corrections[select_id] = {
                    "record_id": select_id, "source_url": r["source_url"],
                    "original_ai_theme": p["primary_theme"], "reviewed_theme": corrected_theme,
                    "original_ai_behavior": p["behavior_description"], "reviewed_behavior": corrected_behavior,
                    "decision": human_decision, "rationale": human_reason.strip(),
                    "source_gate": r["source_gate"],
                }
                st.success("Review saved in this session. Export the CSV to retain it.")
        if corrections:
            st.download_button("Download human-review audit CSV", csv_bytes(list(corrections.values())),
                               file_name="human_correction_audit.csv", mime="text/csv")
            st.caption(f"{len(corrections)} reviewed records in this session")

with eval_tab:
    st.subheader("AI agreement against the approved Golden Set")
    st.caption("Agreement is diagnostic, not proof of causal accuracy. Reference labels were reviewed with AI assistance, so evaluation is not fully blind.")
    if not golden_check["passed"]:
        st.error("Fix golden-set validation issues before evaluating.")
    else:
        evaluation, metrics = evaluation_table(list(preds.values()), golden, eligible_ids)
        q1,q2,q3,q4 = st.columns(4)
        q1.metric("Golden set", metrics["golden_total"])
        q2.metric("AI evaluated", metrics["evaluated"])
        q3.metric("Matches", metrics["matching"])
        q4.metric("Agreement", "Not measured" if metrics["agreement_rate"] is None else f"{metrics['agreement_rate']:.1%}")
        if metrics["evaluated"] != len(golden):
            st.warning(f"Only {metrics['evaluated']} of {len(golden)} golden records have live AI predictions. Do not report the partial result as full 20-record accuracy.")
        st.dataframe(evaluation, hide_index=True, use_container_width=True)
        st.download_button("Download AI vs human evaluation", csv_bytes(evaluation),
                           file_name="golden_set_agreement_audit.csv", mime="text/csv")
        mismatches = [r for r in evaluation if r["agreement"] == "mismatch"]
        if mismatches:
            st.markdown("#### Genuine disagreements to inspect")
            st.dataframe(mismatches[:10], hide_index=True, use_container_width=True)
        else:
            st.caption("No observed disagreements yet; if the sample is incomplete, more predictions may reveal disagreements.")
        st.divider()
        st.markdown("**Evaluation safeguards**")
        st.write("• AI predictions are generated from observation paraphrases, not human labels.\n\n"
                 "• Only successful, live AI calls count; unavailable or blocked rows do not count as matches.\n\n"
                 "• Each 90-day status remains unknown unless source language explicitly establishes the required timing and completion.\n\n"
                 "• Do not claim a population repeat rate from public posts.")


# Exploratory analyses depend ONLY on successfully classified, currently eligible public evidence.
classified = join_predictions(rows, list(preds.values()), eligible_ids)
with research_tab:
    st.subheader("Eight assignment research questions — evidence coverage")
    st.warning("The app reports partial signals, not completed answers where source evidence is missing. Public posts cannot determine qualified 90-day retention or distinguish silent non-returners.")
    if not classified:
        st.info("Run AI classification or upload your previously exported AI predictions CSV in the sidebar first.")
    else:
        coverage = []
        for qid, question, _ in QUESTIONS:
            matched = research_evidence(qid, classified)
            status, limitation = question_status(qid, classified)
            coverage.append({"question_id": qid, "question": question, "coverage": status, "supporting_observations": len(matched), "limitation": limitation})
        st.dataframe(coverage, use_container_width=True, hide_index=True)
        st.download_button("Download question coverage", csv_bytes(coverage), file_name="urban_company_research_question_coverage.csv", mime="text/csv")
        qid = st.selectbox("Inspect supporting evidence", [q[0] for q in QUESTIONS], format_func=lambda x:next(q[1] for q in QUESTIONS if q[0]==x))
        chosen = research_evidence(qid, classified)
        status, gap = question_status(qid, classified)
        st.markdown(f"**Coverage:** {status}. {gap}")
        if chosen:
            evidence_table = [{"record_id":r["record_id"], "source":r["source_type"], "category":r["service_category"], "city":r["city"],
                               "primary_theme":r["primary_theme"], "behavior":r.get("ai_behavior_description",""),
                               "reported_alternative":r.get("ai_external_alternative",""), "unmet_need":r.get("ai_unmet_need",""),
                               "repeat_90d":r.get("ai_repeat_90d_status","unknown"), "source_url":r["source_url"]} for r in chosen]
            st.dataframe(evidence_table, use_container_width=True, hide_index=True, column_config={"source_url":st.column_config.LinkColumn("Original source")})
            st.download_button("Download selected evidence",csv_bytes(evidence_table),file_name=f"research_{qid}_evidence.csv",mime="text/csv")
        else:
            st.info("No source-grounded supporting records in the eligible classified evidence.")
        st.caption("Source counts represent observed public posts, not the share of all customers. A theme match is a clue, not proof of expectation or repeat motive.")

with segment_tab:
    st.subheader("Descriptive comparisons by city and service category")
    st.info("These are counts of non-representative classified observations. Household type and first-acquisition channel are not recorded consistently; do not fabricate them.")
    if classified:
        dimension = st.selectbox("Compare themes by", ["service_category", "city", "source_type"], format_func=lambda x:x.replace("_"," ").title())
        summary = segment_counts(classified, dimension)
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.download_button("Download segment observations",csv_bytes(summary),file_name="urban_company_segment_theme_counts.csv",mime="text/csv")
        st.caption(f"{len(classified)} eligible classified source observations; no adjusted city/category incidence estimates.")
    else:
        st.info("Classify evidence or upload the authentic predictions CSV to view these comparisons.")

with opportunity_tab:
    st.subheader("Candidate opportunities — transparent evidence comparison")
    st.warning("Sorted by diversity of the observed source sample, NOT by estimated business impact. Effect size, segment reach and solution differentiation need primary research and validation.")
    if classified:
        candidates = opportunity_table(classified)
        st.dataframe(candidates, use_container_width=True, hide_index=True)
        st.download_button("Download candidate opportunity table",csv_bytes(candidates),file_name="urban_company_opportunity_candidates.csv",mime="text/csv")
        selected = st.selectbox("Inspect evidence for an opportunity",list(OPPORTUNITIES))
        subset = [r for r in classified if r["primary_theme"] in OPPORTUNITIES[selected]["themes"]]
        st.write(f"**Potential mechanism:** {OPPORTUNITIES[selected]['mechanism']}")
        st.write(f"**Interview test:** {OPPORTUNITIES[selected]['validation']}")
        st.dataframe([{"record_id":r["record_id"],"theme":r["primary_theme"],"observed_behavior":r.get("ai_behavior_description",""),"source_url":r["source_url"]} for r in subset],
                     use_container_width=True,hide_index=True,column_config={"source_url":st.column_config.LinkColumn("Source")})
        st.markdown("**Still unknown:** true 90-day repeat outcomes; target-segment prevalence; causal effect on consideration or booking; customers with no further service need.")
    else:
        st.info("Run classification or import a genuine prediction export first.")

st.divider()
st.caption("Urban Company fellowship research prototype · No account access, no booking actions, no scraping · Research questions and opportunity comparisons are exploratory and require human validation.")
