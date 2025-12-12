Chạy (Windows cmd):
docker run -it -p 1111:8080 -v "%cd%\\mydata:/label-studio/data" heartexlabs/label-studio:latest

# cmd
docker run -it -p 1111:8080 --env-file .env ^
  -v "%cd%\mydata:/label-studio/data" ^
  heartexlabs/label-studio:latest


# PowerShell (Windows)
docker run -it -p 1111:8080 --env-file .env -v "${PWD}/mydata:/label-studio/data" heartexlabs/label-studio:latest

# Git Bash
docker run -it -p 1111:8080 --env-file .env -v "$(pwd)/mydata:/label-studio/data" heartexlabs/label-studio:latest

#
python -m venv .venv
python -m pip install python-dotenv==1.0.1

# terminal tại root repo, đã set env hoặc dùng .env
python app/gateway_register.py


# Gateway registration guide

Hướng dẫn riêng cho phần đăng ký gateway từ repo này (dùng `app/gateway_register.py` và wrapper Label Studio).

## Mục đích
- Đăng ký các route wrapper `/label/projects`, `/label/tasks`, `/health/` vào gateway để service được proxy.
- Hỗ trợ đặt prefix để tránh trùng path với service khác.

## Biến môi trường
- `SERVICE_NAME`: tên service hiển thị ở gateway (vd: `label-studio-wrapper`).
- `SERVICE_BASE_URL`: URL mà gateway sẽ gọi tới service này (vd: `http://127.0.0.1:8080`).
- `GATEWAY_URL`: URL của gateway (vd: `http://127.0.0.1:30090`).
- `GATEWAY_PREFIX`: optional, prefix cho tất cả route (vd: `/rag`).
- `REGISTER_RETRIES`, `REGISTER_DELAY`: số lần retry và delay giữa các lần đăng ký (mặc định 5 lần, 1s).

## Chạy tay
```bash
export SERVICE_NAME=label-studio-wrapper
export SERVICE_BASE_URL=http://127.0.0.1:8080
export GATEWAY_URL=http://127.0.0.1:30090
export GATEWAY_PREFIX=/rag        # bỏ trống nếu không cần
python app/gateway_register.py
```
Kỳ vọng log: `Gateway registered (...) routes=5 prefix=/rag` và route xuất hiện trên Swagger gateway.

## Auto-register khi service khởi động
Gọi sớm trong startup (FastAPI/Django/Flask):
```python
from app.gateway_register import register_gateway
register_gateway()
```
Đảm bảo các biến môi trường đã được set trước khi khởi động.

## Route mặc định được đăng ký
- `POST /label/projects`, `GET /label/projects`
- `POST /label/tasks`, `GET /label/tasks`
- `GET /health/`
Muốn đổi path/prefix/summary, chỉnh hàm `build_routes()` trong `app/gateway_register.py`.

## Troubleshooting nhanh
- Không thấy route: kiểm tra `GATEWAY_URL`, `SERVICE_BASE_URL`, `GATEWAY_PREFIX`; xem log retry.
- Trùng path: đặt `GATEWAY_PREFIX` để tách namespace.
- Thử đăng ký thủ công: `curl -X POST $GATEWAY_URL/gateway/register -H "Content-Type: application/json" -d '<payload>'` với payload từ `app/gateway_register.py`.
