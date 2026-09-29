"""Celery application for asynchronous PostgreSQL -> Elasticsearch sync.

The broker (RabbitMQ) and result backend come from environment variables
(CELERY_BROKER_URL / CELERY_RESULT_BACKEND); nothing is hard-coded here.

Start a worker from backend/ with:
    celery -A app.celery_app:celery_app worker --loglevel=info
"""
from celery import Celery

from .core.settings import settings


def make_celery() -> Celery:
    app = Celery(
        "ecommerce_orders",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_default_queue="order_sync",
        # Ack only after the task succeeds: a crashed worker redelivers the
        # message and the (idempotent) task runs again instead of being lost.
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
    )
    return app


celery_app = make_celery()

# Register task modules. Placed after `celery_app` exists so
# app.tasks.order_sync / app.tasks.product_sync can do
# `from ..celery_app import celery_app` without a circular import.
from .tasks import order_sync, product_sync  # noqa: F401,E402
