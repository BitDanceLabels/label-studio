"""Streamlit UI that reads OpenAPI and auto-builds request forms per endpoint."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import streamlit as st

from .openapi_utils import (
    body_example,
    collect_endpoints,
    default_base_url,
    load_spec,
    parse_json_input,
    replace_path_params,
    split_parameters,
)

DEFAULT_SPEC_PATH = Path(__file__).resolve().parents[1] / "openapi.json"
DEFAULT_SOURCE = os.getenv("OPENAPI_SOURCE", str(DEFAULT_SPEC_PATH))


@st.cache_data(show_spinner=False)
def fetch_spec(source: str) -> dict:
    return load_spec(source)


def main() -> None:
    st.set_page_config(page_title="Gateway API Explorer", layout="wide")
    st.title("Gateway API Explorer (Streamlit)")

    st.sidebar.header("OpenAPI source")
    source = st.sidebar.text_input("URL or file path", value=DEFAULT_SOURCE)
    if st.sidebar.button("Reload spec"):
        fetch_spec.clear()

    try:
        spec = fetch_spec(source)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load OpenAPI: {exc}")
        return

    endpoints = collect_endpoints(spec)
    if not endpoints:
        st.warning("No endpoints found in OpenAPI spec.")
        return

    tags = sorted({t for ep in endpoints for t in ep["tags"]})
    selected_tag = st.sidebar.selectbox("Tag", options=["<All>"] + tags)

    filtered = endpoints if selected_tag == "<All>" else [ep for ep in endpoints if selected_tag in ep["tags"]]

    if not filtered:
        st.warning("No endpoints found for this tag.")
        return

    endpoint_labels = [f"{ep['method']} {ep['path']} ({', '.join(ep['tags'])})" for ep in filtered]
    idx = st.sidebar.selectbox("Endpoint", options=range(len(filtered)), format_func=lambda i: endpoint_labels[i])
    endpoint = filtered[idx]

    st.subheader(f"{endpoint['method']} {endpoint['path']}")
    if endpoint["summary"]:
        st.write(endpoint["summary"])
    if endpoint["description"]:
        st.caption(endpoint["description"])

    base_url = st.text_input("Base URL", value=default_base_url(spec))

    path_params, query_params, header_params = split_parameters(endpoint["parameters"])
    st.markdown("**Path parameters**")
    path_values = {}
    if not path_params:
        st.write("_None_")
    for p in path_params:
        key = f"path-{p.get('name')}"
        default_val = p.get("schema", {}).get("default", "")
        default_str = "" if default_val is None else str(default_val)
        path_values[p["name"]] = st.text_input(key, value=default_str, label_visibility="collapsed")
        st.caption(f"`{p['name']}` ({p.get('schema', {}).get('type', 'string')}) { '(required)' if p.get('required') else '' }")

    st.markdown("**Query parameters**")
    query_values = {}
    if not query_params:
        st.write("_None_")
    for p in query_params:
        default_val = p.get("schema", {}).get("default", "")
        default = "" if default_val is None else str(default_val)
        query_values[p["name"]] = st.text_input(
            f"query-{p.get('name')}", value=default, label_visibility="collapsed"
        )
        st.caption(f"`{p['name']}` ({p.get('schema', {}).get('type', 'string')})")

    st.markdown("**Header parameters**")
    header_values = {}
    if not header_params:
        st.write("_None_")
    for p in header_params:
        default_val = p.get("schema", {}).get("default", "")
        default = "" if default_val is None else str(default_val)
        header_values[p["name"]] = st.text_input(
            f"header-{p.get('name')}", value=default, label_visibility="collapsed"
        )
        st.caption(f"`{p['name']}` ({p.get('schema', {}).get('type', 'string')})")

    media_type, example_body = body_example(endpoint["request_body"])
    st.markdown("**Request body**")
    body_text = st.text_area(
        "Raw JSON body",
        value=example_body,
        height=200,
        placeholder="{}",
        label_visibility="collapsed",
    )

    if st.button("Send request"):
        url_path = replace_path_params(endpoint["path"], path_values)
        url = f"{base_url.rstrip('/')}{url_path}"
        params = {k: v for k, v in query_values.items() if v != ""}
        headers = {k: v for k, v in header_values.items() if v != ""}
        json_body = parse_json_input(body_text) if media_type == "application/json" else None

        st.info(f"Calling {endpoint['method']} {url}")
        try:
            resp = httpx.request(
                endpoint["method"],
                url,
                params=params or None,
                headers=headers or None,
                json=json_body if media_type == "application/json" else None,
                content=None if media_type == "application/json" else body_text or None,
                timeout=30.0,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Request failed: {exc}")
        else:
            st.success(f"Status: {resp.status_code}")
            st.code("\n".join(f"{k}: {v}" for k, v in resp.headers.items()), language="http")
            try:
                st.json(resp.json())
            except Exception:
                st.code(resp.text)


if __name__ == "__main__":
    main()
