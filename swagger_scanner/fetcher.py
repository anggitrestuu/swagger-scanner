"""Fetch OpenAPI JSON from URL."""

import requests


def fetch_openapi(url: str) -> dict:
    """Fetch OpenAPI JSON from URL.

    Args:
        url: URL to the OpenAPI JSON specification

    Returns:
        Parsed JSON as dictionary

    Raises:
        requests.RequestException: If fetch fails
        ValueError: If response is not valid JSON
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()
