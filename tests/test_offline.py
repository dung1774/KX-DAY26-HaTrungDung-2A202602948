"""Offline unit tests for the non-live parts of Day 26."""

import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


function_calling = load_module(
    "weather_function_calling",
    "01-function-calling/weather_function_calling.py",
)
registry_client = load_module(
    "registry_client",
    "03-production/registry_client.py",
)


class FunctionCallingTests(unittest.TestCase):
    def test_mock_weather_remains_local_mock_data(self):
        result = json.loads(function_calling.get_weather("Đà Nẵng"))
        self.assertEqual(result["city"], "Đà Nẵng")
        self.assertEqual(result["nhiệt_độ"], "30°C")
        self.assertEqual(result["thời_tiết"], "nhiều mây")

    def test_missing_gemini_key_has_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Thiếu Gemini API key"):
                function_calling._create_client()


class RegistryTests(unittest.TestCase):
    def test_search_and_best_match_choose_highest_active_semver(self):
        registry = registry_client.ToolRegistry()
        results = registry.search(tag="weather")
        self.assertEqual({item["tool"] for item in results}, {"get_weather", "get_weather_v2"})
        self.assertEqual(registry.best_match(tag="weather")["tool"], "get_weather_v2")

        registry.tools["get_weather_v10"] = {
            "description": "Deprecated future weather tool",
            "parameters": {},
            "tags": ["weather"],
            "server": "weather-v2",
            "version": "10.0.0",
            "deprecated": True,
        }
        self.assertEqual(registry.best_match(tag="weather")["tool"], "get_weather_v2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
