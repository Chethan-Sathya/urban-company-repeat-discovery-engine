import csv
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine import read_csv_file, eligible_rows
from insights import join_predictions, question_status, research_evidence, opportunity_table, segment_counts, validate_imported_predictions

class InsightsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=read_csv_file(ROOT/'data/ai_input_37.csv')
        cls.eligible,_=eligible_rows(cls.rows,set(),set())
        cls.ids={r['record_id'] for r in cls.eligible}
        cls.predictions=read_csv_file(ROOT/'data/ai_predictions_24.csv')
        cls.valid,cls.issues=validate_imported_predictions(cls.predictions,cls.rows,cls.ids)
        cls.merged=join_predictions(cls.rows,list(cls.valid.values()),cls.ids)
    def test_37_evidence_24_predictions(self):
        self.assertEqual(len(self.rows),37)
        self.assertEqual(len(self.ids),24)
        self.assertEqual(len(self.merged),24)
        self.assertEqual(len(self.issues),0)
    def test_no_confirmed_repeat_comparison(self):
        self.assertEqual(len(research_evidence('Q6',self.merged)),0)
        self.assertEqual(question_status('Q6',self.merged)[0],'Insufficient evidence')
    def test_segment_count_exhaustiveness(self):
        self.assertEqual(sum(x['observations'] for x in segment_counts(self.merged,'city')),24)
    def test_opportunity_rows_are_descriptive(self):
        table=opportunity_table(self.merged)
        self.assertEqual(len(table),5)
        self.assertNotIn('impact_score',table[0])
    def test_held_prediction_is_rejected(self):
        p=dict(self.predictions[0]);p['record_id']='UE023';p['source_url']=next(r['source_url'] for r in self.rows if r['record_id']=='UE023')
        v, issues=validate_imported_predictions([p],self.rows,self.ids)
        self.assertFalse(v)
        self.assertTrue(issues)
    def test_unsupported_repeat_overridden(self):
        p=dict(self.predictions[0]);p['repeat_90d_status']='confirmed_repeat'
        v,_=validate_imported_predictions([p],self.rows,self.ids)
        self.assertEqual(v['UE001']['repeat_90d_status'],'unknown')
    def test_source_url_mismatch_rejected(self):
        p=dict(self.predictions[0]);p['source_url']='https://example.org'
        v,issues=validate_imported_predictions([p],self.rows,self.ids)
        self.assertEqual(v,{})
        self.assertTrue(issues)

if __name__=='__main__': unittest.main()
