# Gateway Skill Toolkit

Toolkit mẫu để mang sang repo khác: gateway + service demo + worker + hạ tầng tối thiểu (Redis, RabbitMQ).

## Cấu trúc
- `docker-compose.yml`: chạy gateway, `ai-math-service`, `ai-task-worker`, `redis`, `rabbitmq`.
- `ai-math-service/`: FastAPI demo, auto đăng ký route vào gateway.
- `ai-task-worker/`: Celery worker, load task module từ env/YAML/DB, có plugin mẫu.
- `gateway-skill-nhutpham.md`: ghi chú nhanh (VN).
- `app/gateway_register.py` (trong repo chính): hàm tự đăng ký toàn bộ API (ví dụ /label/projects, /label/tasks, /health) vào gateway ở startup hoặc chạy tay (env: `SERVICE_NAME`, `SERVICE_BASE_URL`, `GATEWAY_URL`, `GATEWAY_PREFIX`).

## Hướng dẫn đăng ký gateway (sử dụng `app/gateway_register.py`)
### Chạy tay (không cần sửa code)
```bash
export SERVICE_NAME=label-studio-wrapper        # tên hiển thị ở gateway
export SERVICE_BASE_URL=http://127.0.0.1:8080   # URL mà gateway sẽ gọi tới service này
export GATEWAY_URL=http://127.0.0.1:30090       # URL của gateway
export GATEWAY_PREFIX=/rag                      # optional; bỏ trống nếu không cần
python app/gateway_register.py
```
Kỳ vọng: log `Gateway registered (...) routes=5 prefix=/rag` và routes xuất hiện trên Swagger gateway.

### Auto-register khi service khởi động
Thêm vào startup (FastAPI/Django/Flask):
```python
from app.gateway_register import register_gateway
register_gateway()  # gọi sớm trong startup
```
Đảm bảo các env ở trên đã được set trước khi chạy.

### Các route đăng ký mặc định
- `POST/GET /label/projects`  → proxy wrapper tạo/list project
- `POST/GET /label/tasks`     → proxy wrapper import/list tasks
- `GET /health/`              → healthcheck
Có thể chỉnh trong `build_routes()` nếu muốn đổi path/prefix/summary.

### Troubleshooting nhanh
- Không thấy route: kiểm tra `GATEWAY_URL`, `SERVICE_BASE_URL`, prefix; xem log retry.
- Trùng path: set `GATEWAY_PREFIX` để namespacing.
- Thử curl trực tiếp: `curl -X POST $GATEWAY_URL/gateway/register -d @payload.json -H "Content-Type: application/json"` với payload trong `app/gateway_register.py`.

## Chạy demo (repo hiện tại hoặc repo mới đã copy)
```bash
cd folder-gateway-skill
docker compose up -d --build
```
Mở:
- Gateway docs: http://127.0.0.1:30090/docs
- Math service docs: http://127.0.0.1:8082/docs
- RabbitMQ UI: http://127.0.0.1:15672 (guest/guest)
- Redis: 127.0.0.1:6379

## Đăng ký service kiểu ai-math
- Env cần: `SERVICE_NAME`, `SERVICE_BASE_URL`, `GATEWAY_URL`, `REGISTER_RETRIES`, `REGISTER_DELAY`.
- Service POST tới `${GATEWAY_URL}/gateway/register` với payload:
  ```json
  {
    "name": "ai-math-service",
    "base_url": "http://ai-math-service:8082",
    "routes": [
      {"name":"ai-math-add","method":"POST","gateway_path":"/v1/ai/math/add","upstream_path":"/api/add","summary":"Add two numbers","description":"Returns the sum of a+b"}
    ]
  }
  ```
- Mẫu đăng ký nằm trong `ai-math-service/main.py` (`_register_gateway` gọi ở startup).

## Worker kiểu task (WS /ws/workers/{worker_id})
- Worker kết nối tới `ws://<gateway>:30090/ws/workers/{worker_id}` (registry in-memory, xem `GET /gateway/workers`).
- Celery worker mẫu trong `ai-task-worker` (queue `ai_celery`, broker RabbitMQ, backend Redis).
- Env chính: `BROKER`, `REDIS_URL`, `QUEUE_NAME`. Plugin mẫu: `app/plugins/sample_tasks.py`.

## Tool registry (WS /ws/tools/{tool_id})
- Dùng khi cần persist tool/PC_id/PC_token. Gateway sẽ lưu DB (khác worker).
- Client kết nối `ws://<gateway>:30090/ws/tools/{tool_id}` theo protocol của gateway chính (phụ thuộc repo chính).

## Copy sang repo khác
- Copy nguyên thư mục `folder-gateway-skill/`.
- Đảm bảo gateway của repo đích có Dockerfile ở root; nếu khác đường dẫn, chỉnh `build.context` trong `docker-compose.yml`.
- Cập nhật `GATEWAY_URL`/`SERVICE_BASE_URL` nếu host/port khác, sau đó `docker compose up -d --build`.
- Nếu chạy uvicorn trực tiếp, ví dụ: `uvicorn app.main:app --host 0.0.0.0 --port 30091 --reload` và đặt env:
  - `SERVICE_NAME=ai-assistant`
  - `SERVICE_BASE_URL=http://127.0.0.1:30091`
  - `GATEWAY_URL=http://127.0.0.1:30090` (hoặc URL gateway của bạn)
  - `GATEWAY_PREFIX=/ai-assistant` (tùy chọn, để tránh trùng path với service khác; nếu để trống sẽ không có prefix)

## QA OpenAPI (đủ route + UI test nhanh)
- Dump OpenAPI (quét toàn bộ route, kể cả manual) từ `app.main`:\
  `python folder-gateway-skill/openapi_tools/dump_openapi.py -o folder-gateway-skill/openapi.json`
- Cài UI: `pip install -r folder-gateway-skill/openapi_tools/requirements.txt`
- Streamlit explorer (group theo tag, auto form params/body, show status/log/response):\
  `OPENAPI_SOURCE=http://127.0.0.1:30091/openapi.json streamlit run folder-gateway-skill/openapi_tools/streamlit_app.py`
- Gradio explorer (QA/QC nhập JSON path/query/header/body, giống Postman):\
  `OPENAPI_SOURCE=folder-gateway-skill/openapi.json python folder-gateway-skill/openapi_tools/gradio_app.py`
- Mục tiêu: BA/QC/Dev có UI nội bộ để test toàn bộ API theo Swagger/OpenAPI, tránh thiếu schema khi đăng ký gateway.

## Lưu ý quan trọng (tránh 404 do sai upstream)
- `SERVICE_BASE_URL` phải là URL thật mà gateway gọi tới được (port/service đang chạy). Ví dụ nếu service chạy trên 30091: `SERVICE_BASE_URL=http://127.0.0.1:30091`.
- `GATEWAY_URL` phải là URL của gateway, không trỏ nhầm ngược lại. Ví dụ gateway port 30090: `GATEWAY_URL=http://127.0.0.1:30090`.
- Dùng `GATEWAY_PREFIX=/ai-assistant` để tránh đụng path với service khác; khi đó đường dẫn trên gateway sẽ là `/ai-assistant/...`.

## Tuỳ chỉnh thêm (tùy chọn)
- Nếu cần DB capability cho worker: tạo bảng `worker_capabilities(capability_name, queue, module_path, enabled, schema jsonb null)`.
- Thêm healthcheck/depends_on vào compose nếu muốn khởi động tuần tự hơn.
