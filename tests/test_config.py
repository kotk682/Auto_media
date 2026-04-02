import unittest
from unittest.mock import patch

from app.core.config import DEFAULT_LLM_SLOW_LOG_THRESHOLD_MS, Settings


class SettingsValidationTests(unittest.TestCase):
    def test_negative_llm_slow_log_threshold_falls_back_to_default_with_warning(self):
        with patch("app.core.config.logger.warning") as warning_mock:
            settings = Settings(_env_file=None, llm_slow_log_threshold_ms=-1)

        self.assertEqual(settings.llm_slow_log_threshold_ms, DEFAULT_LLM_SLOW_LOG_THRESHOLD_MS)
        warning_mock.assert_called_once()
        self.assertIn("falling back to default", warning_mock.call_args.args[0])

    def test_zero_llm_slow_log_threshold_is_allowed(self):
        settings = Settings(_env_file=None, llm_slow_log_threshold_ms=0)
        self.assertEqual(settings.llm_slow_log_threshold_ms, 0)


if __name__ == "__main__":
    unittest.main()
