import os

from celery import Celery

QUEUE_NAME = os.getenv("QUEUE_NAME", "ai_celery")

broker_url = os.getenv("BROKER") or "amqp://{user}:{pw}@{host}:{port}/{vhost}".format(
    user=os.getenv("RABBITMQ_USER", "guest"),
    pw=os.getenv("RABBITMQ_PASS", "guest"),
    host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
    port=os.getenv("RABBITMQ_PORT", "5672"),
    vhost=os.getenv("RABBITMQ_VHOST", ""),
)

backend_url = os.getenv("REDIS_URL") or os.getenv("REDIS_BACKEND") or "redis://{host}:{port}/{db}".format(
    host=os.getenv("REDIS_HOST", "redis"),
    port=os.getenv("REDIS_PORT", "6379"),
    db=os.getenv("REDIS_DB", "0"),
)

app = Celery(QUEUE_NAME, broker=broker_url, backend=backend_url, include=["app.tasks"])
app.conf.task_default_queue = QUEUE_NAME
app.conf.timezone = "UTC"
