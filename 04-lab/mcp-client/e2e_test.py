"""Live ADK -> MCP -> WeatherAPI test for the three required lab prompts."""

import asyncio
import sys

from google import genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from weather_agent import root_agent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

APP_NAME = "weather_lab_e2e"
USER_ID = "lab-student"
CASES = [
    (
        "A",
        "Cho tôi biết thời tiết hiện tại ở Hà Nội.",
        "get_current_weather",
    ),
    (
        "B",
        "Dự báo thời tiết Hà Nội trong 3 ngày tới.",
        "get_forecast",
    ),
    (
        "C",
        "Hãy gọi health_check để kiểm tra MCP Server.",
        "health_check",
    ),
]


async def run_case(runner: Runner, case_id: str, prompt: str, expected_tool: str) -> None:
    session_id = f"case-{case_id.lower()}"
    await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id,
    )

    called_tools: list[str] = []
    response_tools: list[str] = []
    final_text = ""
    message = genai.types.Content(
        role="user",
        parts=[genai.types.Part.from_text(text=prompt)],
    )

    print(f"\n=== TEST {case_id} ===")
    print(f"PROMPT: {prompt}")
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=message,
    ):
        for function_call in event.get_function_calls():
            called_tools.append(function_call.name or "")
            print(f"TOOL_CALL: {function_call.name} args={function_call.args}")
        for function_response in event.get_function_responses():
            response_tools.append(function_response.name or "")
            print(f"TOOL_RESPONSE: {function_response.name} response={function_response.response}")
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(part.text or "" for part in event.content.parts)

    if expected_tool not in called_tools:
        raise AssertionError(
            f"Test {case_id}: expected {expected_tool}, got calls {called_tools}"
        )
    if expected_tool not in response_tools:
        raise AssertionError(
            f"Test {case_id}: no tool response for {expected_tool}; got {response_tools}"
        )
    print(f"FINAL_RESPONSE: {final_text}")
    print(f"RESULT: PASS ({expected_tool} was called and returned a response)")


async def main() -> None:
    selected_ids = {value.upper() for value in sys.argv[1:]}
    selected_cases = [case for case in CASES if not selected_ids or case[0] in selected_ids]
    if not selected_cases:
        raise SystemExit("Usage: uv run python e2e_test.py [A] [B] [C]")

    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    try:
        for case in selected_cases:
            await run_case(runner, *case)
    finally:
        await runner.close()

    print(f"\nE2E RESULT: PASS ({len(selected_cases)}/{len(selected_cases)} selected cases)")


if __name__ == "__main__":
    asyncio.run(main())
