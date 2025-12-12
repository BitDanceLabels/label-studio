# bọc cho tui vô 2 đăng ký này :
# các bước phân tích main app chính của repo để bọc swaggers và schemas kiểu postman => để làm và trả api là được => ko cần lưu database => gateway sẽ quyết định khi nào cần lưu database 

{ quét lại repo }

- cho tôi 1 click run docker
{ 
    - tạo requirement 
    - docker compose
}

- xác nhận lớp API =>> return API response gateway và mapping core base


# D:\NHUTPHAM-GIT-D\FastAPI_chatgpt_api\folder-gateway-skill\ai-math-service
dựa vào mẫu :
ai math => đăng ký API swagger vô fastapi => giúp tôi bọc thêm 1 lớp vô swagger và thêm schames demo cho nó hiển thị demo trên gateway

# dựa vào ollama backgroup job =>> đăng ký cho tui vào hệ thống D:\NHUTPHAM-GIT-D\FastAPI_chatgpt_api\folder-gateway-skill\ai-task-worker
dựa vào code mẫu => tạo 1 lớp bọc swss


- đăng ký webhook nhận update sự kiện realtime
- đăng ký thêm topics tự động trên rabbitmq => bằng lệnh reload worker task ? đọc lại code chỗ này , quên mất tiêu cách làm ?? 

tạo capital tag cho loại worker và mapping khi có công việc 

tạo thêm 1 endpoint để modules AI tác vụ nặng đắng ký celery modules riêng vô database => đẩy lên celery 

Thêm bản ghi capability vào DB worker_capabilities (capability name, queue, module_path, enabled, optional schema).

# 1 Click run => Các Demo streamlit sử dụng 
{
    nhờ flow agent : viết và thiết kế bài quảng cáo free đăng ký 
    quét qua repo để viết hướng dãn sủ dụng
    cách triển khai app
    auto structure => folder locals
    
}
# bọc sqllite locals => để lưu trữ
- gói nâng cấp =>

# plan code nâng cấp các tính năng => open repo 
# dựa vào docker compose + move models vào docker 
- tạo requirement đã thành công 
- tạo các bước để run mô hình 
- dịch chuyển các file models nếu có vào docker 
- các cấu hình nếu có
- chạy port host 0.0.0.0 

# dựa vào PC IP wss => đăng ký thêm 1 demo khi phát sinh đăng ký list tools PC :

vậy bổ sung luôn đi mà cho tui hỏi 2 cái tools ws khác nhau gì ta, tui tưởng nó là 1 : đăng ký qua  Còn ollama/worker_client.py đang kết nối /ws/workers/{worker_id} (task worker), nên nó không ghi vào tool_registry. Task workers được giữ trong memory của TaskWorkerRegistry và trả ra qua REST GET /gateway/workers, không persist DB. =>> khác gì đăng ký qua tool_registry: trống vì bạn chưa có tool kết nối qua /ws/tools/.... => à tui nhớ rùi, khi tui cần tạo PC id code gì đó thì tui mới đăng ký tool_registry

# vậy nó có bị lưu trùng lặp ko, và làm sao mà tui nhớ nổi PC_id với PC_token

# tạo fork flow agent backup : cho các API với tốc độ xử lý khác nhau : 

- có cho phép lớp API backup nếu try catch không được =>> : có nghĩa là ở trong đó cho phép thêm các id human vô tiến trình để làm việc và lưu full json các công việc 
# chỉ làm API là được, phần quản lý database và multi tenant đã có corebase quản lý rồi => quản lý siteID - userID - appID 
Ok, vậy coi như:

Corebase = lo hết vụ DB, multi-tenant, quyền, id, v.v.

Service này = chỉ cần API FastAPI để: