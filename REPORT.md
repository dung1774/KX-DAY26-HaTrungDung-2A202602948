# BÁO CÁO LAB DAY 26 — MCP & TOOLS INTEGRATION

## 1. Thông tin sinh viên

- Họ tên: **Hà Trung Dũng**
- MSV: **2A202602948**
- Khóa học: **VinUni AI20K**
- Bài lab: **Day 26 — MCP & Tools Integration**

Repository không có `RUBRIC.md` hoặc tài liệu submission chính thức riêng. Báo cáo này chỉ đánh giá theo README và mã nguồn có trong repository.

## 2. Mục tiêu

Hoàn thiện bốn phần: Function Calling với Gemini, MCP cơ bản qua stdio, các mẫu production (authentication, registry, versioning), và Weather Agent dùng Google ADK kết nối FastMCP Server qua Streamable HTTP để lấy dữ liệu WeatherAPI thật.

## 3. Function Calling và MCP

Function Calling là khả năng của model: model chọn tool và sinh tham số, còn Python application thực thi hàm và gửi kết quả lại model. Phần 01 giữ dữ liệu thời tiết mock để minh họa đúng cơ chế này.

MCP là giao thức chuẩn giữa client và server. Client khởi tạo phiên, khám phá tool bằng `list_tools()` và gọi tool bằng `call_tool()`. Lab 04 kết hợp cả hai: ADK/Gemini quyết định tool, còn `McpToolset` giao tiếp với MCP Server.

## 4. Các phần đã hoàn thành

- Phần 01: nạp API key từ environment/`.env`, model gọi `get_weather`, app thực thi mock tool, gửi kết quả lại model, xử lý thiếu key/lỗi API.
- Phần 02: stdio server/client, `initialize()`, `list_tools()`, và `call_tool()` cho Hanoi, Danang, Haiphong.
- Phần 03: bearer authentication qua Streamable HTTP; registry tìm theo tag/keyword và chọn semantic version cao nhất không deprecated; server versioned giữ v1, thêm v2 và `server://info`.
- Phần 04: ba tool `get_current_weather`, `get_forecast`, `health_check`; WeatherAPI thật; xử lý timeout/HTTP/key/city/days; server luôn khởi động Streamable HTTP; ADK Agent gắn `McpToolset` và không fallback âm thầm sang Agent không tool.
- Bổ sung unit test offline, live MCP test, ADK Runner E2E test và thư mục evidence.

## 5. Luồng Google ADK kết nối MCP Server

`User -> Google ADK Agent (Gemini) -> McpToolset -> FastMCP /mcp -> WeatherAPI -> FastMCP -> McpToolset -> Gemini -> User`

`verify_setup.py` không coi việc khởi tạo `McpToolset` là thành công. Script tạo MCP session thật, gọi `initialize()`, kiểm tra đủ ba tool qua `list_tools()` và gọi `health_check()`.

## 6. Cách khởi chạy và test trên Windows PowerShell

Phần 01–03:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python .\02-mcp-basics\weather_client.py
```

Lab 04, terminal 1:

```powershell
Set-Location .\04-lab\mcp-server
uv sync --python 3.12
uv run python weather.py
```

Lab 04, terminal 2:

```powershell
Set-Location .\04-lab\mcp-client
uv sync --python 3.12
uv run python verify_setup.py
uv run python e2e_test.py
uv run adk web
```

## 7. Kết quả kiểm thử thực tế

| Hạng mục | Loại test | Kết quả | Bằng chứng |
|---|---|---|---|
| Function Calling | Live Gemini + mock weather tool | PASS | `evidence/function_calling.txt` |
| MCP Basics | Stdio initialize/list/call 3 thành phố | PASS | `evidence/mcp_basics.txt` |
| Core unit tests | Offline, 3 test | PASS | `evidence/offline_tests.txt` |
| Authentication | Token hợp lệ gọi tool; thiếu/sai token nhận HTTP 401 | PASS | `evidence/production_tests.txt` |
| Tool Registry | Search + best match v2 + gọi server | PASS | `evidence/production_tests.txt` |
| Versioning | Resource metadata + v1 + v2 | PASS | `evidence/production_tests.txt` |
| Weather tool errors | Offline mocked HTTP, 6 test | PASS | `evidence/weather_api_mock_tests.txt` |
| Setup verification | Dependency, key, Agent, MCP handshake/list/call | PASS | `evidence/verify_setup.txt` |
| Live WeatherAPI qua MCP | Current + forecast 3 ngày + health | PASS | `evidence/live_weatherapi_mcp.txt` |
| ADK E2E A/B/C | Live Gemini + MCP + WeatherAPI, có tool call/response | PASS 3/3 | `evidence/live_integration.txt` |
| ADK Web | Khởi động trên Windows, HTTP 200 | PASS | Kiểm tra trực tiếp trong terminal; không tạo ảnh giả |

## 8. Lỗi đã phát hiện và khắc phục

- Console Windows CP1252 không in được tiếng Việt: cấu hình UTF-8 cho các CLI.
- Client stdio phụ thuộc working directory: chuyển sang đường dẫn tuyệt đối từ `__file__`.
- Lab server có thể rơi về stdio do `sys.stdin.isatty()`: bỏ suy luận transport, luôn chạy `streamable-http`.
- `verify_setup.py` từng coi mọi HTTP < 500 là reachable và in một phần key: thay bằng MCP handshake/list/call thật và luôn ẩn giá trị key.
- Agent từng ghi log kết nối thành công ngay khi chỉ tạo `McpToolset`, sau đó fallback không tool: loại bỏ success giả và fallback.
- WeatherAPI chưa kiểm tra days/city và lỗi chi tiết: thêm validation, timeout và thông báo an toàn.
- HTTP client có thể log query URL chứa WeatherAPI key: hạ logger `httpx` xuống WARNING để không ghi secret.
- `gemini-2.5-flash` trả HTTP 404 cho user mới; `gemini-3.8-flash` có lúc trả 503 do tải cao. Model mặc định được đổi có lý do sang `gemini-3.5-flash`, đã PASS E2E 3/3; vẫn có thể override qua `GEMINI_MODEL`.

## 9. Hạn chế

- Live test phụ thuộc kết nối mạng, quota và tình trạng Gemini/WeatherAPI tại thời điểm chạy.
- Không lưu ảnh ADK Web; luồng tool invocation được chứng minh bằng log ADK Runner thật.
- API key chỉ nằm trong các file `.env` bị `.gitignore`, không được ghi vào evidence hay source.

## 10. Kết luận

Tại lần kiểm thử ngày 14/10/2026, bốn phần của Lab Day 26 và ba ca E2E đều PASS. Repository sẵn sàng để sinh viên tự kiểm tra diff, commit và push.
