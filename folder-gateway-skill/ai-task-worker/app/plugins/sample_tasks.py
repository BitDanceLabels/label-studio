import json
import time
import uuid

import redis

from app.celery_app import app


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url("redis://redis:6379/0", decode_responses=True)


@app.task(name="app.plugins.sample_tasks.sleep_echo")
def sleep_echo(message: str, delay: float = 1.0) -> dict:
    """Demo plugin task: waits then echoes a message."""
    time.sleep(delay)
    task_id = uuid.uuid4().hex
    payload = {"task_id": task_id, "status": "SUCCESS", "message": message, "delay": delay}
    _redis_client().set(task_id, json.dumps(payload))
    return payload
