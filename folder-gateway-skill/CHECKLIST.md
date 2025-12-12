# Gateway Toolkit Checklist

Use this to verify the toolkit when copying to a new repo or updating.

## Environment & URLs
- [ ] `GATEWAY_URL` trỏ đúng gateway (không phải service).
- [ ] `SERVICE_BASE_URL` trỏ đúng service đang chạy (port/https đúng).
- [ ] `GATEWAY_PREFIX` (nếu dùng) để tránh trùng path; kiểm tra các route có prefix trong Swagger.
- [ ] `SERVICE_NAME` đặt rõ ràng.
- [ ] Các env AI (OpenAI, Bedrock) đã đặt hoặc tắt nếu không dùng.

## Registration & routes
- [ ] `app/gateway_register.py` được gọi ở startup (đăng ký thành công trong log).
- [ ] `GATEWAY_PREFIX` áp dụng đúng; gateway hiển thị routes kiểu `/prefix/...`.
- [ ] `gateway_routes.py` (manual routes) đã đủ các API cần expose; thêm/sửa nếu thiếu.
- [ ] Auto-discovery + manual merge không tạo route trùng/sai method.
- [ ] Nếu gateway đổi path base, cập nhật lại manual routes/prefix cho khớp.

## Services & infra (docker-compose)
- [ ] Service gateway build được (Dockerfile ở root hoặc chỉnh `build.context`).
- [ ] `ai-math-service` build/chạy được; auto register vào gateway.
- [ ] `ai-task-worker` chạy với RabbitMQ/Redis OK.
- [ ] RabbitMQ/Redis port không trùng; UI RabbitMQ vào được (15672).
- [ ] Nếu cần DB (capability/tool_registry), cấu hình Postgres/SQLite phù hợp (hiện toolkit không bật SQLite).

## Database & schema (nếu dùng DB)
- [ ] `DATABASE_URL_ASYNCPG_DRIVER` hoặc DB URL khác được set khi cần.
- [ ] Nếu lưu capability: đã tạo bảng `worker_capabilities(capability_name, queue, module_path, enabled, schema jsonb null)`.
- [ ] Nếu dùng tool_registry/PC_id: có bảng lưu tool/PC token (không mặc định trong toolkit).

## Swagger/OpenAPI
- [ ] Swagger gateway hiển thị route có prefix đúng.
- [ ] Không còn 404 khi gọi qua gateway; test mẫu `/translate`, `/embed-text`, `/bedrock/chat`.
- [ ] Kiểm tra warning Duplicate Operation ID; đặt `operation_id` riêng nếu cần.
- [ ] Dump OpenAPI từ app chính (`python folder-gateway-skill/openapi_tools/dump_openapi.py`) và so sánh với gateway để chắc schema không thiếu.
- [ ] Mỗi tag mô tả rõ domain, tránh “default”; summary/description đầy đủ để Streamlit/Gradio auto UI hiểu đúng.

## Runtime checks
- [ ] Khi start service: log “Gateway registered (...) routes=N”.
- [ ] Thay đổi code -> reload/khởi động lại để đăng ký lại (không có auto re-register nền ngoài startup).
- [ ] Worker WS và tool_registry WS hoạt động (nếu dùng): `/ws/workers/{id}`, `/ws/tools/{id}`.

## Misc
- [ ] `.env.example` đã phản ánh giá trị mẫu chính xác (gateway/service URL, prefix).
- [ ] README cập nhật hướng dẫn chạy local + uvicorn + compose.
- [ ] Kiểm tra port/public domain reverse proxy nếu gọi HTTPS bên ngoài.

## Convention & validation (global)
- [ ] Route naming: dùng động từ-ngắn, snake/kebab đồng nhất; gateway_path và upstream_path trùng 1:1 (trừ prefix).
- [ ] Tag chuẩn hóa theo domain (auth, chat, embed, file, admin); tránh tag rác.
- [ ] Auth/role: mỗi endpoint rõ yêu cầu (public/internal); controller kiểm tra role/permission trước khi gọi core; trả 403/401 rõ ràng.
- [ ] Input validation: pydantic schema có ràng buộc (min_length, enum, regex, max_size file); add examples cho body/query/path.
- [ ] Error model: trả JSON thống nhất `{code, message, detail?}`; log chi tiết server side, không lộ secret.
- [ ] Idempotency/duplication: với POST tạo resource, hỗ trợ idempotency-key nếu có; với jobs, trả job_id và trạng thái.

## Logic phân tầng
- [ ] Core API module giữ business logic; controller chủ yếu mapping HTTP (deserialize/serialize, auth, DB I/O nhẹ).
- [ ] Gateway proxy chỉ passthrough; không nhúng logic ngoài route mapping.
- [ ] Nếu cần đổi hành vi: sửa core module; controller chỉ chỉnh phần tương tác DB/gateway (ví dụ cache, pagination, filter).
- [ ] Tránh side effects trong controller ngoài DB giao dịch; audit/log tại core hoặc middleware.

## Lỗi & fallback cần cover
- [ ] Thử nghiệm các tình huống: thiếu/invalid token, sai role, payload thiếu field, file quá lớn/sai mime, timeout upstream, 5xx từ model provider.
- [ ] Rate limit/quota: trả 429 có retry-after nếu có; log lại.
- [ ] External dependency (Redis/RabbitMQ/DB) down: trả mã lỗi có mã code riêng; không nuốt exception.
- [ ] Validation khi đăng ký gateway: báo lỗi route trùng method+path, thiếu summary/description, thiếu prefix.

## Proxy tối ưu (proto/grpc)
- [ ] Xác định endpoints có throughput cao -> chuyển sang proto contract (grpc) giữa services; HTTP gateway chỉ làm facade.
- [ ] Proto file lưu trong repo (versioned), generate stubs cho Python; giữ đồng bộ với Swagger (cùng schema logic).
- [ ] Giảm payload (binary proto) cho luồng embed/chat streaming; bật compression nếu cần.
- [ ] Gateway proxy hỗ trợ cả grpc upstream hoặc HTTP; kiểm tra health và backoff khi upstream lỗi.
