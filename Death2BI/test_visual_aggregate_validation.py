import unittest
from unittest.mock import patch
from dax_engine import evaluate_visual
from dax_sql import UnsupportedSql


class VisualAggregateValidationTests(unittest.TestCase):
    def test_visual_reference_is_rejected_before_model_execution(self):
        for expression in ({'SelectRef': {'ExpressionName': 'M.Value'}}, {}, None, {'Column': {'Property': 'Value'}}):
            with self.subTest(expression=expression), self.assertRaisesRegex(ValueError, 'expected a qualified model column'):
                evaluate_visual(None, {}, {'groups': [{}], 'fields': [{'Aggregation': {'Expression': expression, 'Function': 1}}]})

    def test_unknown_aggregate_is_rejected(self):
        column = {'Column': {'Expression': {'SourceRef': {'Entity': 'F'}}, 'Property': 'Value'}}
        with self.assertRaisesRegex(ValueError, 'Unsupported model aggregation'):
            evaluate_visual(None, {}, {'groups': [{}], 'fields': [{'Aggregation': {'Expression': column, 'Function': 999}}]})

    def test_staged_sql_fallback_is_observable(self):
        def decline(con, model, payload, budget):
            budget['sqlSafetyFallbacks'] = 1
            budget['sqlSafetyReasons'] = ['nested grouped iterator']
            raise UnsupportedSql('Staged evaluation required')
        payload = {'groups': [{}], 'fields': [{'Measure': {'Property': 'Value'}}]}
        with patch('dax_sql.evaluate_groups', decline), patch('dax_sql.evaluate_scalar', return_value=2):
            result = evaluate_visual(None, {'tables': [], 'measures': []}, payload)
        self.assertEqual(result['rows'], [[2]])
        self.assertEqual(result['evaluation']['sqlSafetyFallbacks'], 1)
        self.assertEqual(result['evaluation']['sqlSafetyReasons'], ['nested grouped iterator'])


if __name__ == '__main__':
    unittest.main()
