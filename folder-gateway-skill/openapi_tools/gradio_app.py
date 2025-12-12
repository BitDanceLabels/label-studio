"""Gradio UI to exercise every endpoint from the OpenAPI spec."""

from __future__ import annotations

import os
from pathlib import Path
import json

import gradio as gr
import httpx

from .openapi_utils import (
    body_example,
    collect_endpoints,
    default_base_url,
    load_spec,
    parse_json_input,
    replace_path_params,
)

DEFAULT_SPEC_PATH = Path(__file__).resolve().parents[1] / "openapi.json"
DEFAULT_SOURCE = os.getenv("OPENAPI_SOURCE", str(DEFAULT_SPEC_PATH))


def _label(idx: int, ep: dict) -> str:
    tags = ", ".join(ep["tags"])
    return f"{idx}: {ep['method']} {ep['path']} [{tags}]"


def _pick_endpoint(filtered: list[dict], selected: str) -> dict | None:
    if not selected:
        return filtered[0] if filtered else None
    try:
        idx = int(selected.split(":", 1)[0])
    except Exception:
        idx = 0
    return filtered[idx] if 0 <= idx < len(filtered) else None


def refresh_spec(source: str, tag: str) -> tuple:
    spec = load_spec(source)
    endpoints = collect_endpoints(spec)
    tags = sorted({t for ep in endpoints for t in ep["tags"]})
    filtered = endpoints if tag in ("", "<All>") else [ep for ep in endpoints if tag in ep["tags"]]
    labels = [_label(i, ep) for i, ep in enumerate(filtered)]
    first_ep = filtered[0] if filtered else None
    media_type, example_body = body_example(first_ep["request_body"] if first_ep else {})
    return (
        spec,
        filtered,
        gr.Dropdown.update(choices=["<All>"] + tags, value=tag if tag in tags else "<All>"),
        gr.Dropdown.update(choices=labels, value=labels[0] if labels else None),
        default_base_url(spec),
        example_body,
        media_type,
        first_ep["summary"] if first_ep else "",
    )


def update_body(selected: str, filtered: list[dict]) -> tuple[str, str, str]:
    ep = _pick_endpoint(filtered, selected)
    media_type, example_body = body_example(ep["request_body"] if ep else {})
    return example_body, media_type, ep["summary"] if ep else ""


def call_api(
    selected: str,
    filtered: list[dict],
    base_url: str,
    query_json: str,
    path_json: str,
    headers_json: str,
    body_json: str,
    media_type: str,
) -> tuple[str, str, str]:
    ep = _pick_endpoint(filtered, selected)
    if not ep:
        return "No endpoint", "", ""

    path_values = parse_json_input(path_json)
    query_values = parse_json_input(query_json)
    header_values = parse_json_input(headers_json)
    url_path = replace_path_params(ep["path"], path_values)
    url = f"{base_url.rstrip('/')}{url_path}"

    try:
        resp = httpx.request(
            ep["method"],
            url,
            params=query_values or None,
            headers=header_values or None,
            json=parse_json_input(body_json) if media_type == "application/json" else None,
            content=None if media_type == "application/json" else (body_json or None),
            timeout=30.0,
        )
    except Exception as exc:  # noqa: BLE001
        return f"Request failed: {exc}", "", ""

    headers_text = "\n".join(f"{k}: {v}" for k, v in resp.headers.items())
    try:
        body = resp.json()
        body_text = json.dumps(body, indent=2, ensure_ascii=False)
    except Exception:
        body_text = resp.text

    return f"{resp.status_code} {resp.reason_phrase}", headers_text, body_text


with gr.Blocks(title="Gateway API Explorer (Gradio)") as demo:
    spec_state = gr.State({})
    filtered_state = gr.State([])
    media_state = gr.State("application/json")

    gr.Markdown("# Gateway API Explorer (Gradio)")
    with gr.Row():
        source_input = gr.Textbox(value=DEFAULT_SOURCE, label="OpenAPI URL or file")
        tag_input = gr.Dropdown(choices=["<All>"], value="<All>", label="Tag")
        reload_btn = gr.Button("Reload")
    summary_box = gr.Markdown("")
    endpoint_dropdown = gr.Dropdown(choices=[], label="Endpoint", interactive=True)
    base_url_input = gr.Textbox(label="Base URL", value="")

    query_box = gr.Textbox(label="Query params (JSON)", lines=3, placeholder='{"q": "text"}')
    path_box = gr.Textbox(label="Path params (JSON)", lines=2, placeholder='{"item_id": 123}')
    headers_box = gr.Textbox(label="Headers (JSON)", lines=2, placeholder='{"Authorization": "Bearer ..."}')
    body_box = gr.Code(label="Request body (JSON)", language="json", value="")

    send_btn = gr.Button("Send request")
    status_out = gr.Textbox(label="Status")
    headers_out = gr.Textbox(label="Response headers")
    body_out = gr.Code(label="Response body", language="json")

    reload_outputs = [
        spec_state,
        filtered_state,
        tag_input,
        endpoint_dropdown,
        base_url_input,
        body_box,
        media_state,
        summary_box,
    ]

    reload_btn.click(
        fn=refresh_spec,
        inputs=[source_input, tag_input],
        outputs=reload_outputs,
    )
    tag_input.change(
        fn=refresh_spec,
        inputs=[source_input, tag_input],
        outputs=reload_outputs,
    )
    endpoint_dropdown.change(
        fn=update_body,
        inputs=[endpoint_dropdown, filtered_state],
        outputs=[body_box, media_state, summary_box],
    )
    send_btn.click(
        fn=call_api,
        inputs=[
            endpoint_dropdown,
            filtered_state,
            base_url_input,
            query_box,
            path_box,
            headers_box,
            body_box,
            media_state,
        ],
        outputs=[status_out, headers_out, body_out],
    )

    demo.load(
        fn=refresh_spec,
        inputs=[source_input, tag_input],
        outputs=reload_outputs,
    )

demo.launch()
