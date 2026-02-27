"""OpenProject REST API v3 client."""

import base64
import os
from typing import Any
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv

load_dotenv()


class OpenProjectClient:
    """Thin wrapper around the OpenProject REST API v3."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or os.getenv("OPENPROJECT_URL", "")).rstrip("/")
        api_key = api_key or os.getenv("OPENPROJECT_API_KEY", "")

        if not self.base_url:
            raise ValueError("OPENPROJECT_URL is required")
        if not api_key:
            raise ValueError("OPENPROJECT_API_KEY is required")

        token = base64.b64encode(f"apikey:{api_key}".encode()).decode()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def get(self, path: str, params: dict | None = None) -> Any:
        url = urljoin(self.base_url + "/", f"api/v3/{path.lstrip('/')}")
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, data: dict) -> Any:
        url = urljoin(self.base_url + "/", f"api/v3/{path.lstrip('/')}")
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def patch(self, path: str, data: dict) -> Any:
        url = urljoin(self.base_url + "/", f"api/v3/{path.lstrip('/')}")
        response = self.session.patch(url, json=data)
        response.raise_for_status()
        return response.json()

    def delete(self, path: str) -> None:
        url = urljoin(self.base_url + "/", f"api/v3/{path.lstrip('/')}")
        response = self.session.delete(url)
        response.raise_for_status()

    def get_all(self, path: str, params: dict | None = None) -> list[dict]:
        """Fetch all pages of a collection endpoint."""
        params = params or {}
        params.setdefault("pageSize", 100)
        params["offset"] = 1
        results = []
        while True:
            data = self.get(path, params)
            elements = data.get("_embedded", {}).get("elements", [])
            results.extend(elements)
            total = data.get("total", 0)
            if len(results) >= total:
                break
            params["offset"] += 1
        return results
