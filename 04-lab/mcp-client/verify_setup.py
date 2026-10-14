#!/usr/bin/env python3
"""
Verification script for Weather Agent setup
Checks configuration and performs a real MCP initialize/list_tools/call_tool round trip.
"""
import asyncio
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SERVER_ENV_FILE = BASE_DIR.parent / "mcp-server" / ".env"
EXPECTED_TOOLS = {"get_current_weather", "get_forecast", "health_check"}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _configured(value: str | None) -> bool:
    """Return True for a non-empty, non-placeholder secret without logging it."""
    if not value:
        return False
    lowered = value.strip().lower()
    return not any(marker in lowered for marker in ("your_", "replace", "changeme"))


def check_environment():
    """Check both Gemini and WeatherAPI configuration without exposing secrets."""
    print("🔍 Checking environment configuration...")

    env_file = BASE_DIR / ".env"
    from dotenv import load_dotenv

    if env_file.exists():
        load_dotenv(env_file)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not _configured(api_key):
        print("❌ GOOGLE_API_KEY is missing or is a placeholder in environment/.env")
        print("   Get key from: https://aistudio.google.com/apikey")
        return False

    print("✅ GOOGLE_API_KEY configured (value hidden)")

    if SERVER_ENV_FILE.exists() and not os.getenv("WEATHERAPI_KEY"):
        load_dotenv(SERVER_ENV_FILE, override=False)
    weather_key = os.getenv("WEATHERAPI_KEY")
    if not _configured(weather_key):
        print("❌ WEATHERAPI_KEY is missing or is a placeholder")
        print(f"   Configure it in: {SERVER_ENV_FILE}")
        return False

    print("✅ WEATHERAPI_KEY configured (value hidden)")
    return True

def check_dependencies():
    """Check if required packages are installed"""
    print("\n🔍 Checking dependencies...")
    
    required_packages = [
        ("google.adk", "Google ADK"),
        ("google.genai", "Google Gen AI SDK"),
        ("mcp", "MCP"),
        ("fastmcp", "FastMCP"),
        ("dotenv", "python-dotenv"),
        ("httpx", "httpx"),
    ]
    
    all_installed = True
    for package, name in required_packages:
        try:
            __import__(package)
            print(f"✅ {name}")
        except ImportError:
            print(f"❌ {name} not installed")
            all_installed = False
    
    if not all_installed:
        print("\n   Install with: uv sync")
    
    return all_installed

def check_agent_structure():
    """Check if agent directory structure is correct"""
    print("\n🔍 Checking agent structure...")
    
    required_files = [
        BASE_DIR / "weather_agent" / "agent.py",
        BASE_DIR / "weather_agent" / "__init__.py",
    ]
    
    all_exist = True
    for path in required_files:
        if path.exists():
            print(f"✅ {path.relative_to(BASE_DIR)}")
        else:
            print(f"❌ {path.relative_to(BASE_DIR)} not found")
            all_exist = False
    
    return all_exist

async def _verify_mcp_round_trip(server_url: str) -> tuple[set[str], str]:
    """Use the real MCP client protocol, not a plain HTTP reachability check."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(server_url) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            tool_names = {tool.name for tool in listed.tools}
            result = await session.call_tool("health_check", {})
            if result.isError or not result.content:
                raise RuntimeError("health_check returned an MCP tool error")
            health_text = getattr(result.content[0], "text", "")
            return tool_names, health_text


def check_mcp_server():
    """Initialize MCP, discover the three tools, and call health_check."""
    print("\n🔍 Checking MCP server connectivity...")

    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8085/mcp")

    try:
        tool_names, health_text = asyncio.run(_verify_mcp_round_trip(server_url))
    except Exception as e:
        print(f"❌ MCP protocol check failed at {server_url}: {type(e).__name__}: {e}")
        print("   Start it: cd ../mcp-server && uv run python weather.py")
        return False

    missing = EXPECTED_TOOLS - tool_names
    if missing:
        print(f"❌ MCP list_tools is missing: {', '.join(sorted(missing))}")
        return False
    if "running" not in health_text.lower():
        print("❌ health_check returned an unexpected response")
        return False

    print(f"✅ MCP initialize succeeded at {server_url}")
    print(f"✅ MCP list_tools discovered: {', '.join(sorted(tool_names))}")
    print("✅ MCP call_tool('health_check') succeeded")
    return True

def check_agent_import():
    """Try to import the agent"""
    print("\n🔍 Checking agent import...")
    
    try:
        import warnings
        warnings.filterwarnings("ignore")

        from weather_agent import root_agent
        if root_agent.name != "weather_agent" or not root_agent.tools:
            raise RuntimeError("root_agent is missing its name or MCP toolset")
        print(f"✅ Agent imported successfully: {root_agent.name}")
        print(f"   Model: {root_agent.model}; toolsets: {len(root_agent.tools)}")
        return True
    except Exception as e:
        print(f"❌ Failed to import agent: {e}")
        return False

def main():
    """Run all verification checks"""
    print("=" * 60)
    print("Weather Agent Setup Verification")
    print("=" * 60)
    print()
    
    checks = [
        check_environment(),
        check_dependencies(),
        check_agent_structure(),
        check_mcp_server(),
        check_agent_import(),
    ]
    
    print("\n" + "=" * 60)
    if all(checks):
        print("✅ All checks passed!")
        print("\n🚀 Ready to start!")
        print("   Run: uv run adk web")
        print("\n📍 Then open: http://localhost:8000")
        return 0
    else:
        print("❌ Some checks failed")
        print("\n⚠️  Fix the issues above and run this script again")
        return 1

if __name__ == "__main__":
    sys.exit(main())

