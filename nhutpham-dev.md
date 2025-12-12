mkdir mydata

Kéo image có sẵn:
docker pull heartexlabs/label-studio:latest
Chạy (Windows cmd):
docker run -it -p 1111:8080 -v "%cd%\\mydata:/label-studio/data" heartexlabs/label-studio:latest



docker build -t my-label-studio:latest .
docker run -it -p 1111:8080 -v "%cd%\\mydata:/label-studio/data" my-label-studio:latest


# Mục tiêu để phân rã đối tượng =>> 

Không cần nhét thêm ChatGPT API key vào repo này nếu backend gateway của bạn đã gọi ChatGPT sẵn. Việc cần làm là nối Label Studio với gateway đó để nhận pre-label rồi bạn annotate. Cách làm:

Chạy Label Studio: container hiện có là my-label-studio:latest. Mount data: docker run -it -p 1111:8080 -v "%cd%\\mydata:/label-studio/data" my-label-studio:latest (cmd) hoặc $(pwd) nếu Git Bash.
Nối ML Backend: trong Label Studio → Settings → Model → Add Model → URL trỏ tới API /predict của gateway (ví dụ http://host.docker.internal:9090/predict nếu gateway chạy trên host). Không cần thêm OpenAI API ở đây vì gateway đã làm.
Đảm bảo API trả về đúng schema: body nhận {"data": {...}} với trường bạn import (vd text). Trả về:
[{
  "result": [{
    "from_name": "model",
    "to_name": "text",
    "type": "text",
    "value": {"text": "<gợi ý LLM>"}
  }],
  "score": 0.9
}]
Chỉnh from_name/to_name/type trùng với labeling config của project (Intent, Entity, Answer…).

Import dữ liệu raw: đặt JSONL/CSV vào mydata/ rồi import trong Data Manager. Bật “Use model predictions” để gateway được gọi cho từng item → pre-label → bạn sửa lại.
Nếu muốn mình thêm file mẫu: mình có thể tạo thư mục ml-backend/ kèm FastAPI adapter gọi gateway của bạn và một labeling config (Intent/Entity/QA). Cho mình biết: endpoint gateway, schema mong muốn (Intent, Entities, Answer, Sentiment…), và tên trường dữ liệu (vd text).

# labels 
Nối ML Backend nghĩa là Label Studio sẽ gọi API /predict của bạn mỗi khi cần pre-label. Bạn chỉ cần viết một adapter nhỏ nhận {"data": {...}}, gọi gateway flow của bạn, rồi trả về đúng schema cho Label Studio.

Cách làm cụ thể (giả sử LS chạy trong container, gateway chạy host tại http://localhost:30091/... → từ container gọi http://host.docker.internal:30091/...):

Adapter FastAPI tối giản (vd đặt ngoài repo hoặc trong ml-backend/app.py):
import os, httpx
from fastapi import FastAPI
from pydantic import BaseModel

GATEWAY_URL = os.getenv(
    "GATEWAY_URL",
    "http://host.docker.internal:30091/flows/1407931ddb1f4d388ad2457f7285510a/execute",
)

app = FastAPI()

class LSRequest(BaseModel):
    data: dict  # Label Studio gửi {"data": {"text": "..."}}

@app.post("/predict")
async def predict(req: LSRequest):
    question = req.data.get("text", "")
    if not question:
        return [{"result": []}]

    payload = {
        "inputs": {"question": question},
        "step_payloads": {
            "ask_model": {
                "model": "gpt-oss:20b-cloud",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": question},
                ],
                "stream": False,
            }
        },
        "notify": {
            "ask_model": {"enabled": True, "message": "Ask_model xong", "include_result": True},
            "review": {"enabled": True, "message": "Flow hoàn tất", "include_result": True},
        },
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(GATEWAY_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        # Giả sử gateway trả về text trong data["result"] hoặc tương tự
        suggestion = data.get("result") or str(data)

    return [{
        "result": [{
            "from_name": "model",     # phải khớp labeling config
            "to_name": "text",        # phải khớp labeling config
            "type": "text",
            "value": {"text": suggestion}
        }],
        "score": 0.9
    }]

@app.get("/health")
def health():
    return {"status": "ok"}
Chạy: uvicorn app:app --host 0.0.0.0 --port 9090 (đặt env GATEWAY_URL nếu cần đổi).

Labeling config tối thiểu (hiển thị văn bản và gợi ý từ model):
<View>
  <Text name="text" value="$text"/>
  <Textarea name="model" toName="text" label="Model Suggestion"/>
</View>
Nếu bạn muốn tách Intent/Entities/Answer… thì thêm các control tương ứng và đổi from_name/to_name/type cho đúng.

Cấu hình trong Label Studio:
Settings → Model → Add Model → URL: http://host.docker.internal:9090/predict
Bật “Use model predictions”.
Import dữ liệu raw:
Đặt JSONL vào mydata/raw.jsonl, mỗi dòng {"text": "câu hỏi..."}.
Import vào project. Khi mở từng task, LS gọi /predict → adapter gọi gateway → trả gợi ý → bạn chỉnh sửa.
Test nhanh adapter (ngoài Label Studio):
curl -X POST http://localhost:9090/predict \
  -H "Content-Type: application/json" \
  -d '{"data": {"text": "Viết một đoạn giới thiệu ngắn về Bumbee AI."}}'
Nếu bạn cần mình tạo sẵn file adapter + labeling config trong repo này, cho biết bạn muốn đặt ở đâu và response thực tế của gateway (để parse đúng trường).

# Checklist nhanh cho endpoint /predict (quản lý theo dataset + model)
- Endpoint: POST /predict, input luôn dạng {"data": {...}} với các key đúng theo dataset (vd text, context).
- Output: mảng gồm result + score; from_name/to_name/type khớp label config.
- Tên model (nếu backend hỗ trợ nhiều model): truyền qua config hoặc header, ví dụ header X-Model: gpt-oss:20b-cloud, hoặc nhận field model trong data.
- Nếu có nhiều loại dataset cần validate: dùng param query ?dataset=chatbot hoặc phân nhánh theo nhãn project; log lại dataset name + model name để trace.
- Bật preannotations trong Project Settings → Model để mỗi lần mở task auto gọi /predict.
Trang “My Account” chỉ để xem thông tin cá nhân và tạo Personal Access Token cho API; không có chỗ cấu hình model.

Để thêm ML backend (model):

Vào project cụ thể → Settings → Model → Add Model.
Điền URL backend (vd http://host.docker.internal:9090/predict) và token nếu backend của bạn cần.
Bật “Use model predictions”.
Token ở “Create New Token” là token của Label Studio để bạn gọi REST API (import/export, tạo project, v.v.), không phải để khai báo model.

#
Đã thêm file cấu hình nhãn mẫu:

mydata/label_config_intent_entities.xml: hiển thị text và context, chọn Intent, gán Entities, nhập Answer, nhập JSON map cho API payload, và ô gợi ý model.
Cách dùng trong Label Studio:

Vào project → Settings → Labeling Setup → Open in Editor → dán nội dung file này → Save.
Đảm bảo ML backend trả về:
[{
  "result": [{
    "from_name": "model",
    "to_name": "text",
    "type": "text",
    "value": {"text": "<gợi ý LLM>"}
  }]
}]
Import dữ liệu (ví dụ mydata/sample.jsonl). Mỗi task sẽ hiển thị text + context; bạn chọn intent, tô entities, điền answer, và map sang JSON payload cho flow API.

#
Chọn như sau cho case chatbot với file JSONL/CSV mỗi dòng là một task:

Ở bước “Nhập dữ liệu”: bật “Danh sách nhiệm vụ” (mỗi dòng/bản ghi = 1 task). “Chuỗi thời gian hoặc toàn bộ tệp văn bản” chỉ dùng khi bạn muốn coi cả file là 1 task duy nhất (hoặc dạng time series).
Ở “Thiết lập nhãn”: chọn “Mẫu tùy chỉnh” (Custom template), mở Editor và dán nội dung mydata/label_config_intent_entities.xml, rồi Save.
Sau đó bấm “Cứu/Save” để tạo dự án. Khi mở một task, bạn sẽ thấy text + context, chọn intent, gán entity, điền answer/payload. Nếu đã gắn ML backend, bật “Use model predictions” trong Project Settings → Model để nhận gợi ý.

#
Bạn đã import xong. Giờ annotate và (nếu có) bật ML backend:

Mở một task: bấm vào dấu <> ở cột text/context.

Trong màn hình labeling:

Chọn Intent (Choices).
Tô Entities (Labels) trên đoạn text nếu cần.
Điền Answer (tóm tắt/câu trả lời).
Điền Mapped API payload (JSON bạn muốn feed vào flow).
Nếu đã gắn ML backend, ô “Model Suggestion” sẽ có gợi ý; bạn có thể copy/sửa.
Bấm Submit/Save để hoàn tất task.
Bật ML backend (nếu chưa): Project Settings → Model → Add Model → URL backend /predict (vd http://host.docker.internal:9090/predict) → bật “Use model predictions” → Save.

Sau khi annotate đủ, Export để lấy JSON/CSV phục vụ training/gắn vào gateway.

Nếu cần chỉnh nhãn/intent/entities, sửa file mydata/label_config_intent_entities.xml và cập nhật lại trong Labeling Setup.

# 
Điền như sau (giả sử backend chạy trên máy host, port 9090):

Name: gateway-llm (tùy bạn).
Backend URL: http://host.docker.internal:9090/predict
Nếu backend chạy trong chính container LS hoặc cùng network docker-compose: dùng http://<service-name>:9090/predict.
Nếu backend ở host nhưng không dùng Docker for Windows: dùng IP thật của máy (vd http://192.168.x.x:9090/predict).
Authentication: No Authentication (trừ khi backend yêu cầu token → chọn Bearer và nhập token, hoặc thêm header trong “extra params” dạng {"Authorization": "Bearer <token>"}).
Interactive preannotations: bật để mỗi lần mở task sẽ gọi backend.
Sau đó bấm “Validate and Save”. Mở một task, ô “Model Suggestion” sẽ được điền nếu backend trả về schema:

[{
  "result": [{
    "from_name": "model",
    "to_name": "text",
    "type": "text",
    "value": {"text": "<gợi ý LLM>"}
  }]
}]
Nếu chưa có backend, cần chạy adapter FastAPI trước rồi mới kết nối.

# cập nhật endpint /predicts cho loại dataset bạn cần validater và tên của models để phân loại nó 
/predict là endpoint để Label Studio gọi lấy “pre-label” cho mỗi task. Yêu cầu:

Request: POST JSON dạng {"data": {...}}, trong đó {...} chứa các field mà bạn import vào project (ví dụ text, context).
Response: một mảng, mỗi phần tử có result (danh sách output gắn nhãn) và score. Ví dụ với label config hiện tại:
[{
  "result": [{
    "from_name": "model",
    "to_name": "text",
    "type": "text",
    "value": {"text": "<gợi ý LLM hoặc JSON payload>"}
  }],
  "score": 0.9
}]
from_name/to_name/type phải khớp với config (model → text, type text).

Plan để thêm controller /predict vào FastAPI chatbot hiện có:

Định nghĩa input model: nhận data: dict (hoặc cụ thể hóa text: str, context: Optional[str]).
Thêm route POST /predict.
Trong handler: lấy text/context từ req.data, gọi flow/chatbot sẵn có (logic bạn đã có), lấy kết quả gợi ý.
Map kết quả sang schema Label Studio (như trên), trả về list.
Test bằng curl/HTTPie; sau đó cấu hình Backend URL trong Label Studio tới endpoint này.
Mẫu code thêm vào FastAPI app (thay call_flow bằng hàm hiện tại của bạn):

from typing import Any, Dict, List, Optional
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class LSRequest(BaseModel):
    data: Dict[str, Any]

async def call_flow(question: str, context: Optional[str]) -> str:
    # TODO: gọi flow/chatbot của bạn, trả về gợi ý text hoặc JSON
    return f"Summary/intent/entities for: {question}"

@app.post("/predict")
async def predict(req: LSRequest) -> List[Dict[str, Any]]:
    text = req.data.get("text")
    context = req.data.get("context")
    if not text:
        return [{"result": [], "score": 0.0}]

    suggestion = await call_flow(text, context)

    return [{
        "result": [{
            "from_name": "model",
            "to_name": "text",
            "type": "text",
            "value": {"text": suggestion}
        }],
        "score": 0.9
    }]
Test nhanh:

curl -X POST http://localhost:9090/predict \
  -H "Content-Type: application/json" \
  -d '{"data": {"text": "Giới thiệu ngắn về Bumbee AI", "context": "API group: marketing..."}}'
Sau khi chạy server, vào Label Studio → Project Settings → Model → Backend URL: http://host.docker.internal:9090/predict (hoặc địa chỉ tương ứng) → Validate and Save → bật “Use model predictions”.

# Label Studio wrapper API (dành cho RAG 3rd party)
Env bắt buộc: `LABEL_STUDIO_BASE`, `LABEL_STUDIO_TOKEN` (mặc định timeout 60s, không cần auth riêng cho endpoint này).

- `POST /label/projects` with body `{"name": "...", "description": "...", "label_config": "<optional xml>"}` → tạo project trên Label Studio, trả về `{"project_id": 123}`. Nếu không gửi `label_config` sẽ dùng template mặc định (Text + Textarea).
- `GET /label/projects` → trả `{"projects": [{"id":..,"name":..,"description":..}, ...]}`.
- `POST /label/tasks` with body `{"project_id":123,"samples":[{"data":{...},"meta":{},"predictions":[...]}],"dataset_id":"ds1","tags":["finance"]}` → import tasks vào project, auto nhét `dataset_id` + `tags` vào `task.meta` nếu chưa có. Trả `{"imported": N, "project_id":123}`.
- `GET /label/tasks?project_id=123` → proxy danh sách tasks gốc từ Label Studio.

Base URL chính là `LABEL_STUDIO_BASE` (ví dụ http://host.docker.internal:8080), token là `LABEL_STUDIO_TOKEN` (PAT trong Account & Settings). Payload samples có thể giữ nguyên schema của Label Studio (data/meta/predictions). Tags/dataset_id được thêm vào meta nếu chưa có.
