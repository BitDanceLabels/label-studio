"""Shared helpers for loading and working with OpenAPI specs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import httpx
import yaml

ALLOWED_METHODS = {"get", "post", "put", "patch", "delete"}


class OpenAPILoadError(RuntimeError):
    pass


def load_spec(source: str | Path) -> dict:
    """Load OpenAPI spec from URL or local file (json/yaml)."""
    if not source:
        raise OpenAPILoadError("OpenAPI source is empty")

    src = str(source)
    if src.startswith("http://") or src.startswith("https://"):
        try:
            resp = httpx.get(src, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            raise OpenAPILoadError(f"Failed to fetch OpenAPI from URL: {exc}") from exc

    path = Path(src)
    if not path.exists():
        raise OpenAPILoadError(f"File not found: {path}")

    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            data = yaml.safe_load(text)
            if not isinstance(data, dict):
                raise OpenAPILoadError("YAML content is not a mapping")
            return data
        except Exception as exc:  # noqa: BLE001
            raise OpenAPILoadError(f"Failed to parse OpenAPI file: {exc}") from exc


def default_base_url(spec: dict, fallback: str = "http://127.0.0.1:30091") -> str:
    servers = spec.get("servers") or []
    for server in servers:
        url = server.get("url")
        if url:
            return url.rstrip("/")
    return fallback.rstrip("/")


def collect_endpoints(spec: dict) -> list[dict]:
    """Flatten OpenAPI paths into a list of endpoints with metadata."""
    endpoints: list[dict] = []
    for path, methods in (spec.get("paths") or {}).items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.lower() not in ALLOWED_METHODS:
                continue
            op = op or {}
            endpoints.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "tags": op.get("tags") or ["untagged"],
                    "summary": op.get("summary") or "",
                    "description": op.get("description") or "",
                    "operation_id": op.get("operationId") or "",
                    "parameters": op.get("parameters") or [],
                    "request_body": (op.get("requestBody") or {}),
                }
            )
    return endpoints


def example_from_schema(schema: dict) -> Any:
    if not isinstance(schema, dict):
        return ""
    if "example" in schema:
        return schema["example"]
    schema_type = schema.get("type")
    if schema_type == "object":
        props = schema.get("properties") or {}
        return {k: example_from_schema(v) for k, v in props.items()}
    if schema_type == "array":
        return [example_from_schema(schema.get("items", {}))]
    if schema_type in {"integer", "number"}:
        return schema.get("default", 0)
    if schema_type == "boolean":
        return schema.get("default", False)
    return schema.get("default", "")


def body_example(request_body: dict) -> Tuple[str, str]:
    """Return (media_type, example_json_str)."""
    content = (request_body or {}).get("content") or {}
    if not content:
        return "", ""
    # pick application/json first if available
    media_type = "application/json" if "application/json" in content else next(iter(content.keys()), "")
    schema = (content.get(media_type) or {}).get("schema") or {}
    example = example_from_schema(schema)
    try:
        return media_type, json.dumps(example, indent=2, ensure_ascii=False)
    except Exception:
        return media_type, ""


def replace_path_params(path: str, values: Dict[str, Any]) -> str:
    out = path
    for name, val in values.items():
        out = out.replace("{" + name + "}", str(val))
    return out


def parse_json_input(raw: str | None) -> Any:
    text = raw.strip() if raw else ""
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def split_parameters(params: Iterable[dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    path_params: list[dict] = []
    query_params: list[dict] = []
    header_params: list[dict] = []
    for p in params:
        if not isinstance(p, dict):
            continue
        location = p.get("in")
        if location == "path":
            path_params.append(p)
        elif location == "header":
            header_params.append(p)
        else:
            query_params.append(p)
    return path_params, query_params, header_params
