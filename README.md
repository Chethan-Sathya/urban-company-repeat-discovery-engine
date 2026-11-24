# Urban Company — AI Evidence Discovery Engine

**Step 1.4.2 | Build + evaluate structured behaviour classification**

This is a deployable Streamlit application. It reads a CSV of public home-service customer evidence, detects data-quality issues, classifies eligible observations via Groq's structured-output API, preserves human review edits, and evaluates AI theme agreement against an independently approved 20-record reference set.

It **does not** scrape Urban Company, access customer accounts, book services, or message service professionals. It cannot calculate Urban Company's actual 90-day repeat-booking rate.

## Included files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit user interface |
| `engine.py` | Input checks, source gates, Groq AI classification and evaluation |
| `data/ai_input_37.csv` | Unlabelled model input (37 source observations) |
| `data/golden_set_20.csv` | Approved manually reviewed reference (never included in AI prompt) |
| `data/validation_log_37.csv` | Existing source and deduplication checks |
| `tests/test_engine.py` | Offline unit tests |
| `.streamlit/secrets.toml.example` | Example configuration; **never** commit real keys |
| `EVIDENCE_LOG_STATUS.md` | Current, honest evidence and evaluation status |

## 1. Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

The app opens on localhost. Without an API key, evidence exploration, validation and golden-set checking work, but **AI classifications are disabled**. This is intentional: the engine never invents predictions or a simulated agreement score.

## 2. Configure the Groq API key

Obtain an active Groq API key in your Groq account, then either:

```bash
# macOS / Linux
export GROQ_API_KEY='your-key-here'

# PowerShell
$env:GROQ_API_KEY='your-key-here'
```

Or create a local `.streamlit/secrets.toml` from the example, with actual `GROQ_API_KEY`. This file is excluded by `.gitignore`.

By default the app uses `openai/gpt-oss-20b`, which Groq documents as supporting strict structured outputs. The legacy `llama-3.3-70b-versatile` was deprecated for non-enterprise use in 2026, so do not copy the old Groww assignment's model setting blindly. You can override `GROQ_MODEL` only with a currently supported, schema-capable model.

## 3. Upload, validate and classify

1. Start with the bundled 37-record input and 20-record golden set.
2. On **Evidence**, inspect original links and descriptions.
3. On **Quality gates**, check duplicate IDs, URLs and source objects. A unique URL is *not* proof that the customer account is independent.
4. The default source gate includes **24 ready/provisional** observations. **11 Trustpilot** direct-review links remain conditional until individually checked; **2 low-confidence** observations remain held.
5. In the sidebar, only mark individual Trustpilot IDs verified after opening those direct review links. A held record requires a written explanation before overriding.
6. On **AI classification**, run 3 records first. Only public evidence paraphrases and category/city metadata are sent to Groq; reference labels are not sent.
7. Inspect structured output. Where qualifying timing and completion are not explicit, 90-day status remains `unknown`.
8. On **Human review**, save approval/corrections/rejection decisions and export the review-audit CSV.
9. On **Evaluation**, see how many of the 20 gold records were actually classified, calculate agreement only on real AI outputs, inspect mismatches, and download the audit.
10. Save exported CSVs. Streamlit session data is not a persistent database and will be lost if the session is reset.

**Important:** A self-reported repeat customer is not a *confirmed qualifying 90-day repeater*. Completion, timing, and exclusions (refunds/warranty/redos) must all be established.

## 4. Deploy on Streamlit Community Cloud

1. Create a new GitHub repository, e.g. `urban-company-repeat-discovery-engine`.
2. Upload **all contents of this folder**, preserving `data/`, `tests/`, and `.streamlit/config.toml`.
3. Do **not** upload `.streamlit/secrets.toml` or any personal API keys.
4. Open [Streamlit Community Cloud](https://share.streamlit.io), choose **Create app / Deploy**, and select your GitHub repository.
5. Set the entrypoint to `app.py` and configure secrets in **Advanced settings**:

```toml
GROQ_API_KEY = "YOUR_REAL_KEY"
GROQ_MODEL = "openai/gpt-oss-20b"
```

6. Deploy and open the public app in an incognito window.
7. Test the full chain: 1 real model classification, review correction, 20-record evaluation (requires all 20 real predictions), CSV download, and a fresh session.
8. Add the app link to the final deck and the Evidence Log only after the app is actually deployed and tested.

References: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy ; https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management ; https://console.groq.com/docs/structured-outputs ; https://console.groq.com/docs/changelog

## 5. Quality and privacy caveats

- The original sample has 24 Reddit observations, 11 Trustpilot reviews, and 2 complaint-site observations. It does not represent the UC customer population; complaint-heavy source bias and silent non-returners remain major gaps.
- Source review flags are inherited; automated checks cannot independently prove review authenticity, source geography, completed bookings, or cohort membership.
- The golden-set manual decisions were reviewed after AI suggestions were shown, so this is **not a fully blind** reference set. Disclose that limitation in the final Evidence Log.
- 20 reference records are from Reddit and consumer complaints, not Trustpilot. Evaluate a second, separately human-labelled Trustpilot sample before claiming model performance generalizes to those reviews.
- The tool analyzes paraphrases, not raw review text. Do not claim quotations or detailed customer histories beyond those paraphrases.
- The source gate is strict by default; users can approve conditional sources after real checking. Any override must be documented and should not be treated as automated source verification.
- User-supplied evidence must be public/allowed. No personal documents, addresses, phone numbers, customer screenshots or invoices.
- AI evaluations measure **theme agreement**, not the causal effect on 90-day repeat bookings.

## 6. Tests and reproducibility

```bash
python -m unittest discover -s tests -v
```

All tests operate offline with mocked AI responses. They verify JSON schema handling, reference-label isolation, safe unknown repeat status, duplicates, source gating and evaluation math. Passing tests does **not** imply the remote Groq API was successfully called or that the UI has been deployed.

## Next assignment step

**Step 1.4.3 — Evidence-backed opportunity dashboard:** use the reviewed AI output to compare customer behaviours with denominators, sample sizes, evidence quality, positive/negative source balance and business-outcome influence. Do not fabricate an uplift estimate.
