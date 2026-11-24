# AI Evidence Log — current status (24 November 2026)

## Data inputs
- 37 unique public observation records and 37 distinct source URLs (source-level link inspection still required for 11 Trustpilot reviews).
- Reddit: 24; Trustpilot: 11; consumer complaint sites: 2.
- Default source gate: 24 ready/provisional, 11 conditionally held pending individual Trustpilot confirmation, 2 low-confidence held.
- 20 human-reviewed golden-set records, all Approved, UE018 classified as `Service suitability and scope`.
- Golden set is not fully blind because AI suggestions were visible during the manual-review workflow; disclose this limitation.
- No evidence record independently establishes a qualifying completed 90-day repeat booking or verified 90-day non-return.

## Classifier implementation
- Single primary theme selected from 10 allowed taxonomy values (9 observed human themes plus `Other / unclear`).
- Extracts customer segment, reported completion, 90-day repeat status, first-time status, need type, outside alternatives, journey stage, limitation, and evidence basis.
- Groq model: `openai/gpt-oss-20b` with strict JSON schema.
- Golden set never transmitted to classifier; reference labels only used after predictions.
- Unsupported model claims of repeat within 90 days are reset to `unknown` by a conservative deterministic safety gate.
- Model errors are retained visibly rather than converted into fake AI classifications.

## Tested results so far
- Offline unit tests: **10 / 10 passed**.
- Live Groq classification: **NOT RUN** (no account/API credentials in this working environment).
- AI vs golden-set matches: **NOT YET MEASURED**.
- Model disagreement examples: **NOT YET AVAILABLE**; collect 2–3 actual AI corrections after live model evaluation.
- Streamlit full UI smoke test: **NOT EXECUTED** (Streamlit package absent from this working environment).
- Public Streamlit deployment: **NOT DEPLOYED**.

## Key evidence and methodological limitations
1. Public comments oversample dissatisfied or motivated users; silent non-returners require interviews.
2. All observed 90-day repeat outcomes unknown; do not calculate a repeat-rate metric from the dataset.
3. A separate 5–6 interview sample must contain confirmed repeaters and non-repeaters, across categories, who completed UC bookings in the past 6 months.
4. App Store/Google Play reviews with untraceable per-review links remain excluded from the accepted 37-record batch.
5. Trustpilot links are ID-specific but need manual page-level review confirmation.
6. Model thematic agreement is not a substitute for primary research and measured product impact.
