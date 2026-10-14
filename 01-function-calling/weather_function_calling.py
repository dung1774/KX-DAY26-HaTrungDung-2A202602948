"""Minh hoạ FUNCTION CALLING thuần với Google Gemini SDK.

Tool `get_weather` được định nghĩa schema thủ công VÀ thực thi ngay trong
chính file app này. Model chỉ QUYẾT ĐỊNH gọi tool nào; app mới là nơi chạy.

Cách chạy (dữ liệu thời tiết trong demo này là mock):
    pip install -r ../requirements.txt
    export GEMINI_API_KEY=...
    python weather_function_calling.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Nạp file .env cạnh script, không phụ thuộc thư mục chạy lệnh.
load_dotenv(Path(__file__).with_name(".env"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 2.5-flash không còn được Gemini API cấp cho user mới (HTTP 404).
# Cho phép ghim model qua môi trường, với default đã được live-check.
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

SYSTEM_INSTRUCTION = (
    "Bạn là trợ lý thời tiết thân thiện, trả lời bằng tiếng Việt tự nhiên. "
    "Dùng emoji phù hợp (🌧️ 🌤️ 💨 💧). "
    "Tóm tắt ngắn gọn, dễ hiểu, và đưa ra lời khuyên thực tế "
    "(ví dụ: mang ô, mặc áo mỏng, ...)."
)

# 1. App tự định nghĩa schema của tool
get_weather_declaration = types.FunctionDeclaration(
    name="get_weather",
    description="Lấy thời tiết hiện tại của một thành phố",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "city": types.Schema(
                type=types.Type.STRING, description="Tên thành phố"
            )
        },
        required=["city"],
    ),
)

TOOLS = [types.Tool(function_declarations=[get_weather_declaration])]


# 2. App tự thực thi tool (trong thực tế sẽ gọi API thời tiết thật)
def get_weather(city: str) -> str:
    """Trả về thời tiết (mock) của *city*. Dùng làm tool cho model."""
    mock_data = {
        "Hà Nội": {
            "nhiệt_độ": "29°C",
            "thời_tiết": "trời mưa nhẹ",
            "độ_ẩm": "82%",
            "gió": {"hướng": "Đông Nam", "tốc_độ": "12 km/h"},
        },
        "Hồ Chí Minh": {
            "nhiệt_độ": "33°C",
            "thời_tiết": "mưa rào",
            "độ_ẩm": "75%",
            "gió": {"hướng": "Tây Nam", "tốc_độ": "15 km/h"},
        },
        "Đà Nẵng": {
            "nhiệt_độ": "30°C",
            "thời_tiết": "nhiều mây",
            "độ_ẩm": "78%",
            "gió": {"hướng": "Đông", "tốc_độ": "10 km/h"},
        },
    }
    import json

    default = {"nhiệt_độ": "28°C", "thời_tiết": "không có dữ liệu chi tiết"}
    return json.dumps({"city": city, **mock_data.get(city, default)}, ensure_ascii=False)


def _create_client() -> genai.Client:
    """Tạo Gemini client sau khi đã kiểm tra cấu hình."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Thiếu Gemini API key. Hãy đặt GEMINI_API_KEY trong biến môi trường "
            "hoặc file 01-function-calling/.env."
        )
    return genai.Client(api_key=api_key)


def run(prompt: str) -> str:
    """Gửi *prompt* tới Gemini, tự động xử lý function calling và trả về câu trả lời cuối."""
    client = _create_client()
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
    ]

    # 3. Gọi model — model quyết định có gọi tool hay không
    config = types.GenerateContentConfig(
        tools=TOOLS,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=config,
        )
    except Exception as exc:
        raise RuntimeError(f"Không thể gọi Gemini API: {exc}") from exc

    # 4. Vòng lặp: nếu model yêu cầu tool, app TỰ THỰC THI rồi đưa kết quả trả lại
    tool_rounds = 0
    while resp.function_calls:
        tool_rounds += 1
        if tool_rounds > 5:
            raise RuntimeError("Gemini yêu cầu quá nhiều vòng gọi tool.")
        # Thêm phản hồi của model vào lịch sử hội thoại
        contents.append(resp.candidates[0].content)

        function_responses = []
        for fc in resp.function_calls:
            print(f"  [model yêu cầu] {fc.name}({fc.args})")
            if fc.name != "get_weather":
                result = f"Tool không được hỗ trợ: {fc.name}"
            else:
                try:
                    result = get_weather(**dict(fc.args))  # App thực thi tool.
                except (TypeError, ValueError) as exc:
                    result = f"Tham số tool không hợp lệ: {exc}"
            print(f"  [app thực thi]  -> {result}")
            function_responses.append(
                types.Part.from_function_response(
                    name=fc.name, response={"result": result}
                )
            )

        # Gửi kết quả tool trả về cho model
        contents.append(types.Content(role="user", parts=function_responses))
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            raise RuntimeError(f"Không thể gửi kết quả tool cho Gemini: {exc}") from exc

    # 5. Model tổng hợp câu trả lời cuối
    return resp.text or "Gemini không trả về nội dung văn bản."


if __name__ == "__main__":
    question = "Thời tiết Hà Nội và Đà Nẵng hôm nay thế nào?"
    print(f"User: {question}\n")
    try:
        print("Trả lời:", run(question))
    except RuntimeError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
