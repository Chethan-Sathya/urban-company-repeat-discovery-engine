"""Urban Company Discovery Engine V2 — Streamlit research workspace."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import streamlit as st
from engine import (REQUIRED, HUMAN_FIELDS, TAXONOMY, QUESTIONS, DEFAULT_MODEL, read_csv_text, csv_bytes, check_evidence, groq_classify)
from workflow import prepare, route, approved_reference, score, analysis_rows, opportunities

ROOT=Path(__file__).parent
st.set_page_config(page_title='Urban Company | Discovery V2',page_icon='🔎',layout='wide')
st.title('Urban Company | Discovery Engine V2')
st.caption('Consumer Growth · 90-day repeat completion · Public evidence research')
st.info('Public reviews are directional, not booking-event data. Repeat usage signals do not establish qualifying 90-day repeat outcomes. No causal or population retention estimate is produced.')

def secret(k,default=''):
    try: return st.secrets.get(k,default)
    except Exception: return default

def load(upload,name):
    return read_csv_text(upload.getvalue() if upload is not None else (ROOT/'data'/name).read_bytes())

with st.sidebar:
    st.header('Inputs & configuration')
    master_up=st.file_uploader('Evidence master / saved review CSV',type='csv')
    gold1_up=st.file_uploader('V1 reference CSV',type='csv')
    gold2_up=st.file_uploader('Phase 2 reference CSV',type='csv')
    holdout_up=st.file_uploader('Optional independent holdout CSV',type='csv')
    key=secret('GROQ_API_KEY') or st.text_input('Groq API key',type='password')
    model=st.text_input('Model',value=secret('GROQ_MODEL',DEFAULT_MODEL))
    exploratory=st.checkbox('Allow provisional exploration',value=False,help='Allows ready or source-checked pending observations to be classified. Final opportunity rankings still require human approval.')
    st.caption('No API calls until you select Run classification. Never commit your API key.')
try:
    raw=load(master_up,'evidence_master.csv'); g1=load(gold1_up,'golden_v1.csv'); g2=load(gold2_up,'golden_v2_pending.csv')
    holdout=read_csv_text(holdout_up.getvalue()) if holdout_up else []
    rows=raw if all(k in raw[0] for k in ('source_check','review_decision','review_notes','screening')) else prepare(raw,g2,g1)
    check_evidence(rows)
except Exception as e:
    st.error(f'Input error: {e}'); st.stop()
# New uploads invalidate in-session state. AI predictions tied to actual input + model.
context=hashlib.sha256(csv_bytes(rows)+csv_bytes(g1)+csv_bytes(g2)+csv_bytes(holdout)).hexdigest()
if st.session_state.get('context')!=context:
    st.session_state.update(context=context, review_rows=rows, predictions=[], corrections={}, gold2=g2)
rows=st.session_state.review_rows; g2=st.session_state.gold2
report=check_evidence(rows)
eligible,excluded=route(rows,exploratory)
strict,_=route(rows,False)
cols=st.columns(5)
for col,label,value in zip(cols,['Candidate records','Human approved / eligible','Current run eligible','Structural blockers','Confirmed 90-day outcomes'],[len(rows),len(strict),len(eligible),len(report['block_ids']),0]): col.metric(label,value)
tabs=st.tabs(['1 · Evidence & approval','2 · Classify','3 · Research questions','4 · Segments & opportunities','5 · Evaluation','6 · Human correction & export'])
with tabs[0]:
    st.subheader('Review evidence and preserve source traceability')
    st.caption('Approval requires both a verified observation and an explicit reviewer decision. The imported V1 approvals are carried forward; 17 Phase 2 source checks are not human approvals. Held sources stay excluded until corrected and explicitly verified.')
    st.dataframe(rows,hide_index=True,use_container_width=True,column_config={'source_url':st.column_config.LinkColumn('Source URL')})
    if report['issues']: st.dataframe(report['issues'],hide_index=True,use_container_width=True)
    with st.form('review'):
        ids=[r['record_id'] for r in rows]; rid=st.selectbox('Record to review',ids)
        st.caption('Select the record ID using the table above. Enter verification only after checking the source and observation.')
        check=st.selectbox('Source content check',['Verified','Pending','Hold','Rejected'])
        decision=st.selectbox('Reviewer decision',['Pending','Approved','Hold','Rejected'])
        notes=st.text_area('Reviewer notes / rationale')
        if st.form_submit_button('Save record decision'):
            if decision=='Approved' and (check!='Verified' or not notes.strip()): st.error('Verified content and reviewer rationale required for approval.')
            else:
                for r in rows:
                    if r['record_id']==rid: r.update(source_check=check,review_decision=decision,review_notes=notes)
                st.rerun()
    with st.form('bulk_verified'):
        checked_ids=[r['record_id'] for r in rows if r['source_check']=='Verified' and r['review_decision']=='Pending']
        selected=st.multiselect('Already source-checked records to approve',checked_ids)
        attest=st.checkbox('I personally reviewed these selected observations and accept them')
        if st.form_submit_button('Approve selected evidence'):
            if not selected or not attest: st.error('Select records and explicitly confirm your review.')
            else:
                for r in rows:
                    if r['record_id'] in selected: r.update(review_decision='Approved',review_notes=r['review_notes']+' | Human reviewer accepted via batch approval.')
                st.rerun()
    st.download_button('Download reviewed evidence master',csv_bytes(rows),'evidence_reviewed.csv','text/csv')
    st.subheader('Excluded from current run'); st.dataframe(excluded,hide_index=True,use_container_width=True)
with tabs[1]:
    st.subheader('Groq structured behavioural classification')
    st.caption('Only record ID, category, city and observation are sent to the model. Human labels, approval notes and screening rationale are never included in the prompt.')
    sig=hashlib.sha256(csv_bytes([{k:r.get(k,'') for k in REQUIRED} for r in rows])+model.encode()).hexdigest()
    if st.session_state.get('prediction_sig')!=sig:
        st.session_state.update(prediction_sig=sig,predictions=[],corrections={})
    active={r['record_id'] for r in eligible}
    batch=st.number_input('Maximum records this run',min_value=1,max_value=max(1,len(eligible)),value=min(20,max(1,len(eligible))))
    if st.button('Run classification',disabled=not eligible or not key, type='primary'):
        existing={p['record_id']:p for p in st.session_state.predictions if p['prediction_status']=='AI success'}
        pending=[r for r in eligible if r['record_id'] not in existing][:int(batch)]
        log={p['record_id']:p for p in st.session_state.predictions}
        progress=st.progress(0.0); status=st.empty()
        for i,r in enumerate(pending):
            status.write(f"Classifying {r['record_id']} ({i+1}/{len(pending)})")
            try: p=groq_classify(r,key,model)
            except Exception as e: p={'record_id':r['record_id'],'source_url':r['source_url'],'model_id':model,'prediction_status':'AI error','error':str(e)[:400]}
            p['run_utc']=datetime.now(timezone.utc).isoformat();log[r['record_id']]=p;st.session_state.predictions=list(log.values())
            progress.progress((i+1)/len(pending))
            if p['prediction_status']=='AI error' and any(x in p['error'] for x in ('HTTP 401','HTTP 403','HTTP 429')):
                st.warning('Stopped on API authentication/rate-limit error. Resolve and run again.');break
        status.write('Run finished. Failed records can be retried. No simulated predictions.')
    preds=[p for p in st.session_state.predictions if p['record_id'] in active]
    st.write(f"Successful predictions: {sum(p['prediction_status']=='AI success' for p in preds)} / {len(eligible)} eligible records")
    st.dataframe(preds,hide_index=True,use_container_width=True)
    if preds: st.download_button('Download raw AI evidence log',csv_bytes(preds),'ai_evidence_log.csv','text/csv')
# Review corrections remain separate from raw AI predictions used in evaluation.
corrected=[{**p,**st.session_state.corrections.get(p['record_id'],{})} for p in preds]
strict_data=analysis_rows(corrected,rows,True)
explore_data=analysis_rows(corrected,rows,False)
with tabs[2]:
    st.subheader('Eight assignment research questions')
    use_provisional=st.checkbox('View exploratory answers (includes pending records)',value=False)
    data=explore_data if use_provisional else strict_data
    st.caption('Answers are candidate extracts from public paraphrases, not verified causal explanations. Q6 cannot compare confirmed 90-day cohorts without primary research. Q7 provides descriptive segment context only.')
    export=[]
    for k,q in QUESTIONS.items():
        answers=[{'record_id':r['record_id'],'answer':r[k],'source_url':r['source_url'],'observation':r['observation_paraphrase'],'limitation':r['limitation']} for r in data if r.get(k,'').strip().lower() not in ('','not established')]
        with st.expander(f'{q} — {len(answers)}/{len(data)} observations with a candidate answer'):
            if answers: st.dataframe(answers,hide_index=True,use_container_width=True,column_config={'source_url':st.column_config.LinkColumn('Source')})
            else: st.write('Research gap — no supported answer in the current classified records.')
        export += [{'question':q,**a} for a in answers]
    if export: st.download_button('Export research question evidence',csv_bytes(export),'research_questions.csv','text/csv')
with tabs[3]:
    st.subheader('Approved-evidence analysis')
    st.caption('Only approved, verified successful records enter this dashboard. Counts describe this convenience sample. They do not estimate retention, severity or causal impact.')
    if strict_data:
        from collections import Counter
        for field,label in [('repeat_signal','Reported repeat / switching signal'),('service_category','Service category'),('city','City'),('customer_segment','Customer evidence type'),('source_type','Source mix')]:
            st.write(label); st.bar_chart([{'segment':k,'records':v} for k,v in Counter(r.get(field,'Unknown') for r in strict_data).items()],x='segment',y='records')
        ranked=opportunities(strict_data)
        st.subheader('Unmet-need hypotheses by frequency')
        st.caption('Denominator: approved classified first-hand observations with a candidate unmet need, excluding contextual supplementary records. Distinct source types indicate breadth, not proof. Human review is required before product prioritization.')
        st.dataframe(ranked,hide_index=True,use_container_width=True)
        if ranked: st.download_button('Export opportunity signals',csv_bytes(ranked),'opportunities.csv','text/csv')
    else: st.info('Run classification on approved evidence first.')
with tabs[4]:
    st.subheader('Reference evaluation — raw AI output only')
    st.caption('V1 historical agreement: 13/20 (65%). Re-run both models on the same approved reference records for a comparable result. Phase 1 and Phase 2 labels were AI-assisted; optional holdout must be independently labelled.')
    st.write('Phase 2 reference approval (separate from source approval)')
    st.dataframe(g2,hide_index=True,use_container_width=True)
    with st.form('gold2'):
        gr=st.selectbox('Reference record',[r['record_id'] for r in g2]); confirmed=st.checkbox('I reviewed and accept the source, manual label, behaviour and notes')
        if st.form_submit_button('Approve Phase 2 reference'):
            if not confirmed: st.error('Explicit review confirmation required.')
            else:
                r=next((r for r in rows if r['record_id']==gr),None); gold=next(x for x in g2 if x['record_id']==gr)
                if not r or r['source_check']!='Verified' or r['review_decision']!='Approved': st.error('Approve verified evidence in tab 1 first.')
                elif gold.get('manual_label') not in TAXONOMY or not gold.get('manual_behavior','').strip(): st.error('Complete valid manual label and behaviour first.')
                else: gold['human_review_status']='Approved';st.rerun()
    with st.form('bulk_gold2'):
        accepted={r['record_id'] for r in strict}
        candidates=[g['record_id'] for g in g2 if g['record_id'] in accepted and g.get('human_review_status')=='Pending' and g.get('manual_label') in TAXONOMY and g.get('manual_behavior','').strip()]
        selected_gold=st.multiselect('Approved evidence references to finalize',candidates)
        accept_labels=st.checkbox('I accept the selected manual labels, behaviour and notes before seeing V2 predictions')
        if st.form_submit_button('Finalize selected references'):
            if not selected_gold or not accept_labels: st.error('Select references and confirm review.')
            else:
                for g in g2:
                    if g['record_id'] in selected_gold: g['human_review_status']='Approved'
                st.rerun()
    st.download_button('Export Phase 2 reference',csv_bytes(g2),'golden_v2_reviewed.csv','text/csv')
    for title,gold in [('V1 reference (AI-assisted)',g1),('Phase 2 reference (AI-assisted)',g2),('Optional holdout (independence must be confirmed)',holdout)]:
        if not gold: continue
        approved=approved_reference(gold,rows)
        table,m,detail=score(preds,approved,active)
        st.write(f'**{title}** — {len(approved)}/{len(gold)} approved and source eligible')
        a,b,c=st.columns(3)
        a.metric('Exact agreement',f"{m['agreement_rate']:.1%}" if m['agreement_rate'] is not None else 'Not evaluated')
        b.metric('Coverage',f"{m['evaluated']}/{len(approved)}")
        c.metric('Macro F1 (evaluated labels)',f"{m['macro_f1']:.3f}" if m['macro_f1'] is not None else 'Not evaluated')
        st.dataframe(table,hide_index=True,use_container_width=True);st.dataframe(detail,hide_index=True,use_container_width=True)
        if table: st.download_button('Export evaluation',csv_bytes(table),f'evaluation_{title.split()[0]}.csv','text/csv',key='export_'+title)
    st.caption('Theme agreement is not behavioural extraction accuracy or source grounding accuracy. Those require human audit. Missing AI predictions are reflected in coverage.')
with tabs[5]:
    st.subheader('Human correction log')
    good=[p for p in preds if p['prediction_status']=='AI success']
    if good:
        with st.form('correct'):
            rid=st.selectbox('Prediction record',[p['record_id'] for p in good]); label=st.selectbox('Corrected primary theme',TAXONOMY); behavior=st.text_area('Corrected behaviour'); notes=st.text_area('Correction rationale'); grounded=st.selectbox('Grounding audit',['Not assessed','Supported','Unsupported'])
            if st.form_submit_button('Save correction'):
                if not behavior.strip() or not notes.strip(): st.error('Behaviour and rationale required.')
                else: st.session_state.corrections[rid]={'primary_theme':label,'behavior_description':behavior,'correction_notes':notes,'grounding_audit':grounded};st.rerun()
        st.dataframe(corrected,hide_index=True,use_container_width=True)
        st.download_button('Export reviewed AI evidence',csv_bytes(corrected),'reviewed_ai_evidence.csv','text/csv')
        logs=[{'record_id':k,**v} for k,v in st.session_state.corrections.items()]
        if logs: st.download_button('Export correction log',csv_bytes(logs),'human_corrections.csv','text/csv')
        st.caption('Corrections change theme and behaviour in the reviewed view only; question extracts still require review. Raw predictions remain unchanged for evaluation.')
    else: st.info('Classify evidence first.')
    st.warning('Review decisions and predictions live in the browser session. Export before closing; upload saved evidence and reference CSVs to restore decisions. Raw prediction re-import is not implemented in this version.')
