"""Offline model selection tests; no credential or API request is needed."""
import os
import unittest
from unittest.mock import patch

from model_config import DEFAULT_MODEL_ID, runtime_model_id


class ModelSelectionTests(unittest.TestCase):
    def test_default_without_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(runtime_model_id(), 'gemini-3.8-flash')
            self.assertEqual(runtime_model_id(), DEFAULT_MODEL_ID)

    def test_override_is_trimmed_and_read_at_call_time(self):
        with patch.dict(os.environ, {'GEMINI_MODEL_ID': '  offline-test-model  '}, clear=True):
            self.assertEqual(runtime_model_id(), 'offline-test-model')
            os.environ['GEMINI_MODEL_ID'] = 'second-offline-model'
            self.assertEqual(runtime_model_id(), 'second-offline-model')

    def test_empty_override_fails_before_model_construction(self):
        for empty in ('', '  '):
            with self.subTest(value=empty), patch.dict(os.environ, {'GEMINI_MODEL_ID': empty}, clear=True):
                with self.assertRaisesRegex(ValueError, 'nonempty'):
                    runtime_model_id()


if __name__ == '__main__':
    unittest.main()
