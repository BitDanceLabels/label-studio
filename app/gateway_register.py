"""
Simple gateway registration helper for this service.

Environment variables:
- SERVICE_NAME: name shown in gateway registry (default: label-studio)
- SERVICE_BASE_URL: base URL that gateway calls (default: http://127.0.0.1:8080)
- GATEWAY_URL: gateway URL (default: http://127.0.0.1:30090)
- GATEWAY_PREFIX: optional prefix for gateway paths (e.g. /rag)
- REGISTER_RETRIES: retry attempts (default: 5)
- REGISTER_DELAY: delay between retries seconds (default: 1.0)
"""
import logging
import os
import time
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)

SERVICE_NAME = os.getenv('SERVICE_NAME', 'label-studio')
SERVICE_BASE_URL = os.getenv('SERVICE_BASE_URL', 'http://127.0.0.1:8080')
GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://127.0.0.1:30033')
GATEWAY_PREFIX = os.getenv('GATEWAY_PREFIX', '')
REGISTER_RETRIES = int(os.getenv('REGISTER_RETRIES', '5'))
REGISTER_DELAY = float(os.getenv('REGISTER_DELAY', '1.0'))


def _with_prefix(path: str) -> str:
    if not GATEWAY_PREFIX:
        return path
    return f'{GATEWAY_PREFIX.rstrip("/")}{path}'


def build_routes() -> List[Dict]:
    """Routes we expose via gateway (wrapper endpoints + health)."""
    return [
        {
            'name': 'label-projects-create',
            'method': 'POST',
            'gateway_path': _with_prefix('/label/projects'),
            'upstream_path': '/label/projects',
            'summary': 'Create Label Studio project',
            'description': 'Proxy to Label Studio /api/projects via wrapper.',
        },
        {
            'name': 'label-projects-list',
            'method': 'GET',
            'gateway_path': _with_prefix('/label/projects'),
            'upstream_path': '/label/projects',
            'summary': 'List Label Studio projects',
            'description': 'Proxy to Label Studio /api/projects via wrapper.',
        },
        {
            'name': 'label-tasks-import',
            'method': 'POST',
            'gateway_path': _with_prefix('/label/tasks'),
            'upstream_path': '/label/tasks',
            'summary': 'Import tasks into Label Studio project',
            'description': 'Proxy to Label Studio /api/projects/{id}/import via wrapper.',
        },
        {
            'name': 'label-tasks-list',
            'method': 'GET',
            'gateway_path': _with_prefix('/label/tasks'),
            'upstream_path': '/label/tasks',
            'summary': 'List tasks in a Label Studio project',
            'description': 'Proxy to Label Studio /api/tasks via wrapper.',
        },
        {
            'name': 'label-health',
            'method': 'GET',
            'gateway_path': _with_prefix('/health/'),
            'upstream_path': '/health/',
            'summary': 'Service healthcheck',
            'description': 'Health endpoint for the service.',
        },
    ]


def register_gateway() -> bool:
    """Register this service with the gateway."""
    if not GATEWAY_URL or not SERVICE_BASE_URL:
        logger.warning('Missing GATEWAY_URL or SERVICE_BASE_URL; skip registration')
        return False

    payload = {
        'name': SERVICE_NAME,
        'base_url': SERVICE_BASE_URL.rstrip('/'),
        'routes': build_routes(),
    }
    endpoint = GATEWAY_URL.rstrip('/') + '/gateway/register'

    for attempt in range(1, REGISTER_RETRIES + 1):
        try:
            resp = requests.post(endpoint, json=payload, timeout=5)
            resp.raise_for_status()
            logger.info(
                'Gateway registered (%s) base_url=%s routes=%s prefix=%s',
                SERVICE_NAME,
                SERVICE_BASE_URL,
                len(payload['routes']),
                GATEWAY_PREFIX or '',
            )
            return True
        except Exception as exc:
            logger.warning(
                'Gateway registration failed attempt %s/%s: %s',
                attempt,
                REGISTER_RETRIES,
                exc,
            )
            time.sleep(REGISTER_DELAY)
    return False


if __name__ == '__main__':
    success = register_gateway()
    if not success:
        raise SystemExit(1)
