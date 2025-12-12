"""
Minimal task worker client for the gateway task dispatcher.

Behavior:
- Connects to WS /ws/workers/{worker_id}
- Registers capabilities: ["ollama_chat_task"]
- Waits for tasks with capability "ollama_chat_task"
- For each task, calls local Ollama /api/chat with the payload
- Sends task_result back to gateway

Usage (from this folder, after filling .env or passing flags):
    python worker_client.py \
      --gateway ws://localhost:30091 \
      --ollama http://127.0.0.1:11434 \
      --worker-id ollama-worker-1
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from typing import Any, Dict

import httpx
import websockets
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("task-worker-client")


async def handle_ollama_chat(payload: Dict[str, Any], base_url: str) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/api/chat"
    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            text = resp.text.strip()
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    return json.loads(line)
                except Exception:
                    continue
            raise


async def run_worker(gateway_ws: str, worker_id: str, base_url: str) -> None:
    while True:
        try:
            target_ws = gateway_ws.rstrip("/")
            expected_suffix = f"/ws/workers/{worker_id}"
            if not target_ws.endswith(expected_suffix):
                target_ws = target_ws + expected_suffix
            logger.info("Connecting to gateway %s as worker %s", target_ws, worker_id)
            async with websockets.connect(target_ws) as ws:
                registration = {
                    "worker_id": worker_id,
                    "capabilities": ["ollama_chat_task"],
                    "metadata": {
                        "kind": "ollama",
                        "actions": ["ollama_chat_task"],
                        "schemas": {
                            "ollama_chat_task": {
                                "request_example": {
                                    "model": "gpt-oss:latest",
                                    "messages": [
                                        {"role": "system", "content": "You are a helpful assistant."},
                                        {"role": "user", "content": "Viết một đoạn giới thiệu ngắn về Bumbee AI."},
                                    ],
                                    "stream": False,
                                }
                            }
                        },
                    },
                }
                await ws.send(json.dumps(registration))
                ack = await ws.recv()
                logger.info("Registered worker: %s", ack)

                async def heartbeat():
                    while True:
                        await asyncio.sleep(15)
                        try:
                            await ws.send(json.dumps({"type": "heartbeat"}))
                        except Exception:
                            return

                hb_task = asyncio.create_task(heartbeat())

                async for raw in ws:
                    try:
                        message = json.loads(raw)
                    except Exception:
                        continue
                    if message.get("type") != "task":
                        continue
                    tracking_id = message.get("tracking_id")
                    capability = message.get("capability")
                    payload = message.get("payload") or {}
                    if capability != "ollama_chat_task":
                        continue
                    try:
                        result = await handle_ollama_chat(payload, base_url)
                        response = {"type": "task_result", "tracking_id": tracking_id, "status": "ok", "result": result}
                    except Exception as exc:
                        logger.warning("Task failed: %s", exc)
                        response = {"type": "task_result", "tracking_id": tracking_id, "status": "error", "error": str(exc)}
                    await ws.send(json.dumps(response))
        except Exception as exc:
            logger.warning("WS worker disconnected (%s), reconnecting in 5s", exc)
            await asyncio.sleep(5)


def parse_args():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", default=os.getenv("GATEWAY_WS", "ws://localhost:30091"), help="Gateway WS base (we append /ws/workers/{worker_id})")
    parser.add_argument("--worker-id", default=os.getenv("WORKER_ID", "ollama-worker-1"))
    parser.add_argument("--ollama", default=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_worker(args.gateway, args.worker_id, args.ollama))
