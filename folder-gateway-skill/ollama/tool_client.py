"""
Simple WebSocket tool client that bridges Gateway jobs to a local Ollama instance.

Usage:
    pip install websockets httpx
    python tool_client.py --gateway ws://<gateway-host>:30091/ws/tools/ollama-vps --ollama http://127.0.0.1:11434
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
logger = logging.getLogger("tool-client")


async def handle_ollama_chat(payload: Dict[str, Any], base_urls: list[str]) -> Dict[str, Any]:
    """
    Call Ollama chat API. Tries primary then fallbacks in order.
    Includes a lenient JSON parser for non-stream responses that may contain
    multiple JSON objects or extra whitespace.
    """
    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        for base_url in base_urls:
            url = base_url.rstrip("/") + "/api/chat"
            try:
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
            except Exception as exc:
                last_exc = exc
                logger.warning("Ollama call failed via %s: %s", url, exc)
                continue
    if last_exc:
        raise last_exc
    raise RuntimeError("No Ollama endpoints configured")


async def run_client(
    gateway_ws: str,
    tool_id: str,
    base_url: str,
    token: str | None = None,
    fallback_base_url: str | None = None,
) -> None:
    while True:
        try:
            target_ws = gateway_ws.rstrip("/")
            expected_suffix = f"/ws/tools/{tool_id}"
            if not target_ws.endswith(expected_suffix):
                target_ws = target_ws + expected_suffix
            logger.info("Connecting to gateway %s as %s", target_ws, tool_id)
            base_urls = [base_url]
            if fallback_base_url:
                base_urls.append(fallback_base_url)
            async with websockets.connect(target_ws) as ws:
                pc_id = os.getenv("PC_ID")
                registration = {
                    "tool_id": tool_id,
                    "capabilities": ["ollama", "ollama_chat"],
                    "base_url": base_url,
                    "metadata": {
                        "kind": "ollama",
                        "actions": ["ollama_chat"],
                        "schemas": {
                            "ollama_chat": {
                                "request_example": {
                                    "model": "gpt-oss:latest",
                                    "messages": [
                                        {"role": "system", "content": "You are a helpful assistant."},
                                        {"role": "user", "content": "Viết một đoạn giới thiệu ngắn về Bumbee AI."},
                                    ],
                                    "stream": False,
                                },
                                "response_example": {
                                    "status": "ok",
                                    "result": {"message": {"content": "Bumbee AI là nền tảng ..."}},
                                },
                            }
                        },
                    },
                    "schemas": {
                        "ollama_chat": {
                            "request_example": {
                                "model": "gpt-oss:latest",
                                "messages": [
                                    {"role": "system", "content": "You are a helpful assistant."},
                                    {"role": "user", "content": "Viết một đoạn giới thiệu ngắn về Bumbee AI."},
                                ],
                                "stream": False,
                            },
                        }
                    },
                    "pc_id": pc_id,
                    "token": token,
                }
                await ws.send(json.dumps(registration))
                ack = await ws.recv()
                logger.info("Registered: %s", ack)

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
                    if message.get("type") != "job":
                        continue
                    job_id = message.get("job_id")
                    action = message.get("action")
                    payload = message.get("payload") or {}
                    try:
                        if action == "ollama_chat":
                            result = await handle_ollama_chat(payload, base_urls)
                        else:
                            raise ValueError(f"Unsupported action: {action}")
                        response = {"job_id": job_id, "status": "ok", "result": result}
                    except Exception as exc:
                        logger.warning("Job failed: %s", exc)
                        response = {"job_id": job_id, "status": "error", "error": str(exc)}
                    await ws.send(json.dumps(response))
        except Exception as exc:
            logger.warning("WS disconnected (%s), reconnecting in 5s", exc)
            await asyncio.sleep(5)


def parse_args():
    # Auto-load .env if present so GATEWAY_WS/TOOL_ID/OLLAMA_BASE_URL are picked up.
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gateway",
        default=os.getenv("GATEWAY_WS", "ws://localhost:30091"),
        help="Gateway WS base (we append /ws/tools/{tool-id} if missing)",
    )
    parser.add_argument("--tool-id", default=os.getenv("TOOL_ID", "ollama-vps"))
    parser.add_argument(
        "--ollama",
        default=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        help="Local Ollama base URL (override with env OLLAMA_BASE_URL)",
    )
    parser.add_argument(
        "--fallback-ollama",
        default=os.getenv("OLLAMA_FALLBACK_URL", "http://127.0.0.1:11434"),
        help="Optional fallback Ollama base URL if primary fails (env OLLAMA_FALLBACK_URL).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=os.getenv("OLLAMA_PORT"),
        help="Optional port to build base URL like http://127.0.0.1:{port} (overrides --ollama if provided).",
    )
    parser.add_argument(
        "--pc-id",
        default=os.getenv("PC_ID"),
        help="Identifier for this machine; if set, included in tool registration (env PC_ID).",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("PC_TOKEN"),
        help="Token issued with pc_id; will be sent with registration (env PC_TOKEN).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.port:
        os.environ["OLLAMA_BASE_URL"] = f"http://127.0.0.1:{args.port}"
        args.ollama = os.environ["OLLAMA_BASE_URL"]
    if args.pc_id:
        os.environ["PC_ID"] = args.pc_id
    asyncio.run(
        run_client(
            args.gateway,
            args.tool_id,
            args.ollama,
            token=args.token,
            fallback_base_url=args.fallback_ollama,
        )
    )
