## Mục tiêu
- Bộ kit `folder-gateway-skill/` mang sang repo khác để có ngay gateway + service demo + worker, chạy 1-click với Docker.
- Gateway chỉ proxy API (không cần DB trừ khi lưu capability/tool_registry). Worker WS khác với tool_registry WS.

## Cấu trúc thư mục
- `docker-compose.yml`: bật gateway, ai-math-service, ai-task-worker, redis, rabbitmq.
- `ai-math-service/`: FastAPI demo (add/multiply/power/background_task), tự đăng ký route vào gateway.
- `ai-task-worker/`: Celery worker, load task module từ env/YAML/DB, plugin mẫu.
- `ollama/`: giữ nguyên nếu cần thêm task liên quan ollama.

## Cách chạy 1-click (demo mặc định)
```bash
cd folder-gateway-skill
docker compose up -d --build
```
- Gateway docs: http://127.0.0.1:30090/docs
- Math service docs: http://127.0.0.1:8082/docs (route đã đăng ký vào gateway)
- RabbitMQ UI: http://127.0.0.1:15672 (guest/guest)
- Redis: 127.0.0.1:6379

## Biến môi trường chính (đã đặt trong compose)
- Gateway: `DATABASE_URL_ASYNCPG_DRIVER` để trống nếu không dùng DB; `APP_CONFIG=config.yml`.
- Math: `SERVICE_BASE_URL`, `GATEWAY_URL`, `REDIS_HOST/PORT`, `RABBITMQ_HOST/PORT`.
- Worker: `BROKER`, `REDIS_URL`, `QUEUE_NAME`.

## Đăng ký service vào gateway
- Math service tự POST `/gateway/register` với danh sách routes (xem `ai-math-service/main.py`).
- Thêm service mới: expose OpenAPI/route upstream, set `GATEWAY_URL`, gửi payload `{name, base_url, routes[]}` tương tự để gateway map.

## Worker vs tool_registry
- Task worker: kết nối `/ws/workers/{worker_id}`, lưu trong memory `TaskWorkerRegistry`, liệt kê qua `GET /gateway/workers`, không persist DB.
- Tool_registry: kết nối `/ws/tools/...`, persist DB. Nếu cần PC_id/PC_token bền vững, lưu (pc_id, token, type, metadata) vào DB riêng.

## Mở rộng
- Capability DB (nếu cần): bảng `worker_capabilities(capability_name, queue, module_path, enabled, schema jsonb null)`.
- Worker load module thứ tự: env `EXTRA_TASK_MODULES` → YAML `config/worker_modules.yaml` → DB (`WORKER_MODULES_TABLE`, `DATABASE_URL`).
- Plugin demo: `app/plugins/sample_tasks.py` có task `sleep_echo`.

## Khi copy sang repo khác
- Copy nguyên `folder-gateway-skill/`.
- Nếu gateway ở repo khác: chỉnh `docker-compose.yml` (`build.context` của service gateway) và `GATEWAY_URL`.
- Sau đó `docker compose up -d --build` để có gateway + service + worker mẫu, Swagger sẵn để test.
