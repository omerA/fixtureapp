"""
Tests for division discovery and the season helper, run offline against a
saved copy of the real standings form (fixtures/standings_form.html) and a
mocked NCSA backend. No request ever reaches ncsanj.com.

Run:
    python -m pytest -q test_divisions.py
"""
import json
import sys
from datetime import date
from pathlib import Path

import pytest
import responses

sys.path.insert(0, str(Path(__file__).parent))
import build_team_index
from divisions import (
    DivisionDiscoveryError,
    diff_divisions,
    discover_divisions,
    parse_division_codes,
    season_for,
)
from fetcher import STANDINGS_URL, USER_AGENT, StandingsFetcher

FIXTURE = Path(__file__).parent / "fixtures" / "standings_form.html"


@pytest.fixture(scope="module")
def form_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


# ---- parse_division_codes ------------------------------------------------

def test_parse_returns_all_140_codes(form_html):
    codes = parse_division_codes(form_html)
    assert len(codes) == 140
    assert len(set(codes)) == 140


def test_parse_skips_placeholder(form_html):
    assert "0" not in parse_division_codes(form_html)


def test_parse_reflects_this_season(form_html):
    codes = parse_division_codes(form_html)
    assert "B08CB7" in codes  # new this season
    assert "B12A" in codes    # carried over
    assert "B12B" not in codes  # dropped this season


def test_parse_keeps_page_order(form_html):
    assert parse_division_codes(form_html)[:3] == ["B08A4", "B08A7", "B08B4"]


def test_parse_raises_without_dropdown():
    with pytest.raises(DivisionDiscoveryError):
        parse_division_codes("<html><body>Site down for maintenance</body></html>")


def test_parse_ignores_other_selects():
    html = '<select name="club"><option value="Tenafly">Tenafly</option></select>'
    with pytest.raises(DivisionDiscoveryError):
        parse_division_codes(html)


def test_parse_raises_when_only_placeholder():
    html = '<select name="div"><option value="0">Select a Division</option></select>'
    with pytest.raises(DivisionDiscoveryError):
        parse_division_codes(html)


# ---- discover_divisions ----------------------------------------------------

@responses.activate
def test_discover_gets_form_through_fetcher(form_html):
    responses.add(responses.GET, STANDINGS_URL, body=form_html, status=200)
    fetcher = StandingsFetcher(cache_dir=None, min_delay_seconds=0)

    codes = discover_divisions(fetcher)

    assert len(codes) == 140
    assert len(responses.calls) == 1
    assert responses.calls[0].request.headers["User-Agent"] == USER_AGENT


@responses.activate
def test_discover_raises_on_bad_status():
    responses.add(responses.GET, STANDINGS_URL, body="oops", status=503)
    fetcher = StandingsFetcher(cache_dir=None, min_delay_seconds=0)
    with pytest.raises(RuntimeError, match="503"):
        discover_divisions(fetcher)


# ---- diff_divisions / season_for -------------------------------------------

def test_diff_divisions():
    added, removed = diff_divisions(["B12A", "B12B"], ["B12A", "B08CB7"])
    assert added == ["B08CB7"]
    assert removed == ["B12B"]


@pytest.mark.parametrize("day, expected", [
    (date(2026, 1, 1), "2026-spring"),
    (date(2026, 7, 31), "2026-spring"),
    (date(2026, 8, 1), "2026-fall"),
    (date(2026, 10, 6), "2026-fall"),
    (date(2026, 12, 31), "2026-fall"),
    (date(2027, 3, 15), "2027-spring"),
])
def test_season_for(day, expected):
    assert season_for(day) == expected


# ---- build_team_index.main -------------------------------------------------

STANDINGS_PAGE = (
    '<html><body><table id="standings_table"><tbody>'
    '<tr class="standings_row"><td class="team_column">Tenafly-X-Coach</td></tr>'
    '</tbody></table></body></html>'
)


def run_builder(monkeypatch, tmp_path, *extra_args):
    out_path = tmp_path / "team_index.json"
    monkeypatch.setattr(sys, "argv", [
        "build_team_index.py",
        "--out", str(out_path),
        "--cache-dir", str(tmp_path / "cache"),
        "--delay", "0",
        *extra_args,
    ])
    build_team_index.main()
    return json.loads(out_path.read_text(encoding="utf-8"))


@responses.activate
def test_builder_discovers_by_default(monkeypatch, tmp_path, capsys):
    form = (
        '<select name="div"><option value="0">Select a Division</option>'
        '<option value="B12A">B12A</option><option value="B08CB7">B08CB7</option></select>'
    )
    responses.add(responses.GET, STANDINGS_URL, body=form, status=200)
    responses.add(responses.POST, STANDINGS_URL, body=STANDINGS_PAGE, status=200)
    (tmp_path / "team_index.json").write_text(
        json.dumps({"divisions": ["B12A", "B12B"]}), encoding="utf-8"
    )

    data = run_builder(monkeypatch, tmp_path)

    assert data["divisions"] == ["B12A", "B08CB7"]
    assert data["season"] == season_for(date.fromisoformat(data["scraped_at"][:10]))
    out = capsys.readouterr().out
    assert "Added since last index (1): B08CB7" in out
    assert "Removed since last index (1): B12B" in out


@responses.activate
def test_builder_override_skips_discovery(monkeypatch, tmp_path):
    # No GET is registered: a discovery request would raise ConnectionError.
    responses.add(responses.POST, STANDINGS_URL, body=STANDINGS_PAGE, status=200)

    data = run_builder(monkeypatch, tmp_path, "--divisions", "B12A")

    assert data["divisions"] == ["B12A"]
    assert all(call.request.method == "POST" for call in responses.calls)
    assert "season" in data


@responses.activate
def test_builder_aborts_when_discovery_fails(monkeypatch, tmp_path):
    responses.add(responses.GET, STANDINGS_URL, body="<html>no form</html>", status=200)
    out_path = tmp_path / "team_index.json"
    out_path.write_text('{"divisions": ["B12A"]}', encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        run_builder(monkeypatch, tmp_path)

    assert "discovery failed" in str(exc.value)
    # The existing index is left exactly as it was.
    assert json.loads(out_path.read_text(encoding="utf-8")) == {"divisions": ["B12A"]}
    assert len(responses.calls) == 1


@responses.activate
def test_builder_keeps_old_index_when_a_division_errors(monkeypatch, tmp_path):
    # One good division, then the site starts failing: a partial index would
    # make every team in the failed division look gone to the app.
    responses.add(responses.POST, STANDINGS_URL, body=STANDINGS_PAGE, status=200)
    responses.add(responses.POST, STANDINGS_URL, body="down", status=500)
    out_path = tmp_path / "team_index.json"
    out_path.write_text('{"divisions": ["B12A"]}', encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        run_builder(monkeypatch, tmp_path, "--divisions", "B12A,B10A")

    assert exc.value.code == 1
    assert json.loads(out_path.read_text(encoding="utf-8")) == {"divisions": ["B12A"]}


@responses.activate
def test_builder_refuses_index_that_shrank_by_half(monkeypatch, tmp_path):
    form = '<select name="div"><option value="B12A">B12A</option></select>'
    responses.add(responses.GET, STANDINGS_URL, body=form, status=200)
    responses.add(responses.POST, STANDINGS_URL, body=STANDINGS_PAGE, status=200)
    previous = {"divisions": ["B12A"], "by_team": {f"Club-X-{i}": {} for i in range(10)}}
    out_path = tmp_path / "team_index.json"
    out_path.write_text(json.dumps(previous), encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        run_builder(monkeypatch, tmp_path)

    assert "index not updated" in str(exc.value)
    assert json.loads(out_path.read_text(encoding="utf-8")) == previous

    data = run_builder(monkeypatch, tmp_path, "--force")
    assert list(data["by_team"]) == ["Tenafly-X-Coach"]
