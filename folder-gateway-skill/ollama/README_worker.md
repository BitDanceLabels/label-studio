# Ollama Task Worker (gateway dispatch)

This worker connects to the gateway’s task dispatcher over WebSocket and executes Ollama chat jobs.

## Prereqs
- Gateway running with WS support (e.g. `uvicorn app.main:app --host 0.0.0.0 --port 30091`).
- Background-task-service running (for tracking statuses).
- Ollama running locally on the worker host (e.g. `http://127.0.0.1:11434`).
- Install deps: `pip install websockets httpx python-dotenv` (or reuse the service venv).

## Env (example in `env_sample`)
```
GATEWAY_WS=ws://localhost:30091
WORKER_ID=ollama-worker-1
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

## Run the worker
```bash
cd aimicroservices/service/ai-service/ollama
python worker_client.py
```
Flags (override env): `--gateway`, `--worker-id`, `--ollama`.

## What it does
- Connects to `ws://<gateway>/ws/workers/{worker_id}`.
- Registers capability `ollama_chat_task` and advertises example schemas in metadata.
- Waits for tasks with `capability: "ollama_chat_task"`, calls local Ollama `/api/chat`, and sends `task_result` back to gateway.

## How to dispatch a job (Postman/curl)
Endpoint (gateway): `POST http://localhost:30091/gateway/tasks/dispatch`
Body:
```json
{
  "capability": "ollama_chat_task",
  "payload": {
    "model": "gpt-oss:latest",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Viết một đoạn giới thiệu ngắn về Bumbee AI."}
    ],
    "stream": false
  }
}
```
Response returns `tracking_id`; check status via background-task-service `/api/tasks/{tracking_id}` (or your existing gateway route if you expose it).

## Notes
- For internet tunnels (ngrok/CF), set `GATEWAY_WS` to `wss://<host>` if TLS.
- If Ollama returns non-standard JSON, worker has a fallback parser for the first valid JSON line.
