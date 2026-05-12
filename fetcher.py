"""
fetcher.py — Politely fetch standings.cfm for one or many divisions.

Design principles:
- Be polite by default: rate-limited, identifying User-Agent, retries with backoff
- Cache aggressively: re-runs during development should NOT re-hit NCSA
- Fail loudly on unexpected responses, gracefully on empty data
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

NCSA_BASE = "https://www.ncsanj.com"
STANDINGS_URL = f"{NCSA_BASE}/standings.cfm"

# Identify ourselves clearly to NCSA admins. Set SCRAPER_CONTACT in the
# environment (or .env) so the User-Agent includes a real contact address.
import os as _os
_contact = _os.getenv("SCRAPER_CONTACT", "your-email@example.com")
USER_AGENT = (
    "TenaflyStandingsBot/0.1 "
    f"(parent-side project; polite, max 1 req/2s, contact: {_contact})"
)


log = logging.getLogger(__name__)


@dataclass
class FetchResult:
    division: str
    html: str
    from_cache: bool
    status_code: int


class StandingsFetcher:
    """
    Stateful fetcher with rate-limiting and disk caching.

    Usage:
        fetcher = StandingsFetcher(cache_dir=Path("./cache"))
        result = fetcher.fetch("B12B")
        for division in ["B12B", "B10A", ...]:
            r = fetcher.fetch(division)  # rate-limited automatically
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        min_delay_seconds: float = 2.0,
        cache_ttl_seconds: int = 60 * 60 * 12,  # 12 hours
        user_agent: str = USER_AGENT,
        timeout_seconds: float = 15.0,
    ):
        self.cache_dir = cache_dir
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_delay = min_delay_seconds
        self.cache_ttl = cache_ttl_seconds
        self.timeout = timeout_seconds
        self._last_request_at = 0.0
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })

    # ---- caching --------------------------------------------------------

    def _cache_path(self, division: str) -> Optional[Path]:
        if self.cache_dir is None:
            return None
        # Hashing is overkill for division names, but keeps file names safe.
        h = hashlib.sha1(division.encode()).hexdigest()[:8]
        return self.cache_dir / f"{division}_{h}.html"

    def _read_cache(self, division: str) -> Optional[str]:
        path = self._cache_path(division)
        if path is None or not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > self.cache_ttl:
            return None
        return path.read_text()

    def _write_cache(self, division: str, html: str) -> None:
        path = self._cache_path(division)
        if path is not None:
            path.write_text(html)

    # ---- rate limiting --------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_at
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)

    # ---- main API -------------------------------------------------------

    def fetch(self, division: str, *, force_refresh: bool = False) -> FetchResult:
        """
        Fetch the standings HTML for a given division. Uses cache when valid.
        """
        if not force_refresh:
            cached = self._read_cache(division)
            if cached is not None:
                log.info("cache hit: %s", division)
                return FetchResult(division, cached, from_cache=True, status_code=200)

        self._wait_for_rate_limit()
        log.info("fetching %s from network", division)

        # NCSA's form posts `div=<DIVISION>` and `getGames=Enter`
        response = self._session.post(
            STANDINGS_URL,
            data={"div": division, "getGames": "Enter"},
            timeout=self.timeout,
            allow_redirects=True,
        )
        self._last_request_at = time.time()

        if response.status_code != 200:
            raise RuntimeError(
                f"NCSA returned status {response.status_code} for {division}"
            )

        html = response.text
        self._write_cache(division, html)
        return FetchResult(division, html, from_cache=False, status_code=200)
