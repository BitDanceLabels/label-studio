import json
import os
import time
import uuid

import redis

from .celery_app import app


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)


@app.task(name="ai_task_worker.power")
def power(task_id: str, base: float, exp: float) -> dict:
    """Compute power and store a queue-style payload in Redis for gateway polling."""
    start = time.time()
    result = base**exp
    payload = {
        "task_id": task_id,
        "status": {"general_status": "SUCCESS", "queue_status": "SUCCESS"},
        "time": {"start_generate": str(start), "end_generate": str(time.time())},
        "data": {"operation": "power", "base": base, "exp": exp, "result": result},
    }
    _redis_client().set(task_id, json.dumps(payload))
    return payload


@app.task(name="ai_task_worker.echo")
def echo(message: str) -> dict:
    """Simple echo task to verify worker wiring."""
    task_id = uuid.uuid4().hex
    payload = {"task_id": task_id, "status": "SUCCESS", "message": message}
    _redis_client().set(task_id, json.dumps(payload))
    return payload
