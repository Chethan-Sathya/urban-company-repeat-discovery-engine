import unittest,json
from pathlib import Path
from engine import *
from workflow import *
P=Path(__file__).parent/'data'
class Tests(unittest.TestCase):
    def setUp(self):
        self.g1=read_csv_file(P/'golden_v1.csv');self.g2=read_csv_file(P/'golden_v2_pending.csv');self.rows=prepare(read_csv_file(P/'evidence_master.csv'),self.g2,self.g1)
    def test_data(self):
        self.assertEqual(len(self.rows),97);self.assertEqual(check_evidence(self.rows)['unique_urls'],97);self.assertFalse(check_evidence(self.rows)['block_ids'])
    def test_gates(self):
        a,_=route(self.rows);self.assertEqual(len(a),20)
        b,_=route(self.rows,True);self.assertFalse({'UE047','UE065','UE077'} & {r['record_id'] for r in b});self.assertGreater(len(b),20)
        self.assertEqual(len(approved_reference(self.g2,self.rows)),0)
    def test_prompt_and_safety(self):
        r=self.rows[0]; ans={k:(v['enum'][0] if 'enum' in v else 'not established') for k,v in PROPERTIES.items()}
        ans['repeat_90d_status']='confirmed_repeat'
        def mock(payload):
            content=json.loads(payload['messages'][1]['content']);self.assertEqual(set(content),{'record_id','service_category','city_as_recorded','observation_paraphrase'})
            return {'choices':[{'message':{'content':json.dumps(ans)}}]}
        p=groq_classify(r,'fake-test-key',request_fn=mock);self.assertEqual(p['repeat_90d_status'],'unknown');self.assertEqual(p['prediction_status'],'AI success')
    def test_opportunities_and_eval(self):
        g=approved_reference(self.g1,self.rows);p=[{'record_id':g[0]['record_id'],'prediction_status':'AI success','primary_theme':g[0]['manual_label']}]
        _,m,_=score(p,g,{x['record_id'] for x in g});self.assertEqual(m['agreement_rate'],1);self.assertEqual(m['evaluated'],1);self.assertEqual(m['coverage'],.05)
        self.assertFalse(analysis_rows([{'record_id':'UE038','prediction_status':'AI success'}],self.rows,True))
    def test_month(self):
        r=dict(self.rows[0],published_date='2026-01',date_precision='month');self.assertFalse(check_evidence([r])['block_ids'])
    def test_outside_window(self):
        r=dict(self.rows[0],published_date='2025-01',date_precision='month');self.assertTrue(check_evidence([r])['block_ids'])
if __name__=='__main__':unittest.main(verbosity=2)
