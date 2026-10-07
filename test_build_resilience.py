"""
Verify build_standings.py / build_schedules.py treat empty (retired) divisions
as expected, and still fail loudly on real errors. Fully mocked; no network.
"""
import json
import sys
from pathlib import Path

import pytest
import responses

sys.path.insert(0, str(Path(__file__).parent))
from fetcher import STANDINGS_URL, SCHEDULE_URL

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "b12b_table.html").read_text(encoding="utf-8")
GOOD_STANDINGS = f"<html><body>{FIXTURE_HTML}</body></html>"
EMPTY_PAGE = "<html><body><p>No games found for this division.</p></body></html>"

GOOD_SCHEDULE = """<html><body>
<table id="schedule_table"><tbody>
<tr bgcolor="#FFFFFF">
  <td class="game_division">B12B</td>
  <td><button class="calendar_trigger" data-game-id="1001" data-date="03/29/26"
      data-time="04:15 PM" data-field="Some Field" data-home-team="Tenafly-B12B-Coach"
      data-away-team="Secaucus-B12B-Other"></button></td>
  <td class="game_home_score">2</td>
  <td class="game_visitor_score">1</td>
</tr>
</tbody></table>
</body></html>"""

SCRIPTS = {
    "standings": ("build_standings", STANDINGS_URL, GOOD_STANDINGS),
    "schedules": ("build_schedules", SCHEDULE_URL, GOOD_SCHEDULE),
}


def _mock(url, pages):
    """pages maps division -> (status, body)."""
    def cb(request):
        div = [p.split("=", 1)[1] for p in request.body.split("&") if p.startswith("div=")][0]
        status, body = pages[div]
        return status, {"Content-Type": "text/html"}, body
    responses.add_callback(responses.POST, url, callback=cb)


def _run(kind, tmp_path, monkeypatch, divisions):
    module_name = SCRIPTS[kind][0]
    index = tmp_path / "team_index.json"
    index.write_text(json.dumps({"divisions": divisions, "empty_divisions": []}))
    out_dir = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        f"{module_name}.py", "--divisions", ",".join(divisions),
        "--index", str(index), "--cache-dir", str(tmp_path / "cache"),
        "--out-dir", str(out_dir), "--no-cache", "--delay", "0",
    ])
    module = __import__(module_name)
    code = 0
    try:
        module.main()
    except SystemExit as e:
        code = e.code if e.code is not None else 0
    return code, out_dir


@pytest.mark.parametrize("kind", ["standings", "schedules"])
@responses.activate
def test_mixed_good_and_empty_exits_zero(kind, tmp_path, monkeypatch, capsys):
    _, url, good = SCRIPTS[kind]
    _mock(url, {"B12B": (200, good), "G99Z": (200, EMPTY_PAGE)})

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    stale = out_dir / "G99Z.json"
    stale.write_text('{"keep": "me"}')

    code, out_dir = _run(kind, tmp_path, monkeypatch, ["B12B", "G99Z"])

    assert code == 0
    assert (out_dir / "B12B.json").exists()
    assert stale.read_text() == '{"keep": "me"}'
    assert sorted(p.name for p in out_dir.iterdir()) == ["B12B.json", "G99Z.json"]
    out = capsys.readouterr().out
    assert "Skipped (empty): 1" in out
    assert "G99Z" in out


@pytest.mark.parametrize("kind", ["standings", "schedules"])
@responses.activate
def test_empty_division_writes_no_file(kind, tmp_path, monkeypatch):
    _, url, good = SCRIPTS[kind]
    _mock(url, {"B12B": (200, good), "G99Z": (200, EMPTY_PAGE)})
    code, out_dir = _run(kind, tmp_path, monkeypatch, ["B12B", "G99Z"])
    assert code == 0
    assert [p.name for p in out_dir.iterdir()] == ["B12B.json"]


@pytest.mark.parametrize("kind", ["standings", "schedules"])
@responses.activate
def test_http_500_exits_nonzero(kind, tmp_path, monkeypatch):
    _, url, good = SCRIPTS[kind]
    _mock(url, {"B12B": (200, good), "B13A": (500, "<html>boom</html>")})
    code, out_dir = _run(kind, tmp_path, monkeypatch, ["B12B", "B13A"])
    assert code != 0
    assert (out_dir / "B12B.json").exists()  # good data still written
    assert not (out_dir / "B13A.json").exists()


@pytest.mark.parametrize("kind", ["standings", "schedules"])
@responses.activate
def test_all_empty_exits_nonzero(kind, tmp_path, monkeypatch):
    _, url, _ = SCRIPTS[kind]
    _mock(url, {"G99Y": (200, EMPTY_PAGE), "G99Z": (200, EMPTY_PAGE)})
    code, out_dir = _run(kind, tmp_path, monkeypatch, ["G99Y", "G99Z"])
    assert code != 0
    assert list(out_dir.iterdir()) == []
