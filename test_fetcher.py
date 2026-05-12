"""
Test the fetcher end-to-end with a mocked HTTP backend.
Verifies: correct method, URL, form payload, headers, caching behavior, rate limiting.
"""
import json
import logging
import sys
import time
from pathlib import Path

import responses

sys.path.insert(0, str(Path(__file__).parent))
from fetcher import StandingsFetcher, STANDINGS_URL

logging.basicConfig(level=logging.INFO, format="%(message)s")

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "b12b_table.html").read_text()
# Wrap it in a minimal page envelope so it looks like a real response
MOCK_RESPONSE = f"<html><body>{FIXTURE_HTML}</body></html>"


@responses.activate
def test_basic_post_request():
    """Verifies we send a POST with the right form data and User-Agent."""
    responses.add(
        responses.POST, STANDINGS_URL,
        body=MOCK_RESPONSE, status=200, content_type="text/html",
    )

    fetcher = StandingsFetcher(cache_dir=None, min_delay_seconds=0)
    result = fetcher.fetch("B12B")

    assert result.status_code == 200
    assert result.from_cache is False
    assert "B12B" in result.html  # the fixture mentions B12B

    # Inspect what we actually sent
    call = responses.calls[0]
    body = call.request.body
    assert "div=B12B" in body, f"expected div=B12B in body, got: {body}"
    assert "getGames=Enter" in body, f"expected getGames=Enter, got: {body}"
    assert call.request.method == "POST"
    assert "TenaflyStandingsBot" in call.request.headers["User-Agent"]
    print("test_basic_post_request: PASS")


@responses.activate
def test_caching_avoids_second_request(tmp_path):
    """First call hits the network. Second call returns from cache."""
    responses.add(
        responses.POST, STANDINGS_URL,
        body=MOCK_RESPONSE, status=200,
    )

    fetcher = StandingsFetcher(cache_dir=tmp_path, min_delay_seconds=0)
    r1 = fetcher.fetch("B12B")
    r2 = fetcher.fetch("B12B")

    assert r1.from_cache is False
    assert r2.from_cache is True
    assert r1.html == r2.html
    assert len(responses.calls) == 1, f"expected 1 call, got {len(responses.calls)}"
    print("test_caching_avoids_second_request: PASS")


@responses.activate
def test_rate_limiting_enforces_delay():
    """Two consecutive uncached requests must be spaced by min_delay."""
    responses.add(
        responses.POST, STANDINGS_URL,
        body=MOCK_RESPONSE, status=200,
    )
    responses.add(
        responses.POST, STANDINGS_URL,
        body=MOCK_RESPONSE, status=200,
    )

    fetcher = StandingsFetcher(cache_dir=None, min_delay_seconds=0.3)
    t0 = time.time()
    fetcher.fetch("B12B")
    fetcher.fetch("B10A")
    elapsed = time.time() - t0
    assert elapsed >= 0.3, f"expected >=0.3s elapsed, got {elapsed:.3f}s"
    print(f"test_rate_limiting_enforces_delay: PASS ({elapsed:.3f}s elapsed for 2 requests)")


@responses.activate
def test_non_200_raises():
    """Unexpected status codes should raise, not silently produce bad data."""
    responses.add(
        responses.POST, STANDINGS_URL,
        body="<html>oops</html>", status=503,
    )

    fetcher = StandingsFetcher(cache_dir=None, min_delay_seconds=0)
    try:
        fetcher.fetch("B12B")
    except RuntimeError as e:
        assert "503" in str(e), f"expected 503 in error message, got: {e}"
        print("test_non_200_raises: PASS")
        return
    raise AssertionError("expected RuntimeError on 503")


if __name__ == "__main__":
    import tempfile
    test_basic_post_request()
    with tempfile.TemporaryDirectory() as d:
        test_caching_avoids_second_request(Path(d))
    test_rate_limiting_enforces_delay()
    test_non_200_raises()
    print("\nAll fetcher tests passed.")
