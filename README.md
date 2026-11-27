# Urban Company Discovery Engine V2

Upgrade of the existing Streamlit/Groq research engine. V1 remains unchanged until you deliberately deploy this package. This is a public-evidence research tool, not the customer-facing MVP or a booking analytics system.

## Included files
- `app.py`: Streamlit dashboard (six tabs)
- `engine.py`: adapted V1 classifier, date validation, 10-theme taxonomy, eight question extracts, repeat-outcome guardrail
- `workflow.py`: approval gates, reference evaluation, descriptive opportunity analysis
- `data/evidence_master.csv`: screened 97 candidates (includes original 37)
- `data/golden_v1.csv`: 20 previously approved AI-assisted reference items
- `data/golden_v2_pending.csv`: 20 labelled Phase 2 items; 17 source-checked pending human approval, 3 on hold
- `data/holdout_optional.csv`: 15 optional unlabelled candidates; not evaluated by default
- `test_v2.py`: offline unit tests using a mocked API response, not live AI predictions

## Run locally (Windows PowerShell)
Extract the ZIP, open its `uc_discovery_v2` folder in VS Code, and open Terminal:
```powershell
py -m pip install -r requirements.txt
py -m unittest -v test_v2.py
py -m streamlit run app.py
```
Paste your Groq key in the app sidebar, or use `.streamlit/secrets.toml` locally (never commit this file).

## Deploy in existing repository without replacing V1
1. Open your existing GitHub repository `Chethan-Sathya/urban-company-repeat-discovery-engine`.
2. Create a branch called `v2` from `main` (GitHub branch selector). Keep `main` unchanged.
3. On `v2`, upload the extracted package files and `data` directory at repository root, including `app.py`, `engine.py`, `workflow.py`, `requirements.txt`, `README.md`, `test_v2.py`, `.gitignore`. Commit to `v2` only. Existing extra V1 files can remain.
4. In Streamlit Community Cloud create a separate app for the same repository, branch `v2`, main file `app.py`. Add `GROQ_API_KEY = "YOUR_KEY"` in the app's secrets. Do not paste the real key in GitHub.
5. Launch V2, verify the dashboard and classify 1 approved record. If successful, run the remaining records in batches. Keep V1 live until V2 passes your checks. A branch can later be merged; no merge is necessary for testing.

## Research workflow
1. Evidence & approval: inspect sources and approval gates. Initial 20 baseline approvals are carried forward, not fresh source verification. 17 Phase 2 candidates are source-checked but require your sign-off. You can select them for batch approval **only after** accepting their observations. Three source-checked holds and two pre-existing low-confidence holds remain excluded. Other candidates need source and human approval. Source approval is not proof of a real booking.
2. Evaluation: finalize the approved Phase 2 reference labels before seeing new AI predictions. The 20 V1 and 17 potentially eligible Phase 2 records are AI-assisted references; report separately. Optional holdout should be independently labelled and approved before predictions. Export reviewed references and evidence master.
3. Classify: use strict approval mode for final evidence. Optional exploratory mode includes pending ready/source-checked candidates but not holds. API failures remain errors; no rule-based fallback or fabricated predictions. Classifications are grounded in supplied paraphrases, not fetched live pages.
4. Research questions: inspect extracted answers and supporting IDs, links, paraphrases and limitations. Blank support is reported as a research gap. Q6 cannot establish comparative 90-day cohort behaviour; Q7 is descriptive.
5. Segments & opportunities: approved classified evidence only. Opportunity counts are first-hand unmet-need signals, not causal impact estimates or severity. Human review and primary research are needed to prioritize.
6. Evaluation: exact theme agreement, evaluation coverage, per-class precision/recall/F1 and macro F1 over the union of observed and predicted labels among evaluated items. Compare V1 vs V2 on the same 20 records using the same conditions; compare the 17 new items separately. Historical 65% is not V2 performance. Manual behavioural and grounding assessment is separate.
7. Human corrections: correct theme and behaviour, record rationale and grounding verdict. Unsupported audited outputs excluded from analytical views. Raw predictions remain intact for evaluation. Research question extracts are not automatically corrected; inspect separately.
8. Export before closing. Session state is temporary; saved evidence/references can be reuploaded. Prediction re-import is not implemented. Use exports for the assignment evidence log.

## Validation scope
Collection window: 26 Nov 2025 through 26 Nov 2026 (month-only dates preserved; boundary months flagged). All 97 rows pass structural blocking checks. At package creation strict routing permits 20 and exploratory routing permits 48. Five are on hold (including three Phase 2 source checks); 72 pending. No qualifying 90-day outcomes are established in supplied data. The current public-paraphrase classifier conservatively always returns unknown for this metric; it is not suitable for verified booking-event cohort computation.

Offline tests cover record count/unique URLs, date parsing and window, evidence gates, prompt leakage, forced unknown repeat outcome, and agreement/coverage. No live Groq run or Streamlit runtime smoke test was performed in the build environment (Streamlit unavailable; no user API credentials). Run the local/deployed smoke test before claiming successful deployment or model performance. No source links were newly checked for this build. Source access can change.
