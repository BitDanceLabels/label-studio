# Ollama gateway bridge (WS tools)

This shows how to connect a remote Ollama host to the gateway via WebSocket, so the gateway can dispatch jobs to that host.
cd C:\Users\Admin\OneDrive\Desktop\FRIENDIFY-AI\aiservices\aimicroservices\service\ai-service\ollama
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install websockets httpx
cp .env.example .env
copy .env.example .env

## Gateway side (runs on local PC)
- Ensure the gateway is running (e.g. `uvicorn app.main:app --reload --port 30091`). Install WS support if needed: `pip install "uvicorn[standard]" websockets`.
- New endpoints:
  - `WS /ws/tools/{tool_id}`: remote tools connect here.
  - `GET /gateway/tools`: list connected tools.
  - `POST /gateway/tools/{tool_id}/jobs`: generic job dispatcher (Swagger shows schemas).
  - `POST /gateway/tools/{tool_id}/ollama/chat`: typed helper for Ollama chat (shows in Swagger).
  - `GET /docs`: Swagger UI for the above.

## Remote side (runs on VPS/other PC)
1) Install deps: `pip install websockets httpx`
2) Prepare env (example in `env_sample`):
   ```bash
   export GATEWAY_WS=ws://<gateway-host>:30091  # client will append /ws/tools/${TOOL_ID}
   export TOOL_ID=ollama-vps
   export OLLAMA_BASE_URL=http://127.0.0.1:11434
   ```
3) Run the tool client, pointing at the gateway WS URL and local Ollama:
   ```bash
   python tool_client.py \
     --gateway ${GATEWAY_WS} \
     --ollama ${OLLAMA_BASE_URL} \
     --tool-id ${TOOL_ID}
   ```
   Replace `gateway-host` with your public/LAN IP (e.g. `192.168.1.253` if reachable, or tunnel/port-forward).
4) The client registers itself and keeps heartbeats. When it receives a `job`, it forwards to local Ollama `/api/chat` and returns the result.

## Dispatch a test job from the gateway (HTTP)
Send through gateway REST (e.g. via Postman/curl):
```bash
curl -X POST http://localhost:30091/gateway/tools/ollama-vps/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "action": "ollama_chat",
    "payload": {
      "model": "gpt-oss:latest",
      "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Viết một đoạn giới thiệu ngắn về Bumbee AI."}
      ]
    },
    "timeout": 60
  }'
```
You should get back `{"job_id": "...", "status": "ok", "result": { ...ollama response... }}`.

Postman:
- Method: `POST`
- URL: `http://localhost:30091/gateway/tools/ollama-vps/ollama/chat`
- Headers: `Content-Type: application/json`
- Body (raw JSON):
```json
{
  "model": "gpt-oss:latest",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Viết một đoạn giới thiệu ngắn về Bumbee AI."}
  ],
  "stream": false
}
```
Or use the generic jobs endpoint and paste the same payload under `"payload"` with `"action": "ollama_chat"`.

## Notes
- WebSocket is outbound-only from the tool host, so NAT/dynamic IP is OK as long as the gateway address is reachable.
- Use TLS termination (nginx/Caddy) for internet-facing traffic; the sample client skips certificate validation (`verify=False`) for Ollama.
- Add firewall rules to allow the gateway port (e.g., 30091) or tunnel with ngrok/Cloudflare if needed.
- Tool metadata now carries `actions` and `schemas` so you can inspect `/gateway/tools` to see what a tool supports without hardcoding in gateway.
