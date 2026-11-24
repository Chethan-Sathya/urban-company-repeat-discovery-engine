"""Offline regression tests; cannot manufacture live AI success or accuracy."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import (TAXONOMY, OUTPUT_SCHEMA, check_evidence, csv_bytes, eligible_rows,
                    evaluation_table, explicit_repeat_evidence, groq_classify,
                    read_csv_file, read_csv_text, validate_golden)

HERE = Path(__file__).resolve().parents[1]


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_csv_file(HERE / 'data/ai_input_37.csv')
        cls.golden = read_csv_file(HERE / 'data/golden_set_20.csv')

    def test_37_records_no_exact_duplication(self):
        report = check_evidence(self.rows)
        self.assertEqual(report['count'], 37)
        self.assertEqual(report['unique_ids'], 37)
        self.assertEqual(report['unique_urls'], 37)
        self.assertFalse(report['block_ids'])

    def test_gate_default_24_11_2(self):
        ready, rejected = eligible_rows(self.rows)
        self.assertEqual(len(ready), 24)
        self.assertEqual(len(rejected), 13)

    def test_gate_only_selected_conditional(self):
        conditional_ids = [r['record_id'] for r in self.rows if 'conditional' in r['source_gate'].lower()]
        ready, rejected = eligible_rows(self.rows, {conditional_ids[0]})
        self.assertEqual(len(ready), 25)
        self.assertEqual(len(rejected), 12)

    def test_golden_has_20_and_ue018(self):
        gold = validate_golden(self.golden, self.rows)
        self.assertTrue(gold['passed'], gold['errors'])
        self.assertEqual(gold['count'], 20)
        self.assertEqual(next(r['manual_label'] for r in self.golden if r['record_id'] == 'UE018'),
                         'Service suitability and scope')

    def test_ai_prompt_no_reference_data_leakage(self):
        row = self.rows[0]
        captured = {}
        sample = {
            'primary_theme': TAXONOMY[0],
            'behavior_description': 'Compares potential service providers',
            'customer_segment': 'prospective_user',
            'booking_completion': 'not_reported',
            'repeat_90d_status': 'unknown',
            'first_time_status': 'unknown',
            'need_type': 'unknown',
            'external_alternative': 'Local AC technicians',
            'unmet_need': 'Confidence in service diagnosis',
            'journey_stage': 'provider_consideration',
            'evidence_basis': 'Compares providers before selection',
            'limitation': 'No completed UC booking or 90-day outcome established',
        }
        def mock_fn(payload):
            captured['payload'] = payload
            return {'choices': [{'message': {'content': json.dumps(sample)}}]}
        pred = groq_classify(row, 'dummy', request_fn=mock_fn)
        self.assertEqual(pred['prediction_status'], 'AI success')
        self.assertEqual(pred['repeat_90d_status'], 'unknown')
        sent = json.dumps(captured['payload'])
        self.assertNotIn('manual_label', sent)
        self.assertNotIn('human_correction_notes', sent)
        self.assertEqual(captured['payload']['response_format']['json_schema']['strict'], True)
        self.assertEqual(len(OUTPUT_SCHEMA['required']), 12)

    def test_forced_unknown_repeat_claim(self):
        row = self.rows[0]
        sample = {k: '' for k in OUTPUT_SCHEMA['properties']}
        sample.update({
            'primary_theme': TAXONOMY[0], 'customer_segment': 'unknown',
            'booking_completion': 'unclear', 'repeat_90d_status': 'confirmed_repeat',
            'first_time_status': 'unknown', 'need_type': 'unknown',
            'journey_stage': 'unknown',
        })
        p = groq_classify(row, 'dummy', request_fn=lambda _: {'choices': [{'message': {'content': json.dumps(sample)}}]})
        self.assertEqual(p['repeat_90d_status'], 'unknown')
        self.assertIn('override', p['limitation'])

    def test_eval_no_predictions_returns_no_accuracy(self):
        table, result = evaluation_table([], self.golden)
        self.assertEqual(result['evaluated'], 0)
        self.assertIsNone(result['agreement_rate'])
        self.assertEqual(len(table), 20)

    def test_eval_only_actual_success(self):
        table, result = evaluation_table([
            {'record_id': 'UE001', 'primary_theme': self.golden[0]['manual_label'], 'prediction_status': 'AI success'},
            {'record_id': 'UE002', 'primary_theme': TAXONOMY[-1], 'prediction_status': 'AI success'},
            {'record_id': 'UE003', 'primary_theme': TAXONOMY[0], 'prediction_status': 'mock'},
        ], self.golden)
        self.assertEqual(result['evaluated'], 2)
        self.assertEqual(result['matching'], 1)
        self.assertEqual(result['agreement_rate'], 0.5)

    def test_roundtrip_csv(self):
        b = csv_bytes(self.rows)
        self.assertEqual(len(read_csv_text(b)), 37)

    def test_thread_duplicate_url_detected(self):
        rows = [dict(self.rows[0]), dict(self.rows[0])]
        rows[1]['record_id'] = 'TEST002'
        a = check_evidence(rows)
        self.assertTrue(a['block_ids'])

if __name__ == '__main__':
    unittest.main()
