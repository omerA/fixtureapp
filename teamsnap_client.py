"""
Thin client for TeamSnap APIv3 (Collection+JSON).

The API returns hypermedia documents; we pull the data array out and
convert each item's {name, value} pairs into plain dicts.
"""
from __future__ import annotations

import time
from typing import Any

import requests


_CONTACT = "fixture-app"
_BASE = "https://api.teamsnap.com/v3"
_MIN_DELAY = 0.5  # seconds between calls


class TeamSnapError(Exception):
    """Raised when the TeamSnap API returns an unexpected response."""
    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        super().__init__(f"TeamSnap API {status_code}: {message}")


class TeamSnapClient:
    def __init__(self, access_token: str):
        self._token = access_token
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "User-Agent": f"FixtureApp/1.0 ({_CONTACT})",
            "Accept": "application/vnd.collection+json",
        })
        self._last_call = 0.0

    def _get(self, path: str, params: dict | None = None) -> dict:
        elapsed = time.monotonic() - self._last_call
        if elapsed < _MIN_DELAY:
            time.sleep(_MIN_DELAY - elapsed)
        url = f"{_BASE}{path}"
        resp = self._session.get(url, params=params, timeout=15)
        self._last_call = time.monotonic()
        if resp.status_code == 401:
            raise TeamSnapError(401, "Unauthorized — token may have expired")
        if not resp.ok:
            raise TeamSnapError(resp.status_code, resp.text[:200])
        return resp.json()

    @staticmethod
    def _items(collection: dict) -> list[dict]:
        """Convert Collection+JSON items to plain dicts."""
        items = collection.get("collection", {}).get("items", [])
        result = []
        for item in items:
            obj: dict[str, Any] = {"href": item.get("href", "")}
            for pair in item.get("data", []):
                obj[pair["name"]] = pair.get("value")
            result.append(obj)
        return result

    def get_teams(self, user_id: str | int) -> list[dict]:
        """Return all teams the authenticated user is a member of."""
        data = self._get("/teams/search", params={"user_id": str(user_id)})
        return self._items(data)

    def get_members(self, team_id: int | str) -> list[dict]:
        """Return roster members for a given team."""
        data = self._get("/members/search", params={"team_id": team_id})
        return self._items(data)
