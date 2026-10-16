"""Thin HTTP client for the payments API. Shared by the agent tools and the UI."""
import os

import httpx

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
http = httpx.Client(base_url=API_URL, timeout=10)


def call(method: str, path: str, **kwargs):
    """Return the JSON body, or {"error": ..., "status_code": ...} on failure."""
    try:
        response = http.request(method, path, **kwargs)
    except httpx.HTTPError:
        return {"error": "Payments service is unreachable", "status_code": 503}
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        return {"error": detail, "status_code": response.status_code}
    return response.json()
