"""Deterministic tests for distinct shared DAX limits; no timing sleeps."""
import os
import time
import unittest
from unittest.mock import patch
import duckdb
from dax_budget import DaxBudgetExceeded, check_budget, limits
from dax_engine import evaluate_visual
from dax_sql import UnsupportedSql


class BudgetTests(unittest.TestCase):
    def test_time_and_steps_are_distinct(self):
        budget = {'steps': 4, 'started': 100, 'deadline': 108, 'seconds': 8, 'max_steps': 10, 'location': 'Revenue, group 2/3'}
        with patch('dax_budget.time.monotonic', return_value=109):
            with self.assertRaisesRegex(DaxBudgetExceeded, r'time limit exceeded.*8 seconds.*9.00s.*Revenue, group 2/3'):
                check_budget(budget)
        budget['deadline'] = 200
        budget['steps'] = 10
        with patch('dax_budget.time.monotonic', return_value=101):
            with self.assertRaisesRegex(DaxBudgetExceeded, r'step limit exceeded.*10 steps'):
                check_budget(budget, 1)

    def test_configuration_and_invalid_limits(self):
        with patch.dict(os.environ, {'D2PBI_DAX_SECONDS': '45', 'D2PBI_DAX_STEPS': '42'}):
            self.assertEqual(limits(), (45, 42))
        with patch.dict(os.environ, {'D2PBI_DAX_SECONDS': '0'}):
            with self.assertRaises(ValueError): limits()

    def test_shared_budget_and_success_diagnostics(self):
        model = {'tables': [], 'measures': [{'TableName': 'M', 'Name': 'Value', 'Expression': '1+2'}]}
        payload = {'fields': [{'Measure': {'Property': 'Value'}}], 'groups': [{'scope':[['T','A']]},{'scope':[['T','B']]}]}
        con = duckdb.connect()
        try:
            with patch.dict(os.environ, {'D2PBI_DAX_STEPS': '4'}), patch('dax_sql.evaluate_groups',side_effect=UnsupportedSql), patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql):
                with self.assertRaisesRegex(DaxBudgetExceeded, r'step limit exceeded.*group 2/2'):
                    evaluate_visual(con, model, payload)
            result = evaluate_visual(con, model, payload)
            self.assertEqual(result['rows'], [[3], [3]])
            self.assertGreater(result['evaluation']['steps'], 0)
        finally: con.close()


if __name__ == '__main__': unittest.main()
