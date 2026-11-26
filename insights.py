"""Evidence-bound research synthesis: no inferred 90-day outcomes or population claims."""
from __future__ import annotations
from collections import Counter, defaultdict

QUESTIONS = [
    ("Q1", "What do customers expect once a booking is complete?", "post_service"),
    ("Q2", "How and when is a new home-service need recognized?", "need_trigger"),
    ("Q3", "Who do customers consider for the same or another service?", "provider_choice"),
    ("Q4", "Why do customers book again or not return?", "repeat_reason"),
    ("Q5", "What do customers do outside Urban Company?", "outside_action"),
    ("Q6", "What separates 90-day repeaters from non-repeaters?", "repeat_comparison"),
    ("Q7", "How do patterns differ by category, city, household and acquisition source?", "segments"),
    ("Q8", "Which unmet needs recur across conversations?", "unmet"),
]

OPPORTUNITIES = {
    "Service discovery and consideration": {
        "themes": {"Provider choice confidence", "Service suitability and scope"},
        "mechanism": "Greater consideration when another genuine need arises",
        "validation": "Did an existing UC customer have another need but fail to consider UC?",
    },
    "Service decision confidence": {
        "themes": {"Provider choice confidence", "Repair diagnosis confidence", "Service suitability and scope"},
        "mechanism": "More confident decisions when a service is genuinely appropriate",
        "validation": "Which uncertainty changed the provider or service decision?",
    },
    "Off-platform choice and workarounds": {
        "themes": {"Off-platform alternatives and workarounds"},
        "mechanism": "Understand why genuine needs are met outside UC",
        "validation": "Which alternative was actually used, and why?",
    },
    "Post-service recovery and trust": {
        "themes": {"Service recovery and resolution", "Professional trust and safety", "Hygiene and safety concerns"},
        "mechanism": "Address customer uncertainty or unresolved service expectations",
        "validation": "Did a previous incident affect an actual later provider decision?",
    },
    "Repeat-need continuity": {
        "themes": {"Repeat usage and continuity", "Positive service experience"},
        "mechanism": "Understand how existing customer routines transfer across needs",
        "validation": "What triggered a later qualifying booking, and in what interval?",
    },
}


def join_predictions(evidence, predictions, allowed_ids=None):
    """Join actual successful predictions; never count unmatched, gated or errored rows."""
    source = {r["record_id"]: r for r in evidence}
    out = []
    seen = set()
    for p in predictions:
        rid = p.get("record_id", "")
        if rid in seen or rid not in source or p.get("prediction_status") != "AI success":
            continue
        if allowed_ids is not None and rid not in allowed_ids:
            continue
        seen.add(rid)
        r = source[rid]
        out.append({**r, **{f"ai_{k}": v for k, v in p.items()}, "primary_theme": p.get("primary_theme", "")})
    return out


def research_evidence(question_id, classified):
    """Relevant records are exploratory signals, not automatically proof of the question's answer."""
    def found(row, field):
        return row.get("ai_"+field, "").strip().lower() not in {"", "unknown", "not established", "none", "not_reported", "not reported", "not applicable", "n/a"}
    if question_id == "Q1":
        return [r for r in classified if r["primary_theme"] in {"Service recovery and resolution", "Positive service experience", "Professional trust and safety", "Hygiene and safety concerns"}]
    if question_id == "Q2":
        return [r for r in classified if found(r, "need_type")]
    if question_id == "Q3":
        return [r for r in classified if found(r, "external_alternative") or r["primary_theme"] == "Provider choice confidence"]
    if question_id == "Q4":
        return [r for r in classified if r["primary_theme"] in {"Repeat usage and continuity", "Off-platform alternatives and workarounds", "Service recovery and resolution"}]
    if question_id == "Q5":
        return [r for r in classified if found(r, "external_alternative")]
    if question_id == "Q6":
        return [r for r in classified if r.get("ai_repeat_90d_status") in {"confirmed_repeat", "confirmed_no_repeat"}]
    if question_id == "Q7":
        return [r for r in classified if r.get("city") or r.get("service_category")]
    if question_id == "Q8":
        return [r for r in classified if found(r, "unmet_need")]
    return []


def question_status(question_id, classified):
    relevant = research_evidence(question_id, classified)
    if question_id == "Q6":
        repeat = sum(r.get("ai_repeat_90d_status") == "confirmed_repeat" for r in relevant)
        non = sum(r.get("ai_repeat_90d_status") == "confirmed_no_repeat" for r in relevant)
        return ("Limited self-reported comparison" if repeat and non else "Insufficient evidence", "Verified booking histories and both 90-day outcome groups are required. The classifier's self-report labels do not validate booking events.")
    if question_id == "Q4":
        return "Partial / not verified", "Theme signals do not establish why an eligible customer repeated or did not repeat within 90 days."
    if question_id == "Q1":
        return "Partial / indirect", "Service feedback is not a direct measurement of what customers expected after completion."
    if question_id == "Q7":
        return "Partial / descriptive", "City and service category can be tabulated; household type and acquisition channel are not systematically recorded."
    if len(relevant) < 3:
        return "Insufficient evidence", "Fewer than three relevant classified observations; additional source diversity and interviews needed."
    return "Partial / exploratory", "These are non-representative public self-reports; review each source before using the signal as a finding."


def segment_counts(classified, dimension):
    counts = defaultdict(lambda: Counter())
    for r in classified:
        group = (r.get(dimension) or "Unknown").strip()
        counts[group][r.get("primary_theme") or "Other / unclear"] += 1
    return [{"segment": seg, "theme": theme, "observations": n}
            for seg, themes in sorted(counts.items()) for theme, n in sorted(themes.items())]


def opportunity_table(classified):
    """Descriptive comparison; no ungrounded impact or addressable-population scoring."""
    output = []
    for name, spec in OPPORTUNITIES.items():
        matches = [r for r in classified if r.get("primary_theme") in spec["themes"]]
        sources = {r.get("source_type", "Unknown") for r in matches}
        categories = {r.get("service_category", "Unknown") for r in matches}
        urls = {r.get("source_url") for r in matches}
        output.append({"opportunity": name, "observations": len(matches),
                       "distinct_source_urls": len(urls), "source_types": len(sources),
                       "service_categories": len(categories),
                       "possible_metric_mechanism": spec["mechanism"],
                       "interview_validation_question": spec["validation"],
                       "evidence_readiness": "Multiple-source signal" if len(sources)>=2 and len(urls)>=3 else "Limited / single-source signal"})
    return sorted(output, key=lambda x:(-x["source_types"], -x["distinct_source_urls"], x["opportunity"]))


def validate_imported_predictions(imported, evidence, allowed_ids):
    """Reject non-source-gated or suspicious imported predictions; validate content and IDs."""
    from engine import TAXONOMY, explicit_repeat_evidence
    source={r["record_id"]:r for r in evidence}
    valid={}
    problems=[]
    for i,p in enumerate(imported,1):
        rid=p.get("record_id","")
        if rid in valid:
            problems.append(f"Row {i}: duplicate prediction for {rid}");continue
        if rid not in source:
            problems.append(f"Row {i}: unknown record {rid}");continue
        if rid not in allowed_ids:
            problems.append(f"Row {i}: source currently gated {rid}");continue
        if p.get("prediction_status")!="AI success" or p.get("primary_theme") not in TAXONOMY:
            problems.append(f"Row {i}: invalid AI result for {rid}");continue
        if p.get("source_url")!=source[rid].get("source_url"):
            problems.append(f"Row {i}: source link mismatch for {rid}");continue
        if p.get("repeat_90d_status","unknown") not in {"unknown","confirmed_repeat","confirmed_no_repeat"}:
            problems.append(f"Row {i}: invalid repeat status for {rid}");continue
        clean=dict(p)
        if not explicit_repeat_evidence(source[rid]["observation_paraphrase"],clean.get("repeat_90d_status","unknown")):
            clean["repeat_90d_status"]="unknown"
            clean["limitation"]=(clean.get("limitation","")+" | Import safety override: unsupported 90-day status").strip()
        valid[rid]=clean
    return valid, problems
