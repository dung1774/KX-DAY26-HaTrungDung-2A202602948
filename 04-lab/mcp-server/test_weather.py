"""Offline tests for WeatherAPI handling; no external API calls are made."""

import unittest
from unittest.mock import AsyncMock, patch

import httpx

import weather


class _AsyncClientContext:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class WeatherToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_api_key_returns_tool_error(self):
        with patch.object(weather, "API_KEY", None):
            result = await weather.get_current_weather("Hanoi")
        self.assertIn("key is not configured", result)

    async def test_current_weather_formats_mocked_api_response(self):
        payload = {
            "location": {"name": "Hanoi", "region": "Ha Noi", "country": "Vietnam"},
            "current": {
                "temp_c": 29,
                "temp_f": 84.2,
                "feelslike_c": 31,
                "feelslike_f": 87.8,
                "condition": {"text": "Partly cloudy"},
                "humidity": 78,
                "wind_kph": 9,
                "wind_mph": 5.6,
                "wind_dir": "SE",
                "pressure_mb": 1008,
                "uv": 5,
                "vis_km": 10,
                "last_updated": "2026-10-14 15:00",
            },
        }
        with patch.object(weather, "make_weather_request", AsyncMock(return_value=payload)):
            result = await weather.get_current_weather("Hanoi")
        self.assertIn("Current Weather for Hanoi", result)
        self.assertIn("Temperature: 29°C", result)

    async def test_forecast_rejects_days_outside_demo_range(self):
        mocked_request = AsyncMock()
        with patch.object(weather, "make_weather_request", mocked_request):
            result = await weather.get_forecast("Hanoi", 4)
        self.assertIn("integer from 1 to 3", result)
        mocked_request.assert_not_awaited()

    async def test_malformed_api_response_does_not_crash_tool(self):
        with patch.object(
            weather,
            "make_weather_request",
            AsyncMock(return_value={"location": {}, "current": {}}),
        ):
            result = await weather.get_current_weather("Hanoi")
        self.assertIn("invalid API response", result)

    async def test_http_error_is_sanitized(self):
        request = httpx.Request("GET", "https://api.weatherapi.com/v1/current.json")
        response = httpx.Response(400, request=request)
        error = httpx.HTTPStatusError("bad request", request=request, response=response)
        client = AsyncMock()
        client.get.side_effect = error

        with (
            patch.object(weather, "API_KEY", "test-key"),
            patch.object(
                weather.httpx,
                "AsyncClient",
                return_value=_AsyncClientContext(client),
            ),
        ):
            with self.assertRaisesRegex(weather.WeatherAPIError, "City was not found"):
                await weather.make_weather_request("current.json", {"q": "invalid"})

    async def test_timeout_is_handled(self):
        client = AsyncMock()
        client.get.side_effect = httpx.ReadTimeout("timeout")
        with (
            patch.object(weather, "API_KEY", "test-key"),
            patch.object(
                weather.httpx,
                "AsyncClient",
                return_value=_AsyncClientContext(client),
            ),
        ):
            with self.assertRaisesRegex(weather.WeatherAPIError, "timed out"):
                await weather.make_weather_request("current.json", {"q": "Hanoi"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
