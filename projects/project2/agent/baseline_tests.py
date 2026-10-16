"""Validate the active professor baseline and Agno compatibility offline."""
import ast
import os
import unittest
from unittest.mock import patch
from professor_baseline import construct_reference, reference_model_ids, value
from model_config import DEFAULT_MODEL_ID, REFERENCE_MODEL_ID


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.dict(os.environ).start()
        os.environ.pop('GEMINI_MODEL_ID', None)

    def test_all_reference_agents_construct_without_network(self):
        agents, active, prompt = construct_reference()
        self.assertEqual(len(agents), 6)
        self.assertEqual(active, 'agno2')
        self.assertIn('San Francisco', prompt)
        self.assertEqual({agent.model.id for agent in agents.values()}, {DEFAULT_MODEL_ID})
        self.assertEqual(type(agents[active].tools[0]).__name__, 'ReasoningTools')

    def test_finance_adapter_enables_professor_tools(self):
        agents, _, _ = construct_reference()
        funcs = agents['agno1'].tools[1].functions
        for name in ('get_current_stock_price', 'get_analyst_recommendations',
                     'get_company_info', 'get_company_news'):
            self.assertIn(name, funcs)

    def test_image_adapter_preserves_identity(self):
        agents, _, _ = construct_reference()
        self.assertEqual(agents['agno3'].id, 'image-to-text')

    def test_parser_rejects_arbitrary_calls(self):
        with self.assertRaises(ValueError): value(ast.parse("open('/etc/passwd')", mode='eval').body)

    def test_reference_model_remains_historical(self):
        self.assertEqual(reference_model_ids(), {REFERENCE_MODEL_ID})

    def test_runtime_override_reaches_all_baseline_models(self):
        os.environ['GEMINI_MODEL_ID'] = 'offline-baseline-test-model'
        agents, _, _ = construct_reference()
        self.assertEqual({agent.model.id for agent in agents.values()}, {'offline-baseline-test-model'})


if __name__ == '__main__': unittest.main()
