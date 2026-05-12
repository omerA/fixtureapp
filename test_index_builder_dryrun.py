"""
Dry-run the index builder against a mock NCSA backend, with realistic
multi-division responses, to prove the orchestration works end-to-end.
"""
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

import responses

sys.path.insert(0, str(Path(__file__).parent))
from fetcher import STANDINGS_URL

logging.basicConfig(level=logging.WARNING)

# Build fake responses for a handful of divisions. Each fake response
# only needs a #standings_table with team_column tds.
def make_response(division: str, teams: list[str]) -> str:
    rows = "\n".join(
        f'<tr class="standings_row"><td class="team_column">{t}</td>'
        f'<td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>'
        for t in teams
    )
    return f'<html><body><table id="standings_table"><tbody>{rows}</tbody></table></body></html>'


FAKE_LEAGUE = {
    "B12B": [
        "WayneBG-B12B-Sanchez",
        "Ajax-B12B-Aufiero",
        "Tenafly-B12B-Schwartzberg",
        "RiverDell-B12B-Sullivan",
    ],
    "B10A": [
        "GlenRock-B10A-Haddad",
        "Tenafly-B10A-Smith",
        "Bergenfield-B10A-Blanco",
    ],
    "B10R": [],  # empty division — not yet flighted
    "G10C": [
        "WestEssex-G10C-Pajuelo",
        "Tenafly-G10C-Jones",
    ],
    "B19R": [
        "SomeClub-B19R-Coach",
    ],
}


@responses.activate
def main():
    # Register mock responses for each division. responses will match on
    # the POST body containing div=<DIVISION>.
    def make_callback(division, teams):
        def cb(request):
            return (200, {}, make_response(division, teams))
        return cb

    for division, teams in FAKE_LEAGUE.items():
        responses.add_callback(
            responses.POST, STANDINGS_URL,
            callback=make_callback(division, teams),
            content_type="text/html",
        )
    # Default catch-all for divisions not in our fake league (returns empty page)
    responses.add(
        responses.POST, STANDINGS_URL,
        body='<html><body>no standings</body></html>', status=200,
    )

    # Use only a subset of divisions to keep the test fast
    divisions = list(FAKE_LEAGUE.keys())

    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "team_index.json"
        cache_dir = Path(tmp) / "cache"

        cmd = [
            sys.executable, str(Path(__file__).parent / "build_team_index.py"),
            "--divisions", ",".join(divisions),
            "--out", str(out_path),
            "--cache-dir", str(cache_dir),
            "--delay", "0",
        ]
        # We need to run inside the same process so responses.activate works.
        # So instead of subprocess, call main() directly.
        sys.argv = cmd[1:]  # strip python executable, set as if invoked
        sys.argv[0] = "build_team_index.py"

        # Import and call main directly so the mocked responses session is shared
        import build_team_index
        build_team_index.main()

        data = json.loads(out_path.read_text())

    # Verify
    assert "Tenafly-B12B-Schwartzberg" in data["by_team"]
    assert data["by_team"]["Tenafly-B12B-Schwartzberg"]["division"] == "B12B"
    assert "Tenafly" in data["by_club"]
    tenafly = data["by_club"]["Tenafly"]
    assert len(tenafly) == 3, f"expected 3 Tenafly teams, got {len(tenafly)}: {tenafly}"
    assert "B10R" in data["empty_divisions"]
    assert not data["errors"]
    print("\nDry-run integration test: PASS")


if __name__ == "__main__":
    main()
