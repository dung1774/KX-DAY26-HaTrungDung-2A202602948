from typing import Any

import logging
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).with_name(".env"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# httpx logs complete query URLs at INFO level. WeatherAPI authenticates with a
# query parameter, so suppress those request lines to keep the key out of logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

# Initialize FastMCP server
port = int(os.getenv("PORT", 8085))
mcp = FastMCP("weather", host="0.0.0.0", port=port)

# Constants
WEATHERAPI_BASE = "https://api.weatherapi.com/v1"
USER_AGENT = "weather-app/1.0"

# Get API key from environment variable
API_KEY = os.getenv("WEATHERAPI_KEY")


class WeatherAPIError(RuntimeError):
    """Lỗi WeatherAPI đã được rút gọn an toàn để trả về tool caller."""


async def make_weather_request(endpoint: str, params: dict[str, str]) -> dict[str, Any]:
    """Make a request to the WeatherAPI with proper error handling."""
    if not API_KEY:
        raise WeatherAPIError(
            "WeatherAPI key is not configured. Set WEATHERAPI_KEY in the environment "
            "or 04-lab/mcp-server/.env."
        )

    headers = {"User-Agent": USER_AGENT}
    request_params = {**params, "key": API_KEY}
    url = f"{WEATHERAPI_BASE}/{endpoint}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url,
                headers=headers,
                params=request_params,
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise WeatherAPIError("WeatherAPI returned an invalid response.")
            return data
        except httpx.TimeoutException as exc:
            logger.warning("WeatherAPI request timed out")
            raise WeatherAPIError("WeatherAPI request timed out.") from exc
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            logger.warning("WeatherAPI returned HTTP %s", status)
            if status in (401, 403):
                message = "WeatherAPI rejected the API key."
            elif status == 400:
                message = "City was not found or the request was invalid."
            elif status == 429:
                message = "WeatherAPI quota has been exceeded."
            else:
                message = f"WeatherAPI returned HTTP {status}."
            raise WeatherAPIError(message) from e
        except httpx.RequestError as e:
            logger.warning("Unable to connect to WeatherAPI: %s", type(e).__name__)
            raise WeatherAPIError("Unable to connect to WeatherAPI.") from e
        except ValueError as exc:
            logger.warning("WeatherAPI returned non-JSON data")
            raise WeatherAPIError("WeatherAPI returned an invalid response.") from exc

@mcp.tool()
async def get_current_weather(city: str) -> str:
    """Get current weather conditions for a city.

    Args:
        city: City name (e.g., "Hanoi", "Haiphong", "Danang", "Brisbane", "Sydney")
    """
    city = city.strip()
    if not city:
        return "❌ City must not be empty."

    params = {
        "q": city,
        "aqi": "no"
    }

    try:
        data = await make_weather_request("current.json", params)
        current = data["current"]
        location = data["location"]
        return f"""
Current Weather for {location['name']}, {location['region']}, {location['country']}:

Temperature: {current['temp_c']}°C ({current['temp_f']}°F)
Feels like: {current['feelslike_c']}°C ({current['feelslike_f']}°F)
Condition: {current['condition']['text']}
Humidity: {current['humidity']}%
Wind: {current['wind_kph']} km/h ({current['wind_mph']} mph) {current['wind_dir']}
Pressure: {current['pressure_mb']} mb
UV Index: {current['uv']}
Visibility: {current['vis_km']} km

Last updated: {current['last_updated']}
"""
    except WeatherAPIError as exc:
        return f"❌ Unable to fetch current weather for {city}: {exc}"
    except (KeyError, TypeError) as exc:
        logger.warning("WeatherAPI current response is missing required fields: %s", exc)
        return f"❌ Unable to fetch current weather for {city}: invalid API response."

@mcp.tool()
async def get_forecast(city: str, days: int = 3) -> str:
    """Get weather forecast for a city.

    Args:
        city: City name (e.g., "Hanoi", "Haiphong", "Danang", "Brisbane", "Sydney", "Melbourne")
        days: Number of days to forecast (1-3 for free tier, max 10 for paid)
    """
    city = city.strip()
    if not city:
        return "❌ City must not be empty."
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 3:
        return "❌ Forecast days must be an integer from 1 to 3."

    params = {
        "q": city,
        "days": str(days),
        "aqi": "no",
        "alerts": "no"
    }
    
    try:
        data = await make_weather_request("forecast.json", params)
        location = data["location"]
        forecast_days = data["forecast"]["forecastday"]

        forecasts = [
            f"Weather Forecast for {location['name']}, "
            f"{location['region']}, {location['country']}:"
        ]
        for day in forecast_days:
            day_data = day["day"]
            date = day["date"]
            forecast = f"""
{date}:
High: {day_data['maxtemp_c']}°C ({day_data['maxtemp_f']}°F)
Low: {day_data['mintemp_c']}°C ({day_data['mintemp_f']}°F)
Condition: {day_data['condition']['text']}
Chance of Rain: {day_data['daily_chance_of_rain']}%
Max Wind: {day_data['maxwind_kph']} km/h
UV Index: {day_data['uv']}
"""
            forecasts.append(forecast)

        return "\n---\n".join(forecasts)
    except WeatherAPIError as exc:
        return f"❌ Unable to fetch forecast for {city}: {exc}"
    except (KeyError, TypeError) as exc:
        logger.warning("WeatherAPI forecast response is missing required fields: %s", exc)
        return f"❌ Unable to fetch forecast for {city}: invalid API response."

@mcp.tool()
async def health_check() -> str:
    """Health check endpoint for deployment verification."""
    return "✅ Weather MCP Server is running! Ready to provide weather data for Australian cities and worldwide."

if __name__ == "__main__":
    print("✅ Available tools: get_current_weather, get_forecast, health_check")
    print(f"🚀 Starting MCP server on http://0.0.0.0:{port}/mcp")
    # Lab 04 always uses Streamable HTTP. Do not infer transport from isatty():
    # terminals launched by Cursor/CI are often non-interactive on Windows.
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        print("Weather MCP Server stopped.")
