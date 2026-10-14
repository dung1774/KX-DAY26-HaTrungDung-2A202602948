"""Google ADK weather agent backed by a Streamable HTTP MCP server."""
from pathlib import Path

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StreamableHTTPConnectionParams
import logging
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mặc định: server chạy local. Deploy lên Cloud Run thì đặt MCP_SERVER_URL trong .env
# (ví dụ: https://<service>.run.app/mcp). verify_setup.py đọc cùng biến này.
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8085/mcp")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

logger.info("Initializing weather agent")
logger.info("MCP Server: %s", MCP_SERVER_URL)

# McpToolset connects lazily when ADK asks for tools. Creating this object alone
# is deliberately not logged as a successful MCP connection; verify_setup.py
# performs a real initialize/list_tools/call_tool health_check round trip.
connection_params = StreamableHTTPConnectionParams(
    url=MCP_SERVER_URL,
    timeout=30.0,
)
weather_tools = McpToolset(connection_params=connection_params)

root_agent = Agent(
    name="weather_agent",
    model=GEMINI_MODEL,
    description="Trợ lý thời tiết sử dụng các tool từ MCP server.",
    instruction=(
        "Trả lời bằng tiếng Việt. Khi người dùng hỏi thời tiết hiện tại, "
        "dự báo, hoặc yêu cầu kiểm tra server, phải dùng MCP tool phù hợp. "
        "Không tự bịa dữ liệu thời tiết. Nếu tool báo lỗi, nói rõ lỗi cho người dùng."
    ),
    tools=[weather_tools],
)
logger.info("Weather agent configured with MCP tools (connection is verified at runtime).")

