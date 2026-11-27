"""Review gates, descriptive analysis and independent reference evaluation."""
from collections import Counter
from datetime import datetime
from engine import REQUIRED,HUMAN_FIELDS,TAXONOMY,QUESTIONS,check_evidence,evaluation_table


def prepare(master, phase2, baseline):
    checked={r['record_id']:r for r in phase2}
    base={r['record_id']:r for r in baseline if r['human_review_status'].lower()=='approved'}
    rows=[]
    for raw in master:
        r={k:raw.get(k,'') for k in REQUIRED}
        rid=r['record_id']; c=checked.get(rid,{})
        try: r['published_date']=datetime.strptime(r['published_date'],'%d-%m-%Y').date().isoformat()
        except ValueError: pass
        r['screening']=raw.get('supplementary_screening','Not screened')
        if r['screening'].startswith('Original'):
            r['screening']='Baseline - review scope'
        r['source_check']='Pending'; r['review_decision']='Pending'; r['review_notes']=''
        if rid in base and 'ready' in r['source_gate'].lower():
            r.update(source_check='Verified',review_decision='Approved',review_notes='Carried forward from approved V1 reference; not a fresh source audit.')
        if c:
            r['source_check']=c.get('source_verification','Pending'); r['review_notes']=c.get('human_correction_notes','')
            if r['source_check']=='Hold': r['review_decision']='Hold'
            elif c.get('human_review_status')=='Approved': r['review_decision']='Approved'
            # Normalize documented source-checked dates, without guessing a day.
            d=c.get('published_date','')
            if d:
                try:
                    r['published_date']=datetime.strptime(d,'%d-%m-%Y').date().isoformat(); r['date_precision']='day'
                except ValueError: pass
        if 'hold' in r['source_gate'].lower(): r['review_decision']='Hold'
        rows.append(r)
    return rows


def route(rows, exploratory=False):
    report=check_evidence(rows); allowed=[]; excluded=[]
    for r in rows:
        decision=r.get('review_decision','Pending'); checked=r.get('source_check','Pending'); gate=r['source_gate'].lower()
        reason=''
        if r['record_id'] in report['block_ids']: reason='Structural blocker'
        elif decision in ('Hold','Rejected') or checked in ('Hold','Rejected'): reason='Held or rejected'
        elif decision=='Approved' and checked=='Verified': pass
        elif exploratory and ('ready' in gate or checked=='Verified') and 'hold' not in gate: pass
        else: reason='Approval / source verification pending'
        if reason: excluded.append({**r,'eligibility_reason':reason})
        else: allowed.append(r)
    return allowed,excluded


def approved_reference(gold, evidence, phase2=False):
    allowed={r['record_id'] for r in route(evidence,False)[0]}
    return [{k:r.get(k,'') for k in HUMAN_FIELDS} for r in gold if r.get('human_review_status')=='Approved' and r['record_id'] in allowed and r.get('manual_label') in TAXONOMY and r.get('manual_behavior','').strip()]


def score(preds, gold, eligible):
    table, metrics=evaluation_table(preds,gold,set(eligible))
    valid=[r for r in table if r['agreement'] in ('match','mismatch')]
    labels=sorted({r['manual_label'] for r in valid}|{r['ai_label'] for r in valid})
    details=[]
    for label in labels:
        tp=sum(r['manual_label']==label and r['ai_label']==label for r in valid)
        fp=sum(r['manual_label']!=label and r['ai_label']==label for r in valid)
        fn=sum(r['manual_label']==label and r['ai_label']!=label for r in valid)
        p=tp/(tp+fp) if tp+fp else 0; rec=tp/(tp+fn) if tp+fn else 0
        details.append(dict(theme=label,precision=p,recall=rec,f1=2*p*rec/(p+rec) if p+rec else 0,support=tp+fn))
    metrics['macro_f1']=sum(r['f1'] for r in details)/len(details) if details else None
    return table,metrics,details


def analysis_rows(preds, rows, approved_only=True):
    lookup={r['record_id']:r for r in rows}
    out=[]
    for p in preds:
        r=lookup.get(p['record_id'])
        if not r or p.get('prediction_status')!='AI success' or p.get('grounding_audit')=='Unsupported': continue
        if approved_only and not (r['source_check']=='Verified' and r['review_decision']=='Approved'): continue
        out.append({**p,**{k:r[k] for k in ('source_type','city','service_category','screening','review_decision','observation_paraphrase')}})
    return out


def opportunities(rows):
    # Counts only; no fabricated causal impact or severity score.
    rows=[r for r in rows if r.get('customer_segment')=='first_hand_UC_user' and r.get('unmet_need','').strip().lower() not in ('','not established') and not r.get('screening','').startswith('Supporting')]
    groups={}
    for r in rows: groups.setdefault(r['primary_theme'],[]).append(r)
    return sorted([{'theme':k,'observations':len(v),'distinct_source_types':len({r['source_type'] for r in v}),'share_of_eligible_unmet_need_signals':len(v)/len(rows),'record_ids':', '.join(r['record_id'] for r in v)} for k,v in groups.items()],key=lambda x:(-x['observations'],x['theme']))
