import json
import logging
import os

import httpx
import redis
from fastapi import FastAPI
from pydantic import BaseModel, Field
import asyncio
from dotenv import load_dotenv
from celery import Celery
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)
app = FastAPI(title="AI Math Service")

# Load .env if present so REDIS_*, SERVICE_BASE_URL… are picked up locally
load_dotenv()

SERVICE_NAME = os.getenv("SERVICE_NAME", "ai-math-service")
# Default to localhost when running outside Docker
SERVICE_BASE_URL = os.getenv("SERVICE_BASE_URL", "http://127.0.0.1:8082")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8080")
REGISTER_RETRIES = int(os.getenv("REGISTER_RETRIES", "5"))
REGISTER_DELAY = float(os.getenv("REGISTER_DELAY", "1.0"))

BROKER = os.getenv("BROKER") or "amqp://{user}:{pw}@{host}:{port}/{vhost}".format(
    user=os.getenv("RABBITMQ_USER", "guest"),
    pw=os.getenv("RABBITMQ_PASS", "guest"),
    host=os.getenv("RABBITMQ_HOST", "127.0.0.1"),
    port=os.getenv("RABBITMQ_PORT", "5672"),
    vhost=os.getenv("RABBITMQ_VHOST", ""),
)
BACKEND = os.getenv("REDIS_BACKEND") or "redis://:{password}@{host}:{port}/{db}".format(
    password=os.getenv("REDIS_PASS", ""),
    host=os.getenv("REDIS_HOST", "127.0.0.1"),
    port=os.getenv("REDIS_PORT", "6379"),
    db=os.getenv("REDIS_DB", "0"),
)
QUEUE_NAME = os.getenv("AI_QUERY_NAME", "ai_celery")
celery_app = Celery(QUEUE_NAME, broker=BROKER, backend=BACKEND)
celery_app.conf.task_default_queue = QUEUE_NAME

# ---- Schemas (local only) ----
class AddRequest(BaseModel):
    a: float = Field(...)
    b: float = Field(...)

class AddResponse(BaseModel):
    result: float

class MultiplyRequest(AddRequest):
    pass

class MultiplyQueueResponse(BaseModel):
    task_id: str
    status: str


class PowerRequest(BaseModel):
    base: float = Field(...)
    exp: float = Field(...)


class BackgroundTaskRequest(BaseModel):
    entity: str = Field(..., description="Logical category for the task")

# ---- Helpers ----
def _get_redis() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASS") or None,
        db=int(os.getenv("REDIS_DB", "0")),
        decode_responses=True,
    )

async def _register_gateway() -> None:
    if not GATEWAY_URL:
        return
    payload = {
        "name": SERVICE_NAME,
        "base_url": SERVICE_BASE_URL,
        "routes": [
            {
                "name": "ai-math-add",
                "method": "POST",
                "gateway_path": "/v1/ai/math/add",
                "upstream_path": "/api/add",
                "summary": "Add two numbers",
                "description": "Returns the sum of a+b"
            },
            {
                "name": "ai-math-multiply-queue",
                "method": "POST",
                "gateway_path": "/v1/ai/math/multiply",
                "upstream_path": "/api/multiply/queue",
                "summary": "Multiply via queue",
                "description": "Stores result in Redis queue format"
            },
            {
                "name": "ai-math-power-queue",
                "method": "POST",
                "gateway_path": "/v1/ai/math/power",
                "upstream_path": "/api/power/queue",
                "summary": "Power via RabbitMQ queue",
                "description": "Delegates power computation to Celery worker"
            },
            {
                "name": "ai-math-background-task",
                "method": "POST",
                "gateway_path": "/v1/ai/math/background_task",
                "upstream_path": "/api/background_task",
                "summary": "Create a background task placeholder",
                "description": "Initializes a queue-style task in Redis"
            }
        ]
    }
    endpoint = GATEWAY_URL.rstrip("/") + "/gateway/register"
    for attempt in range(1, REGISTER_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(endpoint, json=payload)
                resp.raise_for_status()
            logger.info("Gateway registered (%s) base_url=%s", SERVICE_NAME, SERVICE_BASE_URL)
            return
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Gateway registration failed (attempt %s/%s): %s",
                attempt,
                REGISTER_RETRIES,
                exc,
            )
            await asyncio.sleep(REGISTER_DELAY)

@app.on_event("startup")
async def startup():
    await _register_gateway()

# ---- API ----
@app.post("/api/add", response_model=AddResponse)
async def add_numbers(req: AddRequest) -> AddResponse:
    return AddResponse(result=req.a + req.b)

@app.post("/api/multiply/queue", response_model=MultiplyQueueResponse)
async def multiply_queue(req: MultiplyRequest) -> MultiplyQueueResponse:
    task_id = uuid.uuid4().hex
    product = req.a * req.b
    now = datetime.utcnow().timestamp()
    payload = {
        "task_id": task_id,
        "status": {"general_status": "SUCCESS", "queue_status": "SUCCESS"},
        "time": {"start_generate": str(now), "end_generate": str(now)},
        "data": {"operation": "multiply", "a": req.a, "b": req.b, "result": product},
    }
    _get_redis().set(task_id, json.dumps(payload))
    return MultiplyQueueResponse(task_id=task_id, status="SUCCESS")


@app.post("/api/power/queue", response_model=MultiplyQueueResponse)
async def power_queue(req: PowerRequest) -> MultiplyQueueResponse:
    task_id = uuid.uuid4().hex
    celery_app.send_task(
        "ai_task_worker.power",
        args=(task_id, req.base, req.exp),
        queue=QUEUE_NAME,
    )
    return MultiplyQueueResponse(task_id=task_id, status="PENDING")


@app.post("/api/background_task", response_model=MultiplyQueueResponse)
async def background_task(req: BackgroundTaskRequest) -> MultiplyQueueResponse:
    task_id = uuid.uuid4().hex
    now = datetime.utcnow().timestamp()
    payload = {
        "task_id": task_id,
        "status": {"general_status": "PENDING", "queue_status": "STARTED"},
        "time": {"start_generate": str(now), "end_generate": None},
        "data": {"operation": "background_task", "entity": req.entity},
    }
    _get_redis().set(task_id, json.dumps(payload))
    return MultiplyQueueResponse(task_id=task_id, status="PENDING")


@app.get("/healthz")
async def healthcheck():
    return {"status": "ok"}
